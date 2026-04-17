# Extract the smaller Gemach tables (haverim, hork, btlhork, lookups,
# translate, setup) from MttData.mdb. Mirrors the legacy VBS ID extract.
param(
    [Parameter(Mandatory=$true)][string] $MdbPath,
    [Parameter(Mandatory=$true)][string] $OutDir
)

if (-not (Test-Path $MdbPath)) { Write-Host "[X] MDB not found: $MdbPath"; exit 1 }
if (-not (Test-Path $OutDir)) { New-Item -ItemType Directory -Path $OutDir | Out-Null }

$cn = New-Object -ComObject ADODB.Connection
try { $cn.Open("Provider=Microsoft.Jet.OLEDB.4.0;Data Source=$MdbPath;") }
catch { Write-Host "[X] Cannot open MDB: $_"; exit 2 }

function Export-Table {
    param([string] $TableName, [string] $Sql, [string] $OutFile)
    $fullPath = Join-Path $OutDir $OutFile
    if (Test-Path $fullPath) { Remove-Item $fullPath -Force }

    $rs = New-Object -ComObject ADODB.Recordset
    $rs.CursorLocation = 3
    try { $rs.Open($Sql, $cn, 3, 1) }
    catch { Write-Host "  [!] skip $TableName : $_"; return }

    $utf8NoBom = New-Object System.Text.UTF8Encoding($false)
    $sw = New-Object System.IO.StreamWriter($fullPath, $false, $utf8NoBom)
    $names = @(); foreach ($f in $rs.Fields) { $names += $f.Name }
    $sw.WriteLine($names -join '|')

    $fc = $rs.Fields.Count; $n = 0
    $sb = New-Object System.Text.StringBuilder(4096)
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
        $rs.MoveNext() | Out-Null
    }
    $sw.Close(); $rs.Close()
    Write-Host ("  {0}: {1:N0} rows -> {2}" -f $TableName, $n, $OutFile)
}

# The column list mirrors F:\gemach\extract\extract_ids.vbs so the
# existing importer (import_gmach_data.py) consumes the same pipe files.
Export-Table 'Haverim'     'SELECT card_no, last_name, first_name, toar, tel, tel_kidomet, t_z, num_torem, num_truma, date_klita, sug FROM Haverim ORDER BY card_no' 'haverim.txt'
Export-Table 'Hork'        'SELECT num_hork, card_no, status, matbea, schum, date_hathala, hithayev, buza, hazar, yom, sug, num_mosad, bank, snif, heshbon, num_zacai, tkufa FROM Hork ORDER BY num_hork' 'hork.txt'
Export-Table 'Btlhork'     'SELECT num_hork, date_hathala, matbea, schum, hithayev, buza, hazar, date_hiuv_aharon, asmachta, siba, pratim, tkufa, sug FROM Btlhork ORDER BY num_hork' 'btlhork.txt'
Export-Table 'Mosadot'     'SELECT num_mosad, shem_mosad, code_mosad, pail FROM Mosadot ORDER BY num_mosad' 'mosadot.txt'
Export-Table 'HashAccts'   'SELECT acct_no, name, [desc] FROM HashAccts ORDER BY acct_no' 'hashaccts.txt'
Export-Table 'Translate'   'SELECT id, tormim, gmach FROM Translate ORDER BY id' 'translate.txt'
Export-Table 'Setup'       'SELECT [key], value, [desc] FROM Setup ORDER BY [key]' 'setup.txt'
Export-Table 'Sibot bitul' 'SELECT code_siba, shem_siba, lvatel FROM [Sibot bitul] ORDER BY code_siba' 'sibot_bitul.txt'
Export-Table 'Sugei Tnua'  'SELECT sug_tnua, teur FROM [Sugei Tnua] ORDER BY sug_tnua' 'sugei_tnua.txt'

$cn.Close()
Write-Host "DONE (small tables)"
