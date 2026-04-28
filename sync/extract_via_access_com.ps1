# extract_via_access_com.ps1 — extract tables from a front-end MDB that has
# them linked to a secured back-end. Use this when Jet OLEDB direct access
# to the back-end fails with "no read permission" (e.g., Mikud.mdb under
# Mtorm.mdw security). The front-end's existing linked-table credentials
# are honored automatically.
#
# Output format matches extract_gmach_all.ps1: pipe-delimited UTF-8 TSV
# files plus per-table .schema.tsv.
#
# Params:
#   -FrontEnd            path to front-end MDB (e.g. mtt2003local.mdb)
#   -OnlyForBackEnd      optional substring to match against TableDef.Connect;
#                        only tables linked to a back-end matching this filter
#                        are dumped (e.g., "Mikud.mdb"). Empty = dump all.
#   -OutDir              where to write the .tsv / .schema.tsv files

param(
    [Parameter(Mandatory=$true)][string] $FrontEnd,
    [Parameter(Mandatory=$true)][string] $OutDir,
    [string] $OnlyForBackEnd = ''
)

$ErrorActionPreference = 'Continue'

if (-not (Test-Path $FrontEnd)) { Write-Host "[X] Front-end MDB not found: $FrontEnd"; exit 1 }
if (-not (Test-Path $OutDir))  { New-Item -ItemType Directory -Path $OutDir | Out-Null }

function EscapeCell {
    param([object] $v)
    if ($null -eq $v -or [DBNull]::Value.Equals($v)) { return '\N' }
    $s = [string] $v
    $s = $s.Replace('\','\\').Replace('|','\|').Replace("`r",'\r').Replace("`n",'\n').Replace("`t",'\t')
    return $s
}

function SafeName { param([string] $n) ($n -replace '[\\/:*?"<>|]', '_') }

$utf8NoBom = New-Object System.Text.UTF8Encoding($false)

$app = New-Object -ComObject Access.Application
$app.AutomationSecurity = 3   # disable AutoExec macros

try {
    $app.OpenCurrentDatabase($FrontEnd, $false)
} catch {
    Write-Host ("[X] Cannot open front-end: {0}" -f $_.Exception.Message)
    $app.Quit()
    exit 2
}

# Close any forms AutoExec opened
while ($app.Forms.Count -gt 0) {
    try { $app.DoCmd.Close(2, $app.Forms.Item(0).Name, 2) } catch { break }
}

$db = $app.CurrentDb()

# Pick which tables to dump.
# - Local (non-linked) tables: include if no filter (so caller can dump
#   front-end-only tables when they want)
# - Linked tables: include if the Connect string contains $OnlyForBackEnd
$names = New-Object System.Collections.Generic.List[string]
foreach ($td in $db.TableDefs) {
    $tn = $td.Name
    if ($tn.StartsWith('MSys') -or $tn.StartsWith('USys') -or $tn.StartsWith('~')) { continue }

    $connect = ''
    try { $connect = [string] $td.Connect } catch {}

    if ($connect.Length -gt 0) {
        if ($OnlyForBackEnd -and ($connect -notlike "*$OnlyForBackEnd*")) { continue }
    } else {
        if ($OnlyForBackEnd) { continue }   # caller wants only one back-end -> skip local
    }
    $names.Add($tn)
}

Write-Host ("  {0}: {1} tables to dump (filter='{2}')" -f [System.IO.Path]::GetFileName($FrontEnd), $names.Count, $OnlyForBackEnd)

foreach ($t in $names) {
    $safe = SafeName $t
    $tsvPath    = Join-Path $OutDir ("{0}.tsv"        -f $safe)
    $schemaPath = Join-Path $OutDir ("{0}.schema.tsv" -f $safe)

    try {
        $rs = $db.OpenRecordset($t, 4)   # dbOpenSnapshot

        $schemaLines = New-Object System.Collections.Generic.List[string]
        $schemaLines.Add('name|adType|DefinedSize|orig_table')
        $headers = @()
        foreach ($f in $rs.Fields) {
            $size = 0; try { $size = [int] $f.Size } catch {}
            $schemaLines.Add(("{0}|{1}|{2}|{3}" -f (EscapeCell $f.Name), $f.Type, $size, (EscapeCell $t)))
            $headers += (EscapeCell $f.Name)
        }
        [System.IO.File]::WriteAllLines($schemaPath, $schemaLines, $utf8NoBom)

        $sw = New-Object System.IO.StreamWriter($tsvPath, $false, $utf8NoBom)
        $sw.WriteLine($headers -join '|')
        $n = 0
        while (-not $rs.EOF) {
            $cells = @()
            foreach ($f in $rs.Fields) {
                try   { $cells += (EscapeCell $f.Value) }
                catch { $cells += '\N' }
            }
            $sw.WriteLine($cells -join '|')
            $n++
            if ($n % 20000 -eq 0) { $sw.Flush(); Write-Host ("    {0}: {1:N0} rows" -f $t, $n) }
            $rs.MoveNext()
        }
        $sw.Close()
        $rs.Close()
        Write-Host ("  {0}: {1:N0} rows -> {2}" -f $t, $n, [System.IO.Path]::GetFileName($tsvPath))
    } catch {
        Write-Host ("  [!] skip {0} : {1}" -f $t, $_.Exception.Message)
        if (Test-Path $schemaPath) { Remove-Item $schemaPath -Force -ErrorAction SilentlyContinue }
        if (Test-Path $tsvPath)    { Remove-Item $tsvPath    -Force -ErrorAction SilentlyContinue }
    }
}

$app.CloseCurrentDatabase()
$app.Quit()
[void][System.Runtime.Interopservices.Marshal]::ReleaseComObject($app)
[GC]::Collect()
Write-Host "  Done."
