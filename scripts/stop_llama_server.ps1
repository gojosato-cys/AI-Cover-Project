$connections = Get-NetTCPConnection -LocalPort 8080 -State Listen -ErrorAction SilentlyContinue
if (-not $connections) {
    Write-Host 'No llama.cpp server is listening on port 8080.'
    exit 0
}

$processIds = $connections | Select-Object -ExpandProperty OwningProcess -Unique
foreach ($processId in $processIds) {
    $process = Get-Process -Id $processId -ErrorAction SilentlyContinue
    if ($process -and $process.Path -like '*llama-server.exe') {
        Stop-Process -Id $processId -Force
        Write-Host "Stopped llama-server process $processId."
    } else {
        Write-Warning "Port 8080 is owned by PID $processId; it was not stopped automatically."
    }
}
