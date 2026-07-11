Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$Root = $PSScriptRoot
$Backend = Join-Path $Root "backend"
$Frontend = Join-Path $Root "frontend"
$Pages = Join-Path $Frontend "pages"

Write-Host ""
Write-Host "=============================="
Write-Host "Kasi Flavour Deployment"
Write-Host "=============================="

# Step 1
Write-Host "`n[1/4] Moving HTML files..."

if (Test-Path $Pages) {

    Get-ChildItem $Pages -Filter *.html | ForEach-Object {

        $dest = Join-Path $Frontend $_.Name

        if (!(Test-Path $dest)) {
            Move-Item $_.FullName $dest
            Write-Host "Moved $($_.Name)"
        }

    }

    if ((Get-ChildItem $Pages | Measure-Object).Count -eq 0) {
        Remove-Item $Pages
    }

}

# Step 2
Write-Host "`n[2/4] Updating HTML paths..."

Get-ChildItem $Frontend -Filter *.html | ForEach-Object {

    $text = Get-Content $_.FullName -Raw

    $text = $text.Replace("../css/","./css/")
    $text = $text.Replace("../js/","./js/")
    $text = $text.Replace("../images/","./images/")
    $text = $text.Replace("pages/","")

    Set-Content $_.FullName $text

}

# Step 3
Write-Host "`n[3/4] Installing Python packages..."

$req = Join-Path $Backend "requirements.txt"

if (Test-Path $req) {
    pip install -r $req
}

# Step 4
Write-Host "`n[4/4] Installing FastAPI..."

pip install --upgrade "fastapi>=0.139.0"

Write-Host ""
Write-Host "Done."
Write-Host ""
Write-Host "Run:"
Write-Host "cd backend"
Write-Host "uvicorn main:app --reload"