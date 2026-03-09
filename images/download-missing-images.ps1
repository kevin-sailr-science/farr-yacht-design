# Farr Yacht Design — Download Missing Yacht Images
# Run this from the images/ directory: powershell -ExecutionPolicy Bypass -File download-missing-images.ps1
# Sources: Wikimedia Commons (CC-licensed)

$images = @{
    # Volvo Ocean Race
    "volvo-ocean-60-team-news-corp.jpg" = "https://upload.wikimedia.org/wikipedia/commons/thumb/2/2a/VO60_2002_Kiel_SEB_tyco_NewsCorp.jpg/960px-VO60_2002_Kiel_SEB_tyco_NewsCorp.jpg"
    "volvo-ocean-60-team-seb.jpg" = "https://upload.wikimedia.org/wikipedia/commons/thumb/2/2a/VO60_2002_Kiel_SEB_tyco_NewsCorp.jpg/960px-VO60_2002_Kiel_SEB_tyco_NewsCorp.jpg"
    "volvo-ocean-60-team-tyco.jpg" = "https://upload.wikimedia.org/wikipedia/commons/thumb/2/2a/VO60_2002_Kiel_SEB_tyco_NewsCorp.jpg/960px-VO60_2002_Kiel_SEB_tyco_NewsCorp.jpg"
    "volvo-open-70-telefonica-blue.jpg" = "https://upload.wikimedia.org/wikipedia/commons/thumb/5/57/VOR2008_Telefonica_Blue.jpg/960px-VOR2008_Telefonica_Blue.jpg"
    "volvo-open-70-telefonica-blue-2.jpg" = "https://upload.wikimedia.org/wikipedia/commons/thumb/5/57/VOR2008_Telefonica_Blue.jpg/960px-VOR2008_Telefonica_Blue.jpg"
    # IMOCA
    "hugo-boss.jpg" = "https://upload.wikimedia.org/wikipedia/commons/thumb/a/ab/Hugo_Boss_TJV_2019.jpg/960px-Hugo_Boss_TJV_2019.jpg"
    "imoca-60-2018.jpg" = "https://upload.wikimedia.org/wikipedia/commons/thumb/b/ba/Sailing_yacht_-_IMOCA_60_-_Ystad-2017.jpg/960px-Sailing_yacht_-_IMOCA_60_-_Ystad-2017.jpg"
    # One-designs
    "platu-25.jpg" = "https://upload.wikimedia.org/wikipedia/commons/1/11/Platu25_SUVLM06_9.jpg"
}

$total = $images.Count
$done = 0

foreach ($entry in $images.GetEnumerator()) {
    $done++
    $file = $entry.Key
    $url = $entry.Value
    Write-Host "[$done/$total] Downloading $file..." -NoNewline
    try {
        Invoke-WebRequest -Uri $url -OutFile $file -UseBasicParsing
        $size = (Get-Item $file).Length / 1KB
        Write-Host " OK ($([math]::Round($size))KB)" -ForegroundColor Green
    } catch {
        Write-Host " FAILED: $_" -ForegroundColor Red
    }
}

Write-Host "`nDone! Downloaded $done images." -ForegroundColor Cyan
Write-Host "Now run: git add -A && git commit -m 'Add Wikimedia Commons yacht photos' && git push" -ForegroundColor Yellow
