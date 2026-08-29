param(
    [Parameter(Mandatory = $true)][string]$WayfarerPath,
    [Parameter(Mandatory = $true)][string]$ConfigPath,
    [Parameter(Mandatory = $true)][string]$OutputDirectory,
    [string]$Python = "python",
    [string]$InstallationMode = "installed distribution"
)

$ErrorActionPreference = "Stop"
$expectedCommit = "679ddae9717bf78681a2cfbf794f687127b23b5d"
$target = (Resolve-Path -LiteralPath $WayfarerPath).Path
$config = (Resolve-Path -LiteralPath $ConfigPath).Path
$output = [IO.Path]::GetFullPath($OutputDirectory)
if ($output.StartsWith($target + [IO.Path]::DirectorySeparatorChar, [StringComparison]::OrdinalIgnoreCase)) {
    throw "OutputDirectory must be outside the disposable Wayfarer checkout."
}
$commit = (& git -C $target rev-parse HEAD).Trim()
if ($LASTEXITCODE -ne 0 -or $commit -ne $expectedCommit) {
    throw "Wayfarer must be checked out at $expectedCommit; found $commit."
}
$before = (& git -C $target status --porcelain=v1 --untracked-files=all) -join "`n"
New-Item -ItemType Directory -Force -Path $output | Out-Null

$base = Get-Content -LiteralPath $config -Raw | ConvertFrom-Json -AsHashtable
function New-Variant([string]$name, [hashtable]$enabled) {
    $copy = $base | ConvertTo-Json -Depth 100 | ConvertFrom-Json -AsHashtable
    foreach ($guard in @("loc", "callableSize", "nesting", "cyclomaticComplexity", "markdownDocumentSize", "markdownSectionSize")) {
        if (-not $copy.guards.ContainsKey($guard)) { $copy.guards[$guard] = @{} }
        $copy.guards[$guard].enabled = [bool]$enabled[$guard]
    }
    $path = Join-Path $output "$name.config.json"
    $copy | ConvertTo-Json -Depth 100 | Set-Content -LiteralPath $path -Encoding utf8
    return $path
}
$locOnly = New-Variant "loc-only" @{ loc=$true; callableSize=$false; nesting=$false; cyclomaticComplexity=$false; markdownDocumentSize=$false; markdownSectionSize=$false }
$syntaxOnly = New-Variant "syntax-only" @{ loc=$false; callableSize=$true; nesting=$true; cyclomaticComplexity=$true; markdownDocumentSize=$false; markdownSectionSize=$false }

$metadata = [ordered]@{
    recordedAtUtc = [DateTime]::UtcNow.ToString("o")
    sourceCommit = $commit
    configuration = $config
    configurationSha256 = (Get-FileHash -LiteralPath $config -Algorithm SHA256).Hash
    python = (& $Python --version 2>&1) -join " "
    codeGuard = (& $Python -m agent_code_guard.code_guard --version 2>&1) -join " "
    installationMode = $InstallationMode
    workingDirectory = $target
    samples = [ordered]@{}
}
function Measure-Variant([string]$name, [string]$variantConfig) {
    $samples = @()
    for ($sample = 1; $sample -le 3; $sample++) {
        $stdout = Join-Path $output "$name.sample-$sample.json"
        $stderr = Join-Path $output "$name.sample-$sample.stderr.txt"
        $watch = [Diagnostics.Stopwatch]::StartNew()
        $process = Start-Process -FilePath $Python -ArgumentList @(
            "-m", "agent_code_guard.code_guard", ".", "--config", $variantConfig, "--json", "--ci"
        ) -WorkingDirectory $target -Wait -PassThru -NoNewWindow -RedirectStandardOutput $stdout -RedirectStandardError $stderr
        $watch.Stop()
        $samples += [ordered]@{ sample=$sample; seconds=$watch.Elapsed.TotalSeconds; exitCode=$process.ExitCode; stdout=$stdout; stderr=$stderr }
    }
    $ordered = @($samples.seconds | Sort-Object)
    $metadata.samples[$name] = [ordered]@{ command="$Python -m agent_code_guard.code_guard . --config `"$variantConfig`" --json --ci"; runs=$samples; medianSeconds=$ordered[1] }
}
Measure-Variant "loc-only" $locOnly
Measure-Variant "syntax-only" $syntaxOnly
Measure-Variant "normal" $config

$profile = Join-Path $output "normal.cprofile"
$profileStdout = Join-Path $output "normal.profile.json"
$profileStderr = Join-Path $output "normal.profile.stderr.txt"
$profileProcess = Start-Process -FilePath $Python -ArgumentList @(
    "-m", "cProfile", "-o", $profile, "-m", "agent_code_guard.code_guard", ".", "--config", $config, "--json", "--ci"
) -WorkingDirectory $target -Wait -PassThru -NoNewWindow -RedirectStandardOutput $profileStdout -RedirectStandardError $profileStderr
$metadata.profile = [ordered]@{ command="$Python -m cProfile -o `"$profile`" -m agent_code_guard.code_guard . --config `"$config`" --json --ci"; exitCode=$profileProcess.ExitCode; output=$profile; stdout=$profileStdout; stderr=$profileStderr }

$after = (& git -C $target status --porcelain=v1 --untracked-files=all) -join "`n"
$metadata.targetStatusBefore = $before
$metadata.targetStatusAfter = $after
$metadata.normalAnalysisCreatedRepositoryMetadata = ($before -ne $after)
$metadata | ConvertTo-Json -Depth 20 | Set-Content -LiteralPath (Join-Path $output "benchmark-results.json") -Encoding utf8
if ($before -ne $after) { throw "Benchmark changed the target checkout; inspect benchmark-results.json." }
Write-Output (Join-Path $output "benchmark-results.json")
