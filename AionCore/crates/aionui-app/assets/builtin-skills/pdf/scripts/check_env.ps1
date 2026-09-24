param([string]$RuntimeRoot = $env:AIONUI_PDF_RUNTIME)
$ErrorActionPreference = 'SilentlyContinue'
if (-not $RuntimeRoot) { Write-Output 'AIONUI_PDF_RUNTIME is not set'; exit 1 }
$checks = @(
  @('python', (Join-Path $RuntimeRoot 'python.exe')),
  @('pdftoppm', (Join-Path (Join-Path $RuntimeRoot 'poppler') 'pdftoppm.exe')),
  @('pypdf', (Join-Path $RuntimeRoot 'Lib\site-packages\pypdf')),
  @('typing_extensions', (Join-Path $RuntimeRoot 'Lib\site-packages\typing_extensions.py'))
)
$failed = $false
foreach ($check in $checks) {
  $ok = Test-Path -LiteralPath $check[1]
  if ($ok) { $state = 'ok' } else { $state = 'missing'; $failed = $true }
  Write-Output ($check[0] + ': ' + $state + ' ' + $check[1])
}
if ($failed) { exit 1 }
Write-Output 'PDF runtime: ok (Poppler rendering; Tesseract optional)'
exit 0
