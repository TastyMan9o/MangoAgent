# run_app.ps1
# VideoAgent PowerShell 一键启动脚本 (带端口自清理最终版)

$backendPort = 8001

# --- 新增：端口占用检测与清理 ---
Write-Host "[VideoAgent] 正在检查端口 $backendPort 是否被占用..."
try {
    $process = Get-NetTCPConnection -LocalPort $backendPort -State Listen -ErrorAction Stop
    if ($process) {
        $pid = $process.OwningProcess
        Write-Host "[VideoAgent] 警告: 端口 $backendPort 正在被进程 PID $pid 占用。正在强制结束该进程..." -ForegroundColor Yellow
        Stop-Process -Id $pid -Force
        Write-Host "[VideoAgent] ✅ 进程 PID $pid 已成功结束。" -ForegroundColor Green
    }
} catch {
    # 如果Get-NetTCPConnection没有找到任何监听进程，会抛出错误，我们在这里捕获它即可
    Write-Host "[VideoAgent] ✅ 端口 $backendPort 可用。" -ForegroundColor Green
}
# ------------------------------------

Write-Host "[VideoAgent] 正在启动后端服务 (FastAPI / Uvicorn)..."
$backendCommand = "conda activate LangGraph; `$env:HTTPS_PROXY='http://127.0.0.1:7890'; python -u -m uvicorn main:app --reload --port $backendPort --log-level info"
Start-Process powershell -ArgumentList "-NoExit", "-Command", $backendCommand

Write-Host "[VideoAgent] 正在等待后端初始化 (5秒)..."
Start-Sleep -Seconds 5

Write-Host "[VideoAgent] 正在启动前端UI (Streamlit)..."
$frontendCommand = "conda activate LangGraph; `$env:NO_PROXY='127.0.0.1,localhost'; python -u -m streamlit run app.py"
Start-Process powershell -ArgumentList "-NoExit", "-Command", $frontendCommand

Write-Host "[VideoAgent] ✅ 所有服务已在新的 PowerShell 窗口中启动！"