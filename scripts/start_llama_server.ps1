param(
    [string]$RuntimeRoot = 'D:\llama.cpp\b11093',
    [string]$ModelPath = 'D:\llama.cpp\models\Qwen2.5-7B-Instruct-Q4_K_M.gguf',
    [string]$BindHost = '127.0.0.1',
    [int]$Port = 8080,
    [int]$ContextSize = 4096,
    [int]$GpuLayers = 99
)

$server = Join-Path $RuntimeRoot 'llama-server.exe'
if (-not (Test-Path -LiteralPath $server)) {
    throw "llama-server.exe not found: $server"
}
if (-not (Test-Path -LiteralPath $ModelPath)) {
    throw "GGUF model not found: $ModelPath"
}

$logRoot = 'D:\llama.cpp\logs'
New-Item -ItemType Directory -Path $logRoot -Force | Out-Null

$existing = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
if ($existing) {
    throw "Port $Port is already in use. Stop the existing process before starting llama-server."
}

$arguments = @(
    '--model', $ModelPath,
    '--host', $BindHost,
    '--port', $Port,
    '--alias', 'RemLocal',
    '--n-gpu-layers', $GpuLayers,
    '--ctx-size', $ContextSize
)

Write-Host "Starting llama.cpp server with model: $ModelPath"
Start-Process `
    -FilePath $server `
    -ArgumentList $arguments `
    -WorkingDirectory $RuntimeRoot `
    -WindowStyle Hidden `
    -RedirectStandardOutput (Join-Path $logRoot 'llama-server.out.log') `
    -RedirectStandardError (Join-Path $logRoot 'llama-server.err.log') | Out-Null

Write-Host "llama.cpp server starting at http://$BindHost`:$Port"
