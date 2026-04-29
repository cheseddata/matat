# add_website_donation.ps1 -- append a website donation (Stripe / website)
# into the operator's live ZTorm Access DB at C:\ztorm\ztormdata.mdb.
#
# For each donation: inserts ONE Kabalot row (sug='credit') + ONE Tashlumim
# row attached to the donor's open Truma. Captures the auto-assigned
# num_kabala via @@IDENTITY and uses it as the FK on the Tashlumim row.
#
# MUST run under 32-bit PowerShell because DAO 3.6 is 32-bit only.

param(
    [Parameter(Mandatory=$true)][int]    $NumTorem,
    [Parameter(Mandatory=$true)][int]    $NumTruma,
    [Parameter(Mandatory=$true)][string] $Date,
    [Parameter(Mandatory=$true)][double] $AmountUsd,
    [Parameter(Mandatory=$true)][double] $Shaar,
    [Parameter(Mandatory=$true)][string] $DonorName,
    [Parameter(Mandatory=$true)][string] $ReceiptRef,
    [string] $Pratim    = '',
    [string] $MdbPath   = 'C:\ztorm\ztormdata.mdb',
    [string] $Workgroup = 'C:\ztorm\ztormw.mdw',
    [string] $User      = 'user',
    [string] $Password  = '',
    [string] $BackupDir = 'C:\matat\access_mirror',
    [switch] $SkipBackup
)

$ErrorActionPreference = 'Stop'

if (-not (Test-Path $MdbPath))   { Write-Host ("[X] MDB not found: " + $MdbPath); exit 1 }
if (-not (Test-Path $Workgroup)) { Write-Host ("[X] Workgroup not found: " + $Workgroup); exit 1 }

if (-not $SkipBackup) {
    $stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
    $bak = Join-Path $BackupDir ("ztormdata." + $stamp + ".bak.mdb")
    Copy-Item $MdbPath $bak -Force
    Write-Host ("[OK] Backup: " + $bak)
}

function SqlQuote {
    param([string] $s)
    if ($null -eq $s) { return "''" }
    return "'" + ($s -replace "'", "''") + "'"
}

$engine = New-Object -ComObject DAO.DBEngine.36
$engine.SystemDB = $Workgroup

$ws = $engine.CreateWorkspace('add_donation_ws', $User, $Password, 2)
$db = $ws.OpenDatabase($MdbPath, $false, $false)

try {
    # 1. Compute next mispar_kabala (global MAX + 1).
    $rsMax = $db.OpenRecordset('SELECT MAX(mispar_kabala) AS m FROM Kabalot', 4)
    $maxMisparKabala = [int64]$rsMax.Fields('m').Value
    $rsMax.Close()
    $newMispar = $maxMisparKabala + 1
    Write-Host ("  Computed next mispar_kabala = " + $newMispar + " (live max=" + $maxMisparKabala + ")")

    $now      = Get-Date
    $nowStr   = $now.ToString('MM/dd/yyyy HH:mm:ss')
    $dateStr  = $Date + ' 00:00:00'
    $schumNis = [math]::Round($AmountUsd * $Shaar, 2)

    $heara         = "Stripe website -- receipt " + $ReceiptRef
    $donorNameSql  = SqlQuote $DonorName
    $hearaSql      = SqlQuote $heara
    $pratimSql     = SqlQuote $Pratim

    # 2. INSERT Kabalot row. Bracket every column name (many are Jet reserved words).
    $kabalaSql =
        "INSERT INTO Kabalot " +
        "([sug], [mispar_kabala], [date], [matbea], [sum_total], [sum_cash], [num_checks], " +
        " [name], [num_torem], [user], [printed], [time], [canceled], [num_truma], " +
        " [num_mahlaka], [signed], [send_email], [external], [heara], [pratim], [tat_sug], [print_type]) " +
        "VALUES " +
        "('credit', " + $newMispar + ", #" + $dateStr + "#, 'usd', " + $AmountUsd + ", 0, 0, " +
        " " + $donorNameSql + ", " + $NumTorem + ", 'website', False, #" + $nowStr + "#, False, " + $NumTruma + ", " +
        " 3, False, False, True, " + $hearaSql + ", " + $pratimSql + ", 'credit', 'KabalaSignedEng')"

    $db.Execute($kabalaSql, 128)

    # 3. Capture the new num_kabala via @@IDENTITY.
    $rsId = $db.OpenRecordset('SELECT @@IDENTITY AS id', 4)
    $newNumKabala = [int64]$rsId.Fields('id').Value
    $rsId.Close()
    Write-Host ("  Inserted Kabala -- num_kabala=" + $newNumKabala + "  mispar_kabala=" + $newMispar)

    # 4. INSERT Tashlumim row referencing the new num_kabala.
    # ValidationRule on Tashlumim requires `shovi IS NOT NULL AND schum_nis IS
    # NOT NULL` when status='ok'. shovi is the USD-equivalent of the payment
    # (schum_nis / shaar). For matbea='usd' that's just AmountUsd.
    $shovi = $AmountUsd
    $tashlumSql =
        "INSERT INTO Tashlumim " +
        "([num_truma], [erech], [date], [ofen], [status], [schum], [matbea], [schum_nis], [shovi], [num_kabala], [pratim]) " +
        "VALUES " +
        "(" + $NumTruma + ", #" + $dateStr + "#, #" + $dateStr + "#, 'credit', 'ok', " +
        " " + $AmountUsd + ", 'usd', " + $schumNis + ", " + $shovi + ", " + $newNumKabala + ", " + $hearaSql + ")"

    $db.Execute($tashlumSql, 128)

    $rsId = $db.OpenRecordset('SELECT @@IDENTITY AS id', 4)
    $newNumTashlum = [int64]$rsId.Fields('id').Value
    $rsId.Close()
    Write-Host ("  Inserted Tashlum -- num_tashlum=" + $newNumTashlum + "  schum_nis=" + $schumNis)

    Write-Host ("[OK] Donation " + $ReceiptRef + " (" + $AmountUsd + " USD) added to Truma " + $NumTruma)
    Write-Host ("    -> num_kabala=" + $newNumKabala + "  num_tashlum=" + $newNumTashlum + "  mispar_kabala=" + $newMispar)
} finally {
    $db.Close()
    $ws.Close()
}
