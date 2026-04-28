# extract_ztorm_dao.ps1 — extract every user table from a ZTorm-style MDB
# via DAO with explicit workgroup credentials. This is the fallback path
# for tables that access_parser can't decode (memo fields with the
# "NoneType is not subscriptable" bug).
#
# MUST run under 32-bit PowerShell because DAO 3.6 is 32-bit only.
#
# Output format matches extract_gmach_all.ps1.

param(
    [Parameter(Mandatory=$true)][string] $MdbPath,
    [Parameter(Mandatory=$true)][string] $OutDir,
    [string] $Workgroup = 'C:\ztorm\ztormw.mdw',
    [string] $User      = 'user',
    [string] $Password  = '',
    [string[]] $OnlyTables = @()
)

$ErrorActionPreference = 'Continue'

if (-not (Test-Path $MdbPath))    { Write-Host "[X] MDB not found: $MdbPath"; exit 1 }
if (-not (Test-Path $Workgroup))  { Write-Host "[X] Workgroup not found: $Workgroup"; exit 1 }
if (-not (Test-Path $OutDir))     { New-Item -ItemType Directory -Path $OutDir | Out-Null }

function EscapeCell {
    param([object] $v)
    if ($null -eq $v -or [DBNull]::Value.Equals($v)) { return '\N' }
    $s = [string] $v
    $s = $s.Replace('\','\\').Replace('|','\|').Replace("`r",'\r').Replace("`n",'\n').Replace("`t",'\t')
    return $s
}

function SafeName { param([string] $n) ($n -replace '[\\/:*?"<>|]', '_') }

$utf8NoBom = New-Object System.Text.UTF8Encoding($false)

$engine = New-Object -ComObject DAO.DBEngine.36
$engine.SystemDB = $Workgroup

try {
    $ws = $engine.CreateWorkspace('temp_ztorm_dao', $User, $Password, 2)
    $db = $ws.OpenDatabase($MdbPath, $false, $true)   # not-exclusive, read-only
} catch {
    Write-Host ("[X] Cannot open via DAO: {0}" -f $_.Exception.Message)
    exit 2
}

# Enumerate user TableDefs (skip MSys/USys system tables and linked tables)
$tables = New-Object System.Collections.Generic.List[string]
foreach ($td in $db.TableDefs) {
    $tn = $td.Name
    if ($tn.StartsWith('MSys') -or $tn.StartsWith('USys') -or $tn.StartsWith('~')) { continue }
    $connect = ''
    try { $connect = [string] $td.Connect } catch {}
    if ($connect.Length -gt 0) { continue }
    if ($OnlyTables.Count -gt 0 -and -not ($OnlyTables -contains $tn)) { continue }
    $tables.Add($tn)
}

Write-Host ("  Found {0} tables to dump from {1}" -f $tables.Count, [System.IO.Path]::GetFileName($MdbPath))

foreach ($t in $tables) {
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

$db.Close()
Write-Host "  Done."
