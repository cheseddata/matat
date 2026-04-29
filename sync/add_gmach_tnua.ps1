# add_gmach_tnua.ps1 -- append a row to MttData.mdb -> Tnuot table for the
# Gmach "תנועות" tab on the operator's haverim card. Uses an ADO Recordset
# with AddNew/Update so Unicode (Hebrew sug) goes through cleanly without
# encoding round-trips.
#
# Jet OLEDB 4.0 -- 32-bit PowerShell required. No workgroup auth.

param(
    [Parameter(Mandatory=$true)][int]    $CardNo,
    [Parameter(Mandatory=$true)][string] $Date,           # 'MM/DD/YYYY' or 'YYYY-MM-DD'
    [Parameter(Mandatory=$true)][double] $AmountUsd,
    [Parameter(Mandatory=$true)][double] $Shaar,
    [Parameter(Mandatory=$true)][string] $ReceiptRef,
    [int]    $NumTransfer  = 0,
    [string] $MdbPath      = 'C:\Gmach\MttData.mdb',
    [string] $BackupDir    = 'C:\matat\access_mirror',
    [switch] $SkipBackup
)

$ErrorActionPreference = 'Stop'

if (-not (Test-Path $MdbPath)) { Write-Host ("[X] MDB not found: " + $MdbPath); exit 1 }

if (-not $SkipBackup) {
    $stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
    $bak = Join-Path $BackupDir ("MttData." + $stamp + ".bak.mdb")
    Copy-Item $MdbPath $bak -Force
    Write-Host ("[OK] Backup: " + $bak)
}

# Hebrew "תרו" (donation) built from char codes -- avoids source-file encoding pitfalls.
$sug = [string]([char]0x05EA + [char]0x05E8 + [char]0x05D5)

$schumNis = [math]::Round($AmountUsd * $Shaar, 2)
$pratim   = "stripe website -- " + $ReceiptRef
$dateVal  = [datetime] $Date

$cn = New-Object -ComObject ADODB.Connection
$cn.Open("Provider=Microsoft.Jet.OLEDB.4.0;Data Source=$MdbPath;")

try {
    $rs = New-Object -ComObject ADODB.Recordset
    $rs.Open("SELECT * FROM Tnuot WHERE 1=0", $cn, 1, 3)   # adOpenKeyset=1, adLockOptimistic=3
    $rs.AddNew()
    $rs.Fields.Item('card_no').Value      = $CardNo
    $rs.Fields.Item('date').Value         = $dateVal
    $rs.Fields.Item('sug').Value          = $sug
    $rs.Fields.Item('schum_sh').Value     = $schumNis
    $rs.Fields.Item('schum_$').Value      = $AmountUsd
    $rs.Fields.Item('matbea').Value       = '$'
    $rs.Fields.Item('pratim').Value       = $pratim
    $rs.Fields.Item('bank').Value         = 0
    $rs.Fields.Item('num_zacai').Value    = 0
    $rs.Fields.Item('old_schum_nis').Value= 0
    $rs.Fields.Item('amuta').Value        = $false
    $rs.Fields.Item('private').Value      = $true
    $rs.Fields.Item('kabala').Value       = $true
    $rs.Fields.Item('ofen').Value         = 'credit'
    if ($NumTransfer -gt 0) {
        $rs.Fields.Item('num_transfer').Value = $NumTransfer
    }
    $rs.Update()
    $newCounter = $rs.Fields.Item('counter').Value
    Write-Host ("[OK] Tnuot row inserted -- counter=" + $newCounter +
                "  card_no=" + $CardNo + "  date=" + $Date +
                "  schum_`$=" + $AmountUsd + "  schum_sh=" + $schumNis)
    $rs.Close()
} finally {
    $cn.Close()
}
