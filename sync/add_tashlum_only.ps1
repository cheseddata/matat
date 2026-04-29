# add_tashlum_only.ps1 -- one-shot helper to attach a Tashlumim row to an
# already-inserted Kabala (used to recover from a partial run of
# add_website_donation.ps1 where the Kabala INSERT succeeded but the
# Tashlumim INSERT failed on a validation rule).
#
# 32-bit PowerShell + DAO 3.6.

param(
    [Parameter(Mandatory=$true)][int]    $NumTruma,
    [Parameter(Mandatory=$true)][int]    $NumKabala,
    [Parameter(Mandatory=$true)][string] $Date,
    [Parameter(Mandatory=$true)][double] $AmountUsd,
    [Parameter(Mandatory=$true)][double] $Shaar,
    [Parameter(Mandatory=$true)][string] $ReceiptRef,
    [string] $MdbPath   = 'C:\ztorm\ztormdata.mdb',
    [string] $Workgroup = 'C:\ztorm\ztormw.mdw',
    [string] $User      = 'user',
    [string] $Password  = ''
)

$ErrorActionPreference = 'Stop'

function SqlQuote { param([string] $s); if ($null -eq $s) { return "''" }; return "'" + ($s -replace "'", "''") + "'" }

$engine = New-Object -ComObject DAO.DBEngine.36
$engine.SystemDB = $Workgroup
$ws = $engine.CreateWorkspace('add_tashlum_ws', $User, $Password, 2)
$db = $ws.OpenDatabase($MdbPath, $false, $false)

try {
    $dateStr  = $Date + ' 00:00:00'
    $schumNis = [math]::Round($AmountUsd * $Shaar, 2)
    $shovi    = $AmountUsd
    $heara    = "Stripe website -- receipt " + $ReceiptRef
    $hearaSql = SqlQuote $heara

    $tashlumSql =
        "INSERT INTO Tashlumim " +
        "([num_truma], [erech], [date], [ofen], [status], [schum], [matbea], [schum_nis], [shovi], [num_kabala], [pratim]) " +
        "VALUES " +
        "(" + $NumTruma + ", #" + $dateStr + "#, #" + $dateStr + "#, 'credit', 'ok', " +
        " " + $AmountUsd + ", 'usd', " + $schumNis + ", " + $shovi + ", " + $NumKabala + ", " + $hearaSql + ")"

    $db.Execute($tashlumSql, 128)
    $rsId = $db.OpenRecordset('SELECT @@IDENTITY AS id', 4)
    $newNumTashlum = [int64]$rsId.Fields('id').Value
    $rsId.Close()

    Write-Host ("[OK] Tashlum inserted -- num_tashlum=" + $newNumTashlum + "  num_kabala=" + $NumKabala + "  schum_nis=" + $schumNis)
} finally {
    $db.Close()
    $ws.Close()
}
