param(
    [switch]$Install,
    [switch]$Seed,
    [int]$Port = 5000
)

$python = ".venv\Scripts\python.exe"
if (-not (Test-Path $python)) {
    $python = "python"
}

$args = @("run_local.py", "--host", "127.0.0.1", "--port", $Port)
if ($Install) { $args += "--install" }
if ($Seed) { $args += "--seed" }

& $python @args
