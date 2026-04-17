# Extract the big Gemach transaction tables (Peulot + Tnuot + Munz)
# from MttData.mdb to pipe-delimited UTF-8 text files.
# Must run under 32-bit PowerShell (SysWOW64) because Jet OLEDB 4.0 is 32-bit.
param(
    [Parameter(Mandatory=$true)][string] $MdbPath,
    [Parameter(Mandatory=$true)][string] $OutDir
)

if (-not (Test-Path $MdbPath)) { Write-Host "[X] MDB not found: $MdbPath"; exit 1 }
if (-not (Test-Path $OutDir)) { New-Item -ItemType Directory -Path $OutDir | Out-Null }

$cn = New-Object -ComObject ADODB.Connection
try {
    $cn.Open("Provider=Microsoft.Jet.OLEDB.4.0;Data Source=$MdbPath;")
} catch {
    Write-Host "[X] Cannot open MDB: $_"
    exit 2
}
Write-Host "  Connected to $MdbPath"

function Export-Table {
    param([string] $TableName, [string] $Sql, [string] $OutFile)
    $fullPath = Join-Path $OutDir $OutFile
    if (Test-Path $fullPath) { Remove-Item $fullPath -Force }

    $rs = New-Object -ComObject ADODB.Recordset
    $rs.CursorLocation = 3
    try {
        $rs.Open($Sql, $cn, 3, 1)
    } catch {
        Write-Host "  [!] skip $TableName : $_"
        return
    }

    $utf8NoBom = New-Object System.Text.UTF8Encoding($false)
    $sw = New-Object System.IO.StreamWriter($fullPath, $false, $utf8NoBom)

    $headerNames = @(); foreach ($f in $rs.Fields) { $headerNames += $f.Name }
    $sw.WriteLine($headerNames -join '|')

    $fc = $rs.Fields.Count
    $n = 0
    $sb = New-Object System.Text.StringBuilder(16384)
    while (-not $rs.EOF) {
        [void]$sb.Clear()
        for ($i = 0; $i -lt $fc; $i++) {
            if ($i -gt 0) { [void]$sb.Append('|') }
            $v = $rs.Fields.Item($i).Value
            if ($null -ne $v -and $v -isnot [System.DBNull]) {
                if ($v -is [DateTime]) { [void]$sb.Append($v.ToString('yyyy-MM-dd')) }
                else { [void]$sb.Append([string]$v) }
            }
        }
        $sw.WriteLine($sb.ToString())
        $n++
        if ($n % 10000 -eq 0) { $sw.Flush(); Write-Host ("    {0}: {1} rows" -f $TableName, $n) }
        $rs.MoveNext() | Out-Null
    }
    $sw.Flush(); $sw.Close(); $rs.Close()
    Write-Host ("  {0}: {1:N0} rows -> {2}" -f $TableName, $n, $OutFile)
}

Export-Table -TableName 'Munz'   -OutFile 'munz.txt' `
  -Sql 'SELECT card_no, id, name, yom, hodesh, shana, pail, sium_kadish_yomi, date_klita, hudpas_tizcoret, hudpas_kadish FROM Munz ORDER BY id'

Export-Table -TableName 'Peulot' -OutFile 'peulot.txt' `
  -Sql 'SELECT num_hork, [date], asmachta, schum, hazar, siba, sug, schum_d, num_zacai, counter, kabala, num_transfer FROM Peulot ORDER BY counter'

Export-Table -TableName 'Tnuot'  -OutFile 'tnuot.txt' `
  -Sql 'SELECT card_no, [date], counter, tash, sug, schum_sh, [schum_$], matbea, date_peraon, pratim, bank, num_check, num_zacai, amuta, private, num_sgira, kabala, kabala_date, ofen, num_transfer, erech, snif, heshbon FROM Tnuot ORDER BY counter'

$cn.Close()
Write-Host "DONE (big tables)"
