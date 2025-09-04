# run_app.ps1 (v15 - Starts Chrome DevTools + Backend + Frontend, and opens UI in that Chrome)
# This script starts a DevTools-enabled Chrome (if not running), then backend & frontend.

param(
  [string]$CondaEnv      = "LangGraph",
  [int]$BackendPort      = 8001,
  [int]$FrontendPort     = 8501,
  [int]$DevtoolsPort     = 9222,
  [string]$ProxyAddress  = "http://127.0.0.1:7890",
  # 可选：如果你想一并打开 Flow 页面，把链接放这里；留空则只打开本地前端
  [string]$FlowUrl       = "https://labs.google/flow/about"
)

# Ensure console uses UTF-8 to avoid mojibake in Chinese output
try { chcp 65001 | Out-Null } catch {}
try { $OutputEncoding = [System.Text.UTF8Encoding]::new() } catch {}
try { [Console]::OutputEncoding = [System.Text.UTF8Encoding]::new() } catch {}

Write-Host "[Launcher] Starting DevTools Chrome + FastAPI + Streamlit..." -ForegroundColor Cyan

# ---------- helper: find chrome ----------
function Get-ChromePath {
  $candidates = @(
    "$env:ProgramFiles\Google\Chrome\Application\chrome.exe",
    "${env:ProgramFiles(x86)}\Google\Chrome\Application\chrome.exe",
    "$env:LOCALAPPDATA\Google\Chrome\Application\chrome.exe"
  )
  foreach ($p in $candidates) { if (Test-Path $p) { return $p } }
  return $null
}

# ---------- helper: test DevTools port ----------
function Test-DevToolsPort([int]$port) {
  try {
    $resp = Invoke-WebRequest -Uri "http://127.0.0.1:$port/json/version" -TimeoutSec 1 -UseBasicParsing
    return ($resp.StatusCode -eq 200)
  } catch { return $false }
}

# ---------- Step 0: Ensure Chrome with remote debugging is running ----------
$ChromePath = Get-ChromePath
if (-not $ChromePath) {
  Write-Host "[Launcher] ERROR: Chrome not found. Please install Chrome." -ForegroundColor Red
  exit 1
}

$ChromeProfile = "$env:USERPROFILE\chrome-remote-profile"
if (-not (Test-Path $ChromeProfile)) { New-Item -ItemType Directory -Force -Path $ChromeProfile | Out-Null }

if (-not (Test-DevToolsPort -port $DevtoolsPort)) {
  Write-Host "[Launcher] Step 0: Starting Chrome with DevTools port :$DevtoolsPort ..." -ForegroundColor Yellow
  # 重要：使用独立的 user-data-dir，避免已运行的 Chrome 抢占单例导致调试端口失效
  $args = @(
    "--remote-debugging-port=$DevtoolsPort",
    "--user-data-dir=""$ChromeProfile""",
    "--new-window",
    "--start-maximized",
    "--disable-features=Translate",
    "--lang=zh-CN",
    "about:blank"
  )
  Start-Process -FilePath $ChromePath -ArgumentList $args | Out-Null
  Start-Sleep -Seconds 1.0
  if (Test-DevToolsPort -port $DevtoolsPort) {
    Write-Host "[Launcher] OK: Chrome listening at 127.0.0.1:$DevtoolsPort" -ForegroundColor Green
  } else {
    Write-Host "[Launcher] WARN: Chrome DevTools port not reachable yet (will continue)." -ForegroundColor DarkYellow
  }
} else {
  Write-Host "[Launcher] OK: Detected existing Chrome DevTools at :$DevtoolsPort" -ForegroundColor Green
}

# ---------- Step 1: Clean old service ports ----------
Write-Host "[Launcher] Step 1/3: Cleaning ports $BackendPort / $FrontendPort ..." -ForegroundColor DarkYellow
try {
  $be = Get-NetTCPConnection -LocalPort $BackendPort -State Listen -ErrorAction Stop
  if ($be) { ($be | Select-Object -ExpandProperty OwningProcess -Unique) | ForEach-Object { Stop-Process -Id $_ -Force } }
} catch {}
try {
  $fe = Get-NetTCPConnection -LocalPort $FrontendPort -State Listen -ErrorAction Stop
  if ($fe) { ($fe | Select-Object -ExpandProperty OwningProcess -Unique) | ForEach-Object { Stop-Process -Id $_ -Force } }
} catch {}

# ---------- Step 2: Start Backend ----------
Write-Host "[Launcher] Step 2/3: Starting Backend (FastAPI on :$BackendPort)..." -ForegroundColor Cyan
$backendCommand = "conda activate $CondaEnv; chcp 65001; `$env:PYTHONIOENCODING='utf-8'; `$env:HTTP_PROXY='$ProxyAddress'; `$env:HTTPS_PROXY='$ProxyAddress'; python -u -m uvicorn main:app --reload --port $BackendPort --log-level info"
Start-Process powershell -ArgumentList "-NoExit","-Command",$backendCommand | Out-Null
Write-Host "[Launcher] Backend launching..." -ForegroundColor Gray
Start-Sleep -Seconds 4

# ---------- Step 3: Start Frontend ----------
Write-Host "[Launcher] Step 3/3: Starting Frontend (Streamlit on :$FrontendPort)..." -ForegroundColor Cyan
$frontendCommand = "conda activate $CondaEnv; chcp 65001; `$env:PYTHONIOENCODING='utf-8'; `$env:NO_PROXY='127.0.0.1,localhost'; python -u -m streamlit run app.py --server.port $FrontendPort --server.headless true"
Start-Process powershell -ArgumentList "-NoExit","-Command",$frontendCommand | Out-Null
Write-Host "[Launcher] Frontend launching..." -ForegroundColor Gray
Start-Sleep -Seconds 2

# ---------- Open UI tabs in the SAME DevTools Chrome ----------
Write-Host "[Launcher] Opening UI in DevTools Chrome..." -ForegroundColor Cyan
$openArgs = @(
  "--user-data-dir=""$ChromeProfile""",  # 指向同一实例，从而保证仍在带调试端口的 Chrome 里
  "http://localhost:$FrontendPort"
)
if ($FlowUrl -and $FlowUrl.Trim().Length -gt 0) { $openArgs += $FlowUrl.Trim() }
Start-Process -FilePath $ChromePath -ArgumentList $openArgs | Out-Null

Write-Host ""
Write-Host "--- All Services Launched! ---" -ForegroundColor Magenta
