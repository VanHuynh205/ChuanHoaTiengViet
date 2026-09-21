# Rebuild diacritic assets (word_map + bigram_freq) from DataDauCau CSVs.
# Designed for 16GB RAM / laptop CPU: the streaming builder prunes bigrams
# periodically and checkpoints progress (resumable with -Resume).
#
# Usage (tu backend/ hoac repo root):
#   powershell -ExecutionPolicy Bypass -File scripts\rebuild_diacritic_assets.ps1              # build val+train
#   powershell ... -IncludeTest                                                                # them test.csv
#   powershell ... -ChatWeight 3                                                               # CSV trong DataDauCau\chat\ duoc nhan x3
#   powershell ... -SmokeOnly                                                                  # chi thu voi sample_5k.csv
#
# An toan du lieu: asset dang song duoc backup vao data\diacritic\backup\<timestamp>\
# truoc khi ghi de; regression test chay ngay sau build.

param(
    [switch]$IncludeTest,
    [double]$ChatWeight = 2.0,
    [switch]$SmokeOnly,
    [switch]$Resume,
    [int]$ChunkSize = 1000000
)

$ErrorActionPreference = "Stop"
# Python builder ghi tien do vao stderr - khong bien thanh terminating error (pwsh 7+)
$PSNativeCommandUseErrorActionPreference = $false
$RepoRoot = Split-Path $PSScriptRoot -Parent
$Py = Join-Path $RepoRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $Py)) { $Py = "python" }
$Backend = Join-Path $RepoRoot "backend"
# Vi tri chuan cua corpus (theo build_bigram_index.py + test_mine_phrases.py).
# Van fallback ve repo-root\DataDauCau neu ban de o cho cu.
$CorpusDir = Join-Path $Backend "data\DataDauCau"
if (-not (Test-Path $CorpusDir)) { $CorpusDir = Join-Path $RepoRoot "DataDauCau" }
$Stamp = Get-Date -Format "yyyyMMdd_HHmmss"
$BackupDir = Join-Path $Backend "data\diacritic\backup\$Stamp"

Push-Location $Backend
try {
    # --- 0) Kiem tra corpus -------------------------------------------------
    $inputs = @()
    foreach ($name in @("ViDiacritics_val.csv", "ViDiacritics_train.csv")) {
        $p = Join-Path $CorpusDir $name
        if (Test-Path $p) { $inputs += $p }
    }
    if ($IncludeTest) {
        $p = Join-Path $CorpusDir "ViDiacritics_test.csv"
        if (Test-Path $p) { $inputs += $p }
    }
    if (-not $inputs) { Write-Host "Khong tim thay ViDiacritics_val/train trong $CorpusDir" -ForegroundColor Red; exit 1 }

    # CSV chat: dat bat ky file .csv vao DataDauCau\chat\ de duoc nhan trong so
    $chatDir = Join-Path $CorpusDir "chat"
    $chatFiles = @()
    if (Test-Path $chatDir) {
        $chatFiles = Get-ChildItem $chatDir -Filter *.csv -File | ForEach-Object { $_.FullName }
    }

    Write-Host "== Corpus ==" -ForegroundColor Cyan
    foreach ($p in $inputs) { Write-Host ("  news : {0} ({1:N0} MB)" -f (Split-Path $p -Leaf), ((Get-Item $p).Length/1MB)) }
    foreach ($p in $chatFiles) { Write-Host ("  chat : {0} ({1:N0} MB) weight x{2}" -f (Split-Path $p -Leaf), ((Get-Item $p).Length/1MB), $ChatWeight) -ForegroundColor Cyan }
    if ($SmokeOnly) { Write-Host "SMOKE MODE: chi dung sample_5k.csv, ghi vao staging." -ForegroundColor Yellow }

    # --- 1) Backup asset dang song -----------------------------------------
    if (-not $SmokeOnly) {
        New-Item -ItemType Directory -Force -Path $BackupDir | Out-Null
        foreach ($f in @("word_map.json", "bigram_freq.json", "diacritic_assets_manifest.json")) {
            $src = Join-Path $Backend "data\diacritic\$f"
            if (Test-Path $src) { Copy-Item $src $BackupDir }
        }
        Write-Host "== Backup asset cu -> $BackupDir" -ForegroundColor Cyan
    }

    # --- 2) Build ------------------------------------------------------------
    $outDir = "data/diacritic"
    $argList = @()
    $weightArgs = @()
    if ($SmokeOnly) {
        $argList += Join-Path $CorpusDir "sample_5k.csv"
        $outDir = "data/diacritic/.smoke"
    } else {
        $argList += $inputs
        if ($IncludeTest) { $argList += (Join-Path $CorpusDir "ViDiacritics_test.csv") }
        foreach ($p in $chatFiles) {
            $argList += $p
            $weightArgs += "--weight", "$p=$ChatWeight"
        }
    }

    $buildArgs = @("scripts/build_diacritic_streaming.py", "--input") + $argList +
        @("--output-dir", $outDir, "--chunk-size", $ChunkSize, "--bigram-top-n", "220000") +
        $weightArgs
    if ($Resume) { $buildArgs += "--resume" }

    Write-Host "== Build bat dau (chunk $ChunkSize dong, co checkpoint - crash chi can chay lai voi -Resume) ==" -ForegroundColor Cyan
    & $Py @buildArgs
    if ($LASTEXITCODE -ne 0) { throw "Build that bai (exit $LASTEXITCODE). Chay lai voi -Resume de tiep tuc tu checkpoint." }

    if ($SmokeOnly) {
        Write-Host "== SMOKE OK. Asset live KHONG bi thay doi (staging: data/diacritic/.smoke)." -ForegroundColor Green
        exit 0
    }

    # --- 3) Regression test ---------------------------------------------------
    # basetemp nam trong workspace: %TEMP% ngoai sandbox bi chan scandir va cac
    # thu muc pytest tmp cu o repo root da bi khoa ACL (khong the rmtree).
    $Basetemp = Join-Path $RepoRoot ".scratch\pytest-rebuild-tmp"
    Write-Host "== Chay regression diacritic ==" -ForegroundColor Cyan
    & $Py -m pytest tests/test_diacritic_regression.py tests/test_diacritic_restorer.py tests/test_context_phrase_guard.py tests/test_bigram_scoring.py -q --no-header -p no:cacheprovider --basetemp="$Basetemp"
    if ($LASTEXITCODE -ne 0) {
        Write-Host "REGRESSION THAT BAI - asset moi van o cho nhung co the bi loi nghia." -ForegroundColor Red
        Write-Host "Rollback thu cong neu can: copy lai file tu $BackupDir ve data\diacritic\" -ForegroundColor Yellow
        exit 1
    }

    Write-Host "== XONG. Asset moi da thay the. Backup cu nam o $BackupDir ==" -ForegroundColor Green
    Write-Host "Luu y: restart backend de process moi nap asset vua build."
}
finally {
    Pop-Location
}
