$cn = New-Object -ComObject ADODB.Connection
$cn.Open('Provider=Microsoft.Jet.OLEDB.4.0;Data Source=C:\Gmach\MttData.mdb;')
$rs = $cn.Execute("SELECT counter, card_no, [date], sug, schum_sh, [schum_$], matbea, pratim, ofen FROM Tnuot WHERE card_no=4087 ORDER BY [date] DESC, counter DESC")
Write-Host '=== Mendy (4087) Gmach Tnuot rows -- newest first ==='
while (-not $rs.EOF) {
    $cnt = $rs.Fields.Item('counter').Value
    $dt  = $rs.Fields.Item('date').Value
    $sug = $rs.Fields.Item('sug').Value
    $usd = $rs.Fields.Item('schum_$').Value
    $nis = $rs.Fields.Item('schum_sh').Value
    $of  = $rs.Fields.Item('ofen').Value
    $pr  = $rs.Fields.Item('pratim').Value
    Write-Host ("  counter=$cnt  date=$dt  sug=$sug  USD=$usd  NIS=$nis  ofen=$of  pratim=$pr")
    $rs.MoveNext()
}
$rs.Close()
$cn.Close()
