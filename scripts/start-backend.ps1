param([switch]$SkipBuild)
$ErrorActionPreference = 'Stop'
$workspace = Split-Path $PSScriptRoot -Parent
$pythonPath = Join-Path $workspace '.venv\Scripts\python.exe'
if (!(Test-Path -LiteralPath $pythonPath)) { throw '请先按 README 创建虚拟环境并安装开发依赖' }
$env:PYTHON_EXECUTABLE = $pythonPath
$envFile = Join-Path $workspace '.env'
if (!(Test-Path -LiteralPath $envFile)) { throw '请先运行 python scripts/init-env.py' }
Get-Content -LiteralPath $envFile -Encoding UTF8 | ForEach-Object {
    if ($_ -match '^([A-Za-z_][A-Za-z0-9_]*)=(.*)$') {
        [Environment]::SetEnvironmentVariable($matches[1], $matches[2], 'Process')
    }
}
Push-Location (Join-Path $workspace 'kaoyan-B')
try {
    if (!$SkipBuild) { & .\mvnw.cmd -B -ntp package; if ($LASTEXITCODE -ne 0) { throw '构建失败' } }
    & java -jar target/kaoyan-backend-1.0.0.jar
} finally { Pop-Location }
