<#
.SYNOPSIS
    Chitragupt test harness — runs the full unit/mocked-integration test suite
    across all nine test domains and produces a structured findings report.

.DESCRIPTION
    Bootstraps and executes pytest for each domain in sequence, logging all
    observed events to a timestamped log file and writing a final markdown
    report that summarises pass/fail/skip counts, surfaces test findings
    (failures with context), and records which tests were excluded and why.

    EXCLUDED from this harness:
      - Tests marked @pytest.mark.integration  (require Docker Compose)
      - Tests marked @pytest.mark.quality      (require live LLM API keys)
      - Tests marked @pytest.mark.latency      (require warm Docker Compose + API keys)
      - Polyglot build tests / UAT / smoke tests (require all 3 services running)

    INCLUDED:
      - All tests marked @pytest.mark.fast
      - All unmarked unit tests

.PARAMETER Domains
    Comma-separated list of domain numbers to run (1..9). Default: all domains.
    Example: -Domains 1,2

.PARAMETER ServicePath
    Path to the ai-orchestration service directory.
    Default: services/ai-orchestration (relative to repo root).

.PARAMETER ReportDir
    Directory where the log file and final report are written.
    Default: test-reports (relative to repo root).

.PARAMETER Verbose
    Emit pytest -v output to the console as each domain runs.

.EXAMPLE
    # Run all domains from the repo root
    pwsh scripts/Invoke-TestHarness.ps1

    # Run only domains 1 and 2
    pwsh scripts/Invoke-TestHarness.ps1 -Domains 1,2

    # Run with verbose pytest output
    pwsh scripts/Invoke-TestHarness.ps1 -Verbose
#>

[CmdletBinding()]
param(
    [int[]]   $Domains    = @(1, 2, 3, 4, 5, 6, 7, 8, 9),
    [string]  $ServicePath = "services/ai-orchestration",
    [string]  $ReportDir   = "test-reports"
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

# ─────────────────────────────────────────────────────────────────────────────
# DOMAIN MAP
# Maps domain number → metadata used for discovery, labelling, and reporting.
# "TestFile"  : path relative to $ServicePath/tests/
# "Excluded"  : if set, reason the harness skips this domain entirely
# "ExcludeMarker" : pytest marker to exclude within a domain (used for integration
#                   stubs co-located in unit files)
# ─────────────────────────────────────────────────────────────────────────────

$DomainMap = [ordered]@{
    1 = @{
        Name        = "LLM Determinism"
        TestFile    = "unit/test_determinism.py"
        Excluded    = $null
        Description = "temperature=0, prompt determinism, parse-layer consistency"
    }
    2 = @{
        Name        = "Edge Cases"
        TestFile    = "unit/test_edge_cases.py"
        Excluded    = $null
        Description = "empty input, oversized message, malformed JSON, timeouts, binary files, REVISIT"
    }
    3 = @{
        Name        = "Quality of Response"
        TestFile    = "unit/test_quality.py"
        Excluded    = "NOT YET IMPLEMENTED — golden dataset tests scheduled for Week 3"
        Description = "precision/recall on golden utterances, PII leakage, question-mark invariant"
    }
    4 = @{
        Name        = "State Boundaries & Gating"
        TestFile    = "unit/test_state_boundaries.py"
        Excluded    = "NOT YET IMPLEMENTED — scheduled for Week 2"
        Description = "AC threshold N-1/N/waiver, regulated gate, REVISIT boundary, double-transition"
    }
    5 = @{
        Name        = "Code Correctness"
        TestFile    = "unit/test_code_correctness.py"
        Excluded    = "NOT YET IMPLEMENTED — scheduled for Week 1"
        Description = "chunker windows, BM25 weights, PII patterns, proto roundtrips"
    }
    6 = @{
        Name        = "Code Integration"
        TestFile    = "integration/test_code_integration.py"
        Excluded    = "EXCLUDED — requires Docker Compose (PostgreSQL + Redis + gRPC services)"
        Description = "gRPC wire tests, RLS cross-tenant isolation, DB roundtrips"
    }
    7 = @{
        Name        = "Latency"
        TestFile    = "integration/test_latency.py"
        Excluded    = "EXCLUDED — requires Docker Compose + real API keys (run pre-release)"
        Description = "p95 budgets: intent <800ms, first-token <5s, RAG <500ms"
    }
    8 = @{
        Name        = "Context Awareness"
        TestFile    = "unit/test_context_awareness.py"
        Excluded    = "NOT YET IMPLEMENTED — scheduled for Week 3"
        Description = "phase-scoped prompts, tenant-scoped retrieval, multi-turn continuity"
    }
    9 = @{
        Name        = "Budget & Commercial"
        TestFile    = "unit/test_budget.py"
        Excluded    = "NOT YET IMPLEMENTED — scheduled for Week 1"
        Description = "INCRBYFLOAT accuracy, Redis-down fallback, float precision at 200 turns"
    }
}


# ─────────────────────────────────────────────────────────────────────────────
# INTERNAL HELPERS
# ─────────────────────────────────────────────────────────────────────────────

function Write-Log {
    param([string]$Message, [string]$Level = "INFO")
    $ts = (Get-Date).ToString("yyyy-MM-dd HH:mm:ss.fff")
    $line = "[$ts] [$Level] $Message"
    Add-Content -Path $script:LogFile -Value $line
    if ($Level -eq "ERROR") {
        Write-Host $line -ForegroundColor Red
    } elseif ($Level -eq "WARN") {
        Write-Host $line -ForegroundColor Yellow
    } elseif ($Level -eq "PASS") {
        Write-Host $line -ForegroundColor Green
    } elseif ($Level -eq "FAIL") {
        Write-Host $line -ForegroundColor Red
    } else {
        Write-Host $line
    }
}

function Write-Section {
    param([string]$Title)
    $bar = "=" * 72
    Write-Log ""
    Write-Log $bar
    Write-Log "  $Title"
    Write-Log $bar
}

function Get-PytestRunner {
    <#
    .SYNOPSIS Returns the best available pytest invocation for the service directory.
    #>
    param([string]$ServiceAbsPath)

    if (Get-Command "uv" -ErrorAction SilentlyContinue) {
        Write-Log "Test runner: uv run pytest  (uv found)"
        return "uv", @("run", "pytest")
    }
    # Fall back to the Python in the service venv if it exists
    $venvPy = Join-Path $ServiceAbsPath ".venv/Scripts/python.exe"
    if (Test-Path $venvPy) {
        Write-Log "Test runner: $venvPy -m pytest  (venv found)"
        return $venvPy, @("-m", "pytest")
    }
    # Final fallback to system python
    if (Get-Command "python" -ErrorAction SilentlyContinue) {
        Write-Log "Test runner: python -m pytest  (system Python)"
        return "python", @("-m", "pytest")
    }
    throw "No suitable test runner found. Install 'uv' or ensure Python is on PATH."
}

function Invoke-DomainTests {
    <#
    .SYNOPSIS
        Runs pytest for a single domain test file.
        Returns a hashtable with: Passed, Failed, Skipped, Errors, Duration, XmlPath, RawOutput
    #>
    param(
        [int]    $DomainNum,
        [string] $DomainName,
        [string] $TestFilePath,   # absolute path to the test file
        [string] $ServiceAbsPath,
        [string] $XmlDir
    )

    $xmlPath = Join-Path $XmlDir "domain-$DomainNum.xml"
    $marker  = "fast or (not integration and not quality and not latency)"

    $exe, $baseArgs = Get-PytestRunner -ServiceAbsPath $ServiceAbsPath

    $pytestArgs = $baseArgs + @(
        $TestFilePath,
        "-v",
        "--tb=short",
        "--no-header",
        "-m", $marker,
        "--junit-xml=$xmlPath",
        "--override-ini=junit_family=xunit2"
    )

    Write-Log "CMD: $exe $($pytestArgs -join ' ')"

    $startTime = Get-Date

    # Run pytest, capture all output; do NOT throw on non-zero exit
    $output = & $exe @pytestArgs 2>&1 | Out-String
    $exitCode = $LASTEXITCODE

    $duration = [math]::Round(((Get-Date) - $startTime).TotalSeconds, 2)

    # Emit raw output to log
    foreach ($line in ($output -split "`n")) {
        if ($line.Trim() -ne "") {
            Add-Content -Path $script:LogFile -Value "    $line"
        }
    }

    # Parse JUnit XML for structured counts
    $passed = 0; $failed = 0; $skipped = 0; $errors = 0
    $failureDetails = @()

    if (Test-Path $xmlPath) {
        try {
            [xml]$xml = Get-Content $xmlPath -Raw
            $suite = $xml.testsuites.testsuite
            if ($null -eq $suite) { $suite = $xml.testsuite }

            if ($suite) {
                $total   = [int]($suite.tests   ?? 0)
                $failed  = [int]($suite.failures ?? 0)
                $errors  = [int]($suite.errors   ?? 0)
                $skipped = [int]($suite.skipped  ?? 0)
                $passed  = $total - $failed - $errors - $skipped

                # Collect failure details
                $cases = $suite.testcase
                if ($null -ne $cases) {
                    foreach ($tc in @($cases)) {
                        $failNode = $tc.failure ?? $tc.error
                        if ($null -ne $failNode) {
                            $failureDetails += [PSCustomObject]@{
                                TestName = $tc.name
                                ClassName = $tc.classname
                                Message  = ($failNode.message ?? "").Trim() -replace "`n", " " | Select-Object -First 1
                                Body     = ($failNode.'#text' ?? "").Trim()
                            }
                        }
                    }
                }
            }
        } catch {
            Write-Log "Failed to parse JUnit XML for domain $DomainNum: $_" "WARN"
        }
    } else {
        Write-Log "JUnit XML not found for domain $DomainNum — pytest may have failed to start" "WARN"
        # Try to infer counts from stdout
        if ($output -match "(\d+) passed") { $passed  = [int]$Matches[1] }
        if ($output -match "(\d+) failed") { $failed  = [int]$Matches[1] }
        if ($output -match "(\d+) error")  { $errors  = [int]$Matches[1] }
        if ($output -match "(\d+) skipped"){ $skipped = [int]$Matches[1] }
    }

    return [PSCustomObject]@{
        DomainNum      = $DomainNum
        DomainName     = $DomainName
        Passed         = $passed
        Failed         = $failed
        Errors         = $errors
        Skipped        = $skipped
        Total          = $passed + $failed + $errors + $skipped
        Duration       = $duration
        ExitCode       = $exitCode
        XmlPath        = $xmlPath
        FailureDetails = $failureDetails
        RawOutput      = $output
    }
}

function Format-StatusEmoji {
    param([PSCustomObject]$Result)
    if ($Result.Failed -gt 0 -or $Result.Errors -gt 0) { return "FAIL" }
    if ($Result.Passed -eq 0 -and $Result.Skipped -gt 0) { return "SKIP" }
    if ($Result.Passed -gt 0) { return "PASS" }
    return "????"
}

function New-FindingsReport {
    <#
    .SYNOPSIS Generates the final markdown findings report.
    #>
    param(
        [PSCustomObject[]] $Results,
        [hashtable]        $ExcludedDomains,
        [string]           $RunTimestamp,
        [float]            $TotalDuration
    )

    $totalTests  = ($Results | Measure-Object -Property Total   -Sum).Sum
    $totalPassed = ($Results | Measure-Object -Property Passed  -Sum).Sum
    $totalFailed = ($Results | Measure-Object -Property Failed  -Sum).Sum
    $totalErrors = ($Results | Measure-Object -Property Errors  -Sum).Sum
    $totalSkipped= ($Results | Measure-Object -Property Skipped -Sum).Sum
    $passRate    = if ($totalTests -gt 0) { [math]::Round(($totalPassed / $totalTests) * 100, 1) } else { 0 }

    $anyFailed = $totalFailed -gt 0 -or $totalErrors -gt 0
    $overallStatus = if ($anyFailed) { "FINDINGS DETECTED" } else { "ALL TESTS PASSED" }

    $sb = [System.Text.StringBuilder]::new()

    $null = $sb.AppendLine("# Chitragupt Test Harness — Findings Report")
    $null = $sb.AppendLine("")
    $null = $sb.AppendLine("**Run timestamp:** $RunTimestamp  ")
    $null = $sb.AppendLine("**Total duration:** $($TotalDuration)s  ")
    $null = $sb.AppendLine("**Overall status:** ``$overallStatus``  ")
    $null = $sb.AppendLine("**Mode:** fast (unit + mocked-integration; no API keys or Docker required)  ")
    $null = $sb.AppendLine("")
    $null = $sb.AppendLine("---")
    $null = $sb.AppendLine("")

    # ── Executive summary ─────────────────────────────────────────────────────
    $null = $sb.AppendLine("## Executive Summary")
    $null = $sb.AppendLine("")
    $null = $sb.AppendLine("| Metric | Count |")
    $null = $sb.AppendLine("|---|---|")
    $null = $sb.AppendLine("| Total tests run | $totalTests |")
    $null = $sb.AppendLine("| Passed | $totalPassed |")
    $null = $sb.AppendLine("| Failed | $totalFailed |")
    $null = $sb.AppendLine("| Errors | $totalErrors |")
    $null = $sb.AppendLine("| Skipped (integration stubs) | $totalSkipped |")
    $null = $sb.AppendLine("| Pass rate | $passRate% |")
    $null = $sb.AppendLine("")

    if ($anyFailed) {
        $null = $sb.AppendLine("> **Action required:** $($totalFailed + $totalErrors) test(s) failed.")
        $null = $sb.AppendLine("> Each failure section below identifies the root cause and the fix location.")
    } else {
        $null = $sb.AppendLine("> All executed tests passed. Domains not yet implemented are noted in the Excluded section.")
    }

    $null = $sb.AppendLine("")
    $null = $sb.AppendLine("---")
    $null = $sb.AppendLine("")

    # ── Domain results table ──────────────────────────────────────────────────
    $null = $sb.AppendLine("## Domain Results")
    $null = $sb.AppendLine("")
    $null = $sb.AppendLine("| Domain | Name | Tests | Pass | Fail | Skip | Time | Status |")
    $null = $sb.AppendLine("|---|---|---|---|---|---|---|---|")

    foreach ($r in $Results) {
        $status = Format-StatusEmoji -Result $r
        $statusMd = switch ($status) {
            "PASS" { "✅ PASS" }
            "FAIL" { "❌ FAIL" }
            "SKIP" { "⏭ SKIP" }
            default { "❓ ????" }
        }
        $null = $sb.AppendLine("| $($r.DomainNum) | $($r.DomainName) | $($r.Total) | $($r.Passed) | $($r.Failed + $r.Errors) | $($r.Skipped) | $($r.Duration)s | $statusMd |")
    }

    foreach ($entry in $ExcludedDomains.GetEnumerator() | Sort-Object Key) {
        $dom = $DomainMap[$entry.Key]
        $null = $sb.AppendLine("| $($entry.Key) | $($dom.Name) | — | — | — | — | — | ⛔ EXCLUDED |")
    }

    $null = $sb.AppendLine("")
    $null = $sb.AppendLine("---")
    $null = $sb.AppendLine("")

    # ── Failure details ───────────────────────────────────────────────────────
    $failedResults = $Results | Where-Object { $_.Failed -gt 0 -or $_.Errors -gt 0 }

    if ($failedResults) {
        $null = $sb.AppendLine("## Failure Details & Findings")
        $null = $sb.AppendLine("")
        $null = $sb.AppendLine("Each failure below is a **finding** — a gap between the spec and the current implementation.")
        $null = $sb.AppendLine("The test docstring identifies the root cause and the fix location.")
        $null = $sb.AppendLine("")

        foreach ($r in $failedResults) {
            $null = $sb.AppendLine("### Domain $($r.DomainNum) — $($r.DomainName)")
            $null = $sb.AppendLine("")

            if ($r.FailureDetails.Count -eq 0) {
                $null = $sb.AppendLine("_Failures detected but JUnit XML details unavailable. See log file._")
                $null = $sb.AppendLine("")
                continue
            }

            foreach ($f in $r.FailureDetails) {
                $null = $sb.AppendLine("#### ``$($f.TestName)``")
                $null = $sb.AppendLine("")
                if ($f.Message -ne "") {
                    # Extract FINDING: line from the assertion message if present
                    $findingLine = ($f.Body -split "`n" | Where-Object { $_ -match "FINDING:" } | Select-Object -First 1)
                    $fixLine     = ($f.Body -split "`n" | Where-Object { $_ -match "FIX:" }     | Select-Object -First 1)

                    if ($findingLine) {
                        $null = $sb.AppendLine("**Finding:** $($findingLine.Trim() -replace 'FINDING:\s*', '')")
                        $null = $sb.AppendLine("")
                    }
                    if ($fixLine) {
                        $null = $sb.AppendLine("**Fix:** $($fixLine.Trim() -replace 'FIX:\s*', '')")
                        $null = $sb.AppendLine("")
                    }
                    if (-not $findingLine) {
                        # Fall back to assertion message
                        $null = $sb.AppendLine("**Assertion:** ``$($f.Message -replace '`', "'" | Select-String -Pattern '.{0,200}' | Select-Object -First 1)``")
                        $null = $sb.AppendLine("")
                    }
                }
            }
        }

        $null = $sb.AppendLine("---")
        $null = $sb.AppendLine("")
    }

    # ── Excluded domains ──────────────────────────────────────────────────────
    $null = $sb.AppendLine("## Excluded Tests")
    $null = $sb.AppendLine("")
    $null = $sb.AppendLine("The following domains were not run by this harness. Exclusion reasons are noted.")
    $null = $sb.AppendLine("")
    $null = $sb.AppendLine("| Domain | Name | Reason |")
    $null = $sb.AppendLine("|---|---|---|")

    foreach ($entry in $ExcludedDomains.GetEnumerator() | Sort-Object Key) {
        $dom = $DomainMap[$entry.Key]
        $null = $sb.AppendLine("| $($entry.Key) | $($dom.Name) | $($entry.Value) |")
    }

    $null = $sb.AppendLine("")
    $null = $sb.AppendLine("**Also excluded from all runs (out of harness scope):**")
    $null = $sb.AppendLine("- Polyglot build tests (require all 3 services: Rust + Python + Go)")
    $null = $sb.AppendLine("- UAT (user acceptance testing)")
    $null = $sb.AppendLine("- Smoke tests and E2E tests (require full Docker Compose stack)")
    $null = $sb.AppendLine("")
    $null = $sb.AppendLine("To run integration tests: ``docker compose --profile test up && pytest -m integration``")
    $null = $sb.AppendLine("To run quality tests:     ``ANTHROPIC_API_KEY=... pytest -m quality``")
    $null = $sb.AppendLine("To run latency tests:     ``ANTHROPIC_API_KEY=... VOYAGE_API_KEY=... pytest -m latency``")
    $null = $sb.AppendLine("")
    $null = $sb.AppendLine("---")
    $null = $sb.AppendLine("")

    # ── Next steps ────────────────────────────────────────────────────────────
    $null = $sb.AppendLine("## Next Steps")
    $null = $sb.AppendLine("")

    if ($anyFailed) {
        $null = $sb.AppendLine("### Fix required before sprint closure")
        $null = $sb.AppendLine("")
        foreach ($r in $failedResults) {
            foreach ($f in $r.FailureDetails) {
                $fixLine = ($f.Body -split "`n" | Where-Object { $_ -match "FIX:" } | Select-Object -First 1)
                if ($fixLine) {
                    $null = $sb.AppendLine("- [ ] **Domain $($r.DomainNum)** ``$($f.TestName)``: $($fixLine.Trim() -replace 'FIX:\s*', '')")
                } else {
                    $null = $sb.AppendLine("- [ ] **Domain $($r.DomainNum)** ``$($f.TestName)``: Investigate failure in log file.")
                }
            }
        }
        $null = $sb.AppendLine("")
    }

    $null = $sb.AppendLine("### Implement remaining domains")
    $null = $sb.AppendLine("")
    foreach ($entry in $ExcludedDomains.GetEnumerator() | Sort-Object Key) {
        $dom = $DomainMap[$entry.Key]
        if ($entry.Value -match "NOT YET IMPLEMENTED") {
            $null = $sb.AppendLine("- [ ] Domain $($entry.Key) — $($dom.Name): $($dom.Description)")
        }
    }
    $null = $sb.AppendLine("")
    $null = $sb.AppendLine("---")
    $null = $sb.AppendLine("")
    $null = $sb.AppendLine("> Chitragupt · Test Harness Report · Generated $RunTimestamp")

    return $sb.ToString()
}


# ─────────────────────────────────────────────────────────────────────────────
# MAIN EXECUTION
# ─────────────────────────────────────────────────────────────────────────────

# Resolve absolute paths
$RepoRoot    = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$ServiceAbs  = Join-Path $RepoRoot $ServicePath
$ReportAbs   = Join-Path $RepoRoot $ReportDir
$RunTs       = (Get-Date).ToString("yyyy-MM-dd_HH-mm-ss")
$RunTsHuman  = (Get-Date).ToString("yyyy-MM-dd HH:mm:ss")

# Create output directories
New-Item -ItemType Directory -Force -Path $ReportAbs | Out-Null
$XmlDir = Join-Path $ReportAbs "junit-$RunTs"
New-Item -ItemType Directory -Force -Path $XmlDir | Out-Null

$script:LogFile    = Join-Path $ReportAbs "harness-$RunTs.log"
$ReportFile        = Join-Path $ReportAbs "findings-$RunTs.md"
$LatestReportLink  = Join-Path $ReportAbs "findings-latest.md"

# Validate service directory
if (-not (Test-Path $ServiceAbs)) {
    throw "Service directory not found: $ServiceAbs"
}
if (-not (Test-Path (Join-Path $ServiceAbs "pyproject.toml"))) {
    throw "Not a Python service directory (no pyproject.toml): $ServiceAbs"
}

# ── Banner ────────────────────────────────────────────────────────────────────
Write-Section "CHITRAGUPT TEST HARNESS"
Write-Log "Run timestamp : $RunTsHuman"
Write-Log "Repository    : $RepoRoot"
Write-Log "Service       : $ServiceAbs"
Write-Log "Report dir    : $ReportAbs"
Write-Log "Log file      : $($script:LogFile)"
Write-Log "Domains       : $($Domains -join ', ')"
Write-Log "Mode          : fast (unit + mocked-integration; excludes integration/quality/latency)"

# ── Pre-flight ────────────────────────────────────────────────────────────────
Write-Section "PRE-FLIGHT CHECKS"

# Verify service tests directory
$TestsDir = Join-Path $ServiceAbs "tests"
if (-not (Test-Path $TestsDir)) {
    Write-Log "Tests directory not found: $TestsDir" "ERROR"
    throw "Tests directory missing. Run from repo root."
}
Write-Log "Tests directory: $TestsDir  [OK]"

# Verify test runner availability
try {
    $null = Get-PytestRunner -ServiceAbsPath $ServiceAbs
    Write-Log "Test runner detection: [OK]"
} catch {
    Write-Log "Test runner not found: $_" "ERROR"
    throw
}

# Check for conftest.py
if (-not (Test-Path (Join-Path $TestsDir "conftest.py"))) {
    Write-Log "WARNING: tests/conftest.py not found — fixtures may be missing" "WARN"
} else {
    Write-Log "conftest.py: [OK]"
}

# ── Domain execution loop ─────────────────────────────────────────────────────
Write-Section "RUNNING DOMAINS"

$Results         = [System.Collections.Generic.List[PSCustomObject]]::new()
$ExcludedDomains = @{}
$HarnessStart    = Get-Date

foreach ($domNum in ($Domains | Sort-Object)) {
    if (-not $DomainMap.Contains($domNum)) {
        Write-Log "Domain $domNum is not defined in DomainMap — skipping" "WARN"
        continue
    }

    $dom = $DomainMap[$domNum]
    $testFileRel = $dom.TestFile
    $testFileAbs = Join-Path $TestsDir $testFileRel

    Write-Log ""
    Write-Log "── Domain $domNum: $($dom.Name) ──────────────────────────────"

    # Check exclusion
    if ($null -ne $dom.Excluded) {
        Write-Log "EXCLUDED: $($dom.Excluded)" "WARN"
        $ExcludedDomains[$domNum] = $dom.Excluded
        continue
    }

    # Check test file exists
    if (-not (Test-Path $testFileAbs)) {
        $reason = "NOT YET IMPLEMENTED — test file not found: tests/$testFileRel"
        Write-Log $reason "WARN"
        $ExcludedDomains[$domNum] = $reason
        continue
    }

    Write-Log "Test file: tests/$testFileRel  [found]"
    Write-Log "Description: $($dom.Description)"

    # Run the domain
    try {
        $result = Invoke-DomainTests `
            -DomainNum      $domNum `
            -DomainName     $dom.Name `
            -TestFilePath   $testFileAbs `
            -ServiceAbsPath $ServiceAbs `
            -XmlDir         $XmlDir

        $Results.Add($result)

        $status = Format-StatusEmoji -Result $result
        $summary = "Domain $domNum: $($result.Passed) passed, $($result.Failed + $result.Errors) failed, $($result.Skipped) skipped  [$($result.Duration)s]"

        if ($status -eq "PASS") {
            Write-Log $summary "PASS"
        } elseif ($status -eq "FAIL") {
            Write-Log $summary "FAIL"
            foreach ($f in $result.FailureDetails) {
                Write-Log "  FAILING: $($f.TestName)" "FAIL"
                $findingLine = ($f.Body -split "`n" | Where-Object { $_ -match "FINDING:" } | Select-Object -First 1)
                if ($findingLine) {
                    Write-Log "    $($findingLine.Trim())" "FAIL"
                }
            }
        } else {
            Write-Log $summary
        }

    } catch {
        Write-Log "Domain $domNum aborted with exception: $_" "ERROR"
        $Results.Add([PSCustomObject]@{
            DomainNum      = $domNum
            DomainName     = $dom.Name
            Passed         = 0
            Failed         = 1
            Errors         = 1
            Skipped        = 0
            Total          = 1
            Duration       = 0
            ExitCode       = -1
            XmlPath        = ""
            FailureDetails = @([PSCustomObject]@{
                TestName  = "(harness error)"
                ClassName = ""
                Message   = $_.ToString()
                Body      = $_.ToString()
            })
            RawOutput      = ""
        })
    }
}

$HarnessDuration = [math]::Round(((Get-Date) - $HarnessStart).TotalSeconds, 2)

# ── Final report ──────────────────────────────────────────────────────────────
Write-Section "GENERATING FINDINGS REPORT"

$reportContent = New-FindingsReport `
    -Results         $Results `
    -ExcludedDomains $ExcludedDomains `
    -RunTimestamp    $RunTsHuman `
    -TotalDuration   $HarnessDuration

Set-Content -Path $ReportFile        -Value $reportContent -Encoding UTF8
Set-Content -Path $LatestReportLink  -Value $reportContent -Encoding UTF8

Write-Log "Report written: $ReportFile"
Write-Log "Latest report:  $LatestReportLink"

# ── Final console summary ─────────────────────────────────────────────────────
Write-Section "HARNESS COMPLETE"

$totalPassed = ($Results | Measure-Object -Property Passed  -Sum).Sum
$totalFailed = ($Results | Measure-Object -Property Failed  -Sum).Sum
$totalErrors = ($Results | Measure-Object -Property Errors  -Sum).Sum
$totalTests  = ($Results | Measure-Object -Property Total   -Sum).Sum
$excluded    = $ExcludedDomains.Count

Write-Log "Total tests run : $totalTests"
Write-Log "Passed          : $totalPassed"
Write-Log "Failed + Errors : $($totalFailed + $totalErrors)"
Write-Log "Excluded domains: $excluded"
Write-Log "Total duration  : $($HarnessDuration)s"
Write-Log ""

if ($totalFailed -gt 0 -or $totalErrors -gt 0) {
    Write-Log "STATUS: FINDINGS DETECTED — $($totalFailed + $totalErrors) test(s) require attention." "FAIL"
    Write-Log "See: $ReportFile" "FAIL"
    exit 1
} else {
    Write-Log "STATUS: ALL EXECUTED TESTS PASSED" "PASS"
    Write-Log "See: $ReportFile"
    exit 0
}
