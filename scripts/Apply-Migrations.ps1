# Apply-Migrations.ps1
# Applies all numbered SQL migrations in services/ai-orchestration/migrations/ in order.
# Uses the local PostgreSQL installation at C:\Program Files\PostgreSQL\18\bin\psql.exe.
# Reads connection details from .env in the repo root.
# Usage: .\scripts\Apply-Migrations.ps1 [-Verbose] [-DryRun]

param(
    [switch] $DryRun,
    [string] $MigrationsDir = "services\ai-orchestration\migrations",
    [string] $PsqlExe       = "C:\Program Files\PostgreSQL\18\bin\psql.exe"
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

# ── Load .env ─────────────────────────────────────────────────────────────────
$envFile = Join-Path $PSScriptRoot ".." ".env"
$envFile = [System.IO.Path]::GetFullPath($envFile)

if (-not (Test-Path $envFile)) {
    Write-Error ".env not found at $envFile — copy .example.env and fill in credentials"
    exit 1
}

$env:PGPASSWORD = ""
foreach ($line in Get-Content $envFile) {
    $line = $line.Trim()
    if ($line -match '^#' -or $line -eq '' -or $line -notmatch '=') { continue }
    $parts = $line -split '=', 2
    $key   = $parts[0].Trim()
    $value = $parts[1].Trim().Trim('"').Trim("'")
    Set-Item -Path "env:$key" -Value $value -ErrorAction SilentlyContinue
}

$pg_host = $env:POSTGRES_HOST ?? "localhost"
$pg_port = $env:POSTGRES_PORT ?? "5432"
$pg_db   = $env:POSTGRES_DB   ?? "chitragupt"
$pg_user = $env:POSTGRES_USER  ?? "postgres"
$pg_pw   = $env:POSTGRES_PASSWORD ?? "root"

$env:PGPASSWORD = $pg_pw

# ── Verify psql ───────────────────────────────────────────────────────────────
if (-not (Test-Path $PsqlExe)) {
    # Try PostgreSQL 17 fallback
    $PsqlExe = "C:\Program Files\PostgreSQL\17\bin\psql.exe"
    if (-not (Test-Path $PsqlExe)) {
        Write-Error "psql.exe not found — adjust -PsqlExe parameter"
        exit 1
    }
}
Write-Host "Using psql: $PsqlExe" -ForegroundColor Cyan

# ── Ensure database exists ────────────────────────────────────────────────────
Write-Host "Ensuring database '$pg_db' exists..." -ForegroundColor Cyan
$dbExists = & $PsqlExe -h $pg_host -p $pg_port -U $pg_user -d postgres -tAc `
    "SELECT 1 FROM pg_database WHERE datname='$pg_db'" 2>&1
if ($dbExists -notmatch "1") {
    if ($DryRun) {
        Write-Host "[DRY RUN] Would create database: $pg_db" -ForegroundColor Yellow
    } else {
        & $PsqlExe -h $pg_host -p $pg_port -U $pg_user -d postgres -c `
            "CREATE DATABASE $pg_db;" 2>&1 | Write-Host
        Write-Host "Database '$pg_db' created." -ForegroundColor Green
    }
} else {
    Write-Host "Database '$pg_db' already exists." -ForegroundColor DarkGray
}

# ── Create migration tracking table ──────────────────────────────────────────
if (-not $DryRun) {
    & $PsqlExe -h $pg_host -p $pg_port -U $pg_user -d $pg_db -c @"
CREATE TABLE IF NOT EXISTS _migrations (
    filename    TEXT PRIMARY KEY,
    applied_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
"@ 2>&1 | Out-Null
}

# ── Apply migrations ──────────────────────────────────────────────────────────
$migrDir = Join-Path $PSScriptRoot ".." $MigrationsDir
$migrDir = [System.IO.Path]::GetFullPath($migrDir)
$files   = Get-ChildItem -Path $migrDir -Filter "*.sql" | Sort-Object Name

if ($files.Count -eq 0) {
    Write-Host "No migration files found in $migrDir" -ForegroundColor Yellow
    exit 0
}

$applied  = 0
$skipped  = 0
$failures = 0

foreach ($f in $files) {
    # Check if already applied
    if (-not $DryRun) {
        $already = & $PsqlExe -h $pg_host -p $pg_port -U $pg_user -d $pg_db -tAc `
            "SELECT 1 FROM _migrations WHERE filename='$($f.Name)'" 2>&1
        if ($already -match "1") {
            Write-Host "  SKIP  $($f.Name)" -ForegroundColor DarkGray
            $skipped++
            continue
        }
    }

    if ($DryRun) {
        Write-Host "  [DRY]  $($f.Name)" -ForegroundColor Yellow
        continue
    }

    Write-Host "  APPLY  $($f.Name) ..." -ForegroundColor Cyan
    $output = & $PsqlExe -h $pg_host -p $pg_port -U $pg_user -d $pg_db `
        --single-transaction -v ON_ERROR_STOP=1 -f $f.FullName 2>&1

    if ($LASTEXITCODE -ne 0) {
        Write-Host "  FAIL   $($f.Name)" -ForegroundColor Red
        Write-Host $output -ForegroundColor Red
        $failures++
        continue
    }

    # Record as applied
    & $PsqlExe -h $pg_host -p $pg_port -U $pg_user -d $pg_db -c `
        "INSERT INTO _migrations(filename) VALUES ('$($f.Name)') ON CONFLICT DO NOTHING;" 2>&1 | Out-Null

    Write-Host "  DONE   $($f.Name)" -ForegroundColor Green
    $applied++
}

Write-Host ""
Write-Host "Migration summary: $applied applied, $skipped skipped, $failures failed" `
    -ForegroundColor $(if ($failures -gt 0) { "Red" } else { "Green" })

exit $(if ($failures -gt 0) { 1 } else { 0 })
