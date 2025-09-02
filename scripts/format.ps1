# Format code using black and isort
$ErrorActionPreference = "Stop"

pip show black | Out-Null 2>$null
if ($LASTEXITCODE -ne 0) { pip install black isort flake8 mypy | Out-Null }

black .
isort .
flake8 . 