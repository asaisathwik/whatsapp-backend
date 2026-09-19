# start-all.ps1
# Starts all WhatsApp AI SaaS services without Docker
# Run from d:\whatsapp-ai-saas\

Write-Host ""
Write-Host "======================================" -ForegroundColor White
Write-Host "  WhatsApp AI SaaS - Starting All" -ForegroundColor White
Write-Host "======================================" -ForegroundColor White
Write-Host ""

$ROOT = "d:\whatsapp-ai-saas"

# 1. WhatsApp Bridge (real QR codes)
Write-Host "[1/3] WhatsApp Bridge (port 8001)..." -NoNewline
$bridge = Start-Process -FilePath "node" `
    -ArgumentList "$ROOT\whatsapp-bridge\server.js" `
    -WorkingDirectory "$ROOT\whatsapp-bridge" `
    -PassThru -WindowStyle Minimized
Start-Sleep -Milliseconds 3000
try {
    Invoke-RestMethod "http://localhost:8001/health" -TimeoutSec 3 | Out-Null
    Write-Host " ✅ Running (PID $($bridge.Id))" -ForegroundColor Green
} catch {
    Write-Host " ⏳ Starting (give it 5s)" -ForegroundColor Yellow
}

# 2. FastAPI Backend
Write-Host "[2/3] FastAPI Backend   (port 8000)..." -NoNewline
$env:PYTHONPATH = "$ROOT\backend"
$backend = Start-Process -FilePath "$ROOT\backend\venv\Scripts\uvicorn.exe" `
    -ArgumentList "app.main:app", "--host", "127.0.0.1", "--port", "8000" `
    -WorkingDirectory "$ROOT\backend" `
    -PassThru -WindowStyle Minimized
Start-Sleep -Milliseconds 5000
try {
    Invoke-RestMethod "http://localhost:8000/health" -TimeoutSec 3 | Out-Null
    Write-Host " ✅ Running (PID $($backend.Id))" -ForegroundColor Green
} catch {
    Write-Host " ❌ Failed - check terminal" -ForegroundColor Red
}

# 3. Next.js Frontend
Write-Host "[3/3] Next.js Frontend  (port 3000)..." -NoNewline
$frontend = Start-Process -FilePath "cmd" `
    -ArgumentList "/c npm run dev" `
    -WorkingDirectory "$ROOT\frontend" `
    -PassThru -WindowStyle Minimized
Start-Sleep -Milliseconds 6000
try {
    Invoke-WebRequest "http://localhost:3000" -TimeoutSec 5 -UseBasicParsing | Out-Null
    Write-Host " ✅ Running (PID $($frontend.Id))" -ForegroundColor Green
} catch {
    Write-Host " ⏳ Still compiling..." -ForegroundColor Yellow
}

Write-Host ""
Write-Host "======================================" -ForegroundColor White
Write-Host "  All services launched!" -ForegroundColor Green
Write-Host "======================================" -ForegroundColor White
Write-Host ""
Write-Host "  Dashboard : http://localhost:3000" -ForegroundColor Cyan
Write-Host "  API Docs  : http://localhost:8000/docs" -ForegroundColor Cyan
Write-Host "  WA Bridge : http://localhost:8001/health" -ForegroundColor Cyan
Write-Host ""
Write-Host "  Go to http://localhost:3000/whatsapp" -ForegroundColor Yellow
Write-Host "  Click 'Connect Number' -> real QR appears in ~10 seconds" -ForegroundColor Yellow
Write-Host ""
