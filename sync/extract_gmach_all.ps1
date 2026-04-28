# extract_gmach_all.ps1 — faithful full extract of every user table from a
# Gmach-style MDB (MttData.mdb / Mikud.mdb / trans.mdb) to the OutDir as
# pipe-delimited UTF-8 TSV files.
#
# MUST run under 32-bit PowerShell (C:\Windows\SysWOW64\WindowsPowerShell)
# because Jet OLEDB 4.0 is 32-bit only.
#
# For each user table:
#   <SafeName>.tsv          pipe-delimited, header row, ALL columns SELECT *
#   <SafeName>.schema.tsv   col_name | adType | DefinedSize | OrigName
#
# Per the project's "faithful port" rule, every column is preserved (no
# handpicked SELECT lists). The mirror builder uses these to re-create
# SQLite tables with VERBATIM Access names.

param(
    [Parameter(Mandatory=$true)][string] $MdbPath,
    [Parameter(Mandatory=$true)][string] $OutDir,
    [string] $Prefix = ''   # optional prefix for output filenames (e.g., "MttData_")
)

$ErrorActionPreference = 'Continue'   # per-table errors should not abort

if (-not (Test-Path $MdbPath)) { Write-Host "[X] MDB not found: $MdbPath"; exit 1 }
if (-not (Test-Path $OutDir))  { New-Item -ItemType Directory -Path $OutDir | Out-Null }

# Pipe-delimited format. Cells with embedded pipes/newlines get escaped:
#   | -> \|     \r -> \r     \n -> \n     \  -> \\
# (Decoder reverses these in build_mirror_sqlite.py.)
function EscapeCell {
    param([object] $v)
    if ($null -eq $v -or [DBNull]::Value.Equals($v)) { return '\N' }
    $s = [string] $v
    $s = $s.Replace('\','\\').Replace('|','\|').Replace("`r",'\r').Replace("`n",'\n').Replace("`t",'\t')
    return $s
}

function SafeName { param([string] $n) ($n -replace '[\\/:*?"<>|]', '_') }

$cn = New-Object -ComObject ADODB.Connection
try {
    $cn.Open("Provider=Microsoft.Jet.OLEDB.4.0;Data Source=$MdbPath;")
} catch {
    Write-Host "[X] Cannot open MDB: $_"; exit 2
}
Write-Host "  Connected to $MdbPath"

# Enumerate user tables via OpenSchema (adSchemaTables = 20)
$tables = @()
$schema = $cn.OpenSchema(20)
while (-not $schema.EOF) {
    $type = $schema.Fields.Item('TABLE_TYPE').Value
    $name = $schema.Fields.Item('TABLE_NAME').Value
    if ($type -eq 'TABLE' -and $name -notlike 'MSys*' -and $name -notlike '~*') {
        $tables += $name
    }
    $schema.MoveNext()
}
$schema.Close()

Write-Host ("  Found {0} user tables" -f $tables.Count)

$utf8NoBom = New-Object System.Text.UTF8Encoding($false)

foreach ($t in $tables) {
    $safe = SafeName $t
    $tsvPath    = Join-Path $OutDir ("{0}{1}.tsv"        -f $Prefix, $safe)
    $schemaPath = Join-Path $OutDir ("{0}{1}.schema.tsv" -f $Prefix, $safe)

    try {
        $rs = New-Object -ComObject ADODB.Recordset
        $rs.CursorLocation = 3   # adUseClient (snapshot loaded into memory)
        $rs.Open("SELECT * FROM [$t]", $cn, 3, 1)

        # Build schema in memory (so we don't leave a dangling empty file on error)
        $schemaLines = New-Object System.Collections.Generic.List[string]
        $schemaLines.Add('name|adType|DefinedSize|orig_table')
        $headers = @()
        foreach ($f in $rs.Fields) {
            $name = EscapeCell $f.Name
            $type = $f.Type
            $size = 0
            try { $size = [int] $f.DefinedSize } catch { $size = 0 }
            $schemaLines.Add(("{0}|{1}|{2}|{3}" -f $name, $type, $size, (EscapeCell $t)))
            $headers += $name
        }

        # Write schema (only after successful enumeration)
        [System.IO.File]::WriteAllLines($schemaPath, $schemaLines, $utf8NoBom)

        # Data file — header + rows
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
        # Clean up any half-written files so build_mirror doesn't try to import them
        if (Test-Path $schemaPath) { Remove-Item $schemaPath -Force -ErrorAction SilentlyContinue }
        if (Test-Path $tsvPath)    { Remove-Item $tsvPath    -Force -ErrorAction SilentlyContinue }
        if ($rs -and $rs.State -eq 1) { try { $rs.Close() } catch {} }
    }
}

$cn.Close()
Write-Host "  Done."
