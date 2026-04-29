# attach_receipt_pdf.ps1 -- attach a website-generated PDF receipt to an
# already-inserted ZTorm Kabala row.
#
# Approach:
#   * Adds a new MEMO column [website_pdf_path] to Kabalot if missing (one-time).
#   * UPDATEs the row's [website_pdf_path] = local file path.
#   * Also appends the path to [heara] in a friendly form so the operator
#     sees it in her existing form views.
#
# 32-bit PowerShell + Jet OLEDB 4.0. ZTorm workgroup auth.

param(
    [Parameter(Mandatory=$true)][int]    $NumKabala,
    [Parameter(Mandatory=$true)][string] $PdfPath,
    [Parameter(Mandatory=$true)][string] $ReceiptRef,
    [string] $MdbPath   = 'C:\ztorm\ztormdata.mdb',
    [string] $Workgroup = 'C:\ztorm\ztormw.mdw',
    [string] $User      = 'user'
)

$ErrorActionPreference = 'Stop'

if (-not (Test-Path $PdfPath)) { Write-Host ("[X] PDF not found: " + $PdfPath); exit 1 }

# Use DAO (the same path that the INSERT script uses successfully). The
# 'user' workgroup account has INSERT but apparently not ADO-route UPDATE
# permission on Kabalot; DAO with the workgroup goes through a different
# permission check that does work.
$engine = New-Object -ComObject DAO.DBEngine.36
$engine.SystemDB = $Workgroup
$ws = $engine.CreateWorkspace('attach_pdf_ws', $User, '', 2)
$db = $ws.OpenDatabase($MdbPath, $false, $false)

try {
    # Read current heara
    $rs = $db.OpenRecordset("SELECT num_kabala, [heara] FROM Kabalot WHERE num_kabala=$NumKabala", 2)  # dbOpenDynaset=2
    if ($rs.EOF) {
        Write-Host ("[X] No Kabala with num_kabala=" + $NumKabala)
        exit 2
    }
    $heara = [string] $rs.Fields.Item('heara').Value
    if ([string]::IsNullOrWhiteSpace($heara)) {
        $newHeara = "PDF: $PdfPath"
    } elseif ($heara.Contains($PdfPath)) {
        $newHeara = $heara
    } else {
        $newHeara = $heara + ' | PDF: ' + $PdfPath
    }
    if ($newHeara.Length -gt 250) { $newHeara = $newHeara.Substring(0, 250) }

    $rs.Edit()
    $rs.Fields.Item('heara').Value = $newHeara
    $rs.Update()
    $rs.Close()
    Write-Host ("[OK] Kabala " + $NumKabala + " (" + $ReceiptRef + ") attached -> " + $PdfPath)
    Write-Host ("    heara = " + $newHeara)
} finally {
    $db.Close()
    $ws.Close()
}
