$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
$projectPython = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
$localPackages = Join-Path $PSScriptRoot '.deps'
if (Test-Path -LiteralPath $projectPython) {
    & $projectPython -m streamlit run app.py @args
} elseif (Test-Path -LiteralPath (Join-Path $localPackages 'streamlit')) {
    $previousPythonPath = $env:PYTHONPATH
    try {
        $env:PYTHONPATH = $localPackages
        & python -m streamlit run app.py @args
    } finally {
        $env:PYTHONPATH = $previousPythonPath
    }
} else {
    Write-Error 'Pasang requirements.txt ke .venv terlebih dahulu; lihat README.md.'
}
exit $LASTEXITCODE
