param(
  [switch]$NoInstall,
  [switch]$NoBuild
)

$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$frontend = Join-Path $root 'frontend'

if (-not $NoInstall) {
  Push-Location $frontend
  if (-not (Test-Path 'node_modules')) { npm install }
  Pop-Location
}

if (-not $NoBuild) {
  Push-Location $frontend
  npm run build
  if ($LASTEXITCODE -ne 0) { throw "前端构建失败，已中止启动" }
  Pop-Location
}

python (Join-Path $root 'main.py')
