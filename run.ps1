param(
  [switch]$NoInstall
)

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$frontend = Join-Path $root 'frontend'

if (-not $NoInstall) {
  Push-Location $frontend
  if (-not (Test-Path 'node_modules')) {
    npm install
  }
  npm run build
  Pop-Location
}

python (Join-Path $root 'main.py')
