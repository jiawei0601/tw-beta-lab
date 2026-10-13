$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot
$runtime = (Get-Command python -ErrorAction Stop).Source
Write-Host '台股 Beta 研究室：http://127.0.0.1:8765；Ctrl+C 停止。'
& $runtime server.py --open-browser
