[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$Version,
    [switch]$SkipTests,
    [switch]$SkipVenv
)

$ErrorActionPreference = "Stop"

$BuildDir = $PSScriptRoot
$RepoDir = Split-Path -Parent $BuildDir
$AppDir = Join-Path $RepoDir "Spendly"
$PathsFile = Join-Path $AppDir "paths.py"
$BuildScript = Join-Path $BuildDir "build.ps1"
$DistDir = Join-Path $RepoDir "dist"
$ChangelogFile = Join-Path $RepoDir "CHANGELOG.md"
$VenvDir = Join-Path $RepoDir ".venv"
$VenvPython = Join-Path $VenvDir "Scripts\python.exe"
$Utf8NoBom = New-Object System.Text.UTF8Encoding -ArgumentList $false

function Write-Step([string]$Message) {
    Write-Host "==> $Message" -ForegroundColor Cyan
}

if ($Version -notmatch '^\d+\.\d+\.\d+$') {
    throw "Version must use MAJOR.MINOR.PATCH, for example 1.1.0."
}

$VersionSource = [IO.File]::ReadAllText($PathsFile)
$CurrentMatch = [regex]::Match($VersionSource, '(?m)^APP_VERSION\s*=\s*"([0-9]+\.[0-9]+\.[0-9]+)"')
if (-not $CurrentMatch.Success) {
    throw "APP_VERSION was not found in $PathsFile."
}
$CurrentVersion = $CurrentMatch.Groups[1].Value
if ([version]$Version -lt [version]$CurrentVersion) {
    throw "Version $Version must not be lower than the current version $CurrentVersion."
}
$VersionChanged = $CurrentVersion -ne $Version

$Git = Get-Command git -ErrorAction SilentlyContinue
if (-not $Git) {
    throw "git was not found."
}
$Gh = Get-Command gh -ErrorAction SilentlyContinue
if (-not $Gh) {
    throw "GitHub CLI (gh) was not found. Install it from https://cli.github.com and run gh auth login."
}
& $Gh.Source auth status 2>&1 | Out-Null
if ($LASTEXITCODE -ne 0) {
    throw "GitHub CLI is not authenticated. Run gh auth login."
}

$Iscc = $null
$IsccCommand = Get-Command iscc -ErrorAction SilentlyContinue
if ($IsccCommand) {
    $Iscc = $IsccCommand.Source
} else {
    $Candidates = @()
    if ($env:LOCALAPPDATA) {
        $Candidates += (Join-Path $env:LOCALAPPDATA "Programs\Inno Setup 6\ISCC.exe")
    }
    if (${env:ProgramFiles(x86)}) {
        $Candidates += (Join-Path ${env:ProgramFiles(x86)} "Inno Setup 6\ISCC.exe")
    }
    if ($env:ProgramFiles) {
        $Candidates += (Join-Path $env:ProgramFiles "Inno Setup 6\ISCC.exe")
    }
    foreach ($Candidate in $Candidates) {
        if (Test-Path $Candidate) { $Iscc = $Candidate; break }
    }
}
if (-not $Iscc) {
    throw "Inno Setup 6 (ISCC.exe) was not found. Install it from https://jrsoftware.org/isinfo.php."
}

$Status = & $Git.Source status --porcelain
if ($LASTEXITCODE -ne 0) {
    throw "git status failed."
}
if ($Status) {
    throw "The working tree is not clean. Commit or stash changes before releasing."
}

$Changelog = [IO.File]::ReadAllText($ChangelogFile)
$EscapedVersion = [regex]::Escape($Version)
$Heading = [regex]::Match($Changelog, "(?m)^## \[$EscapedVersion\](?: - \d{4}-\d{2}-\d{2})?[ \t]*$")
if (-not $Heading.Success) {
    throw "Add a '## [$Version]' section to CHANGELOG.md before releasing."
}
$Remainder = $Changelog.Substring($Heading.Index + $Heading.Length)
$NextHeading = [regex]::Match($Remainder, "(?m)^## \[")
$Body = if ($NextHeading.Success) { $Remainder.Substring(0, $NextHeading.Index) } else { $Remainder }
$Body = (($Body -split "\r?\n") | Where-Object { $_ -notmatch '^\[[^\]]+\]:\s+https?://' }) -join "`n"
$Body = $Body.Trim()
if (-not $Body) {
    throw "The CHANGELOG section for $Version is empty."
}

if (-not $SkipTests) {
    if (-not (Test-Path $VenvPython)) {
        $VenvPython = (Get-Command python -ErrorAction Stop).Source
    }

    Write-Step "Checking Python sources"
    & $VenvPython -m compileall -q $AppDir
    if ($LASTEXITCODE -ne 0) { throw "Python syntax check failed." }

    $UnitTests = Join-Path $AppDir "tests"
    if (Test-Path $UnitTests) {
        Write-Step "Running updater unit tests"
        Push-Location $AppDir
        try {
            & $VenvPython -m unittest discover -s tests -p "test_*.py"
            if ($LASTEXITCODE -ne 0) { throw "Updater tests failed." }
        } finally {
            Pop-Location
        }
    }

    $Npm = Get-Command npm -ErrorAction SilentlyContinue
    $TestsDir = Join-Path $RepoDir "tests"
    if ($Npm -and (Test-Path (Join-Path $TestsDir "package.json")) -and (Test-Path (Join-Path $TestsDir "node_modules"))) {
        Write-Step "Running frontend unit tests"
        Push-Location $TestsDir
        try {
            & $Npm.Source run test
            if ($LASTEXITCODE -ne 0) { throw "Frontend tests failed." }
        } finally {
            Pop-Location
        }
    } else {
        Write-Warning "Frontend unit tests were skipped."
    }
}

if ($VersionChanged) {
    Write-Step "Updating APP_VERSION to $Version"
    $UpdatedSource = [regex]::Replace($VersionSource, '(?m)^APP_VERSION\s*=\s*"[0-9]+\.[0-9]+\.[0-9]+"', "APP_VERSION = `"$Version`"")
    [IO.File]::WriteAllText($PathsFile, $UpdatedSource, $Utf8NoBom)
} else {
    Write-Step "APP_VERSION is already $Version"
}

Write-Step "Building Spendly $Version"
if ($SkipVenv) {
    & $BuildScript -SkipVenv
} else {
    & $BuildScript
}
if ($LASTEXITCODE -ne 0) {
    throw "Build failed with exit code $LASTEXITCODE."
}

$Assets = @(
    "Spendly-$Version-Setup.exe",
    "Spendly-$Version-Update.exe",
    "Spendly-$Version-portable.zip"
)
foreach ($Name in $Assets) {
    $Path = Join-Path $DistDir $Name
    if (-not (Test-Path $Path)) {
        throw "Expected build output was not created: $Path"
    }
}

$ChecksumName = "SHA256SUMS.txt"
$ChecksumPath = Join-Path $DistDir $ChecksumName
$Lines = foreach ($Name in $Assets) {
    $Hash = (Get-FileHash (Join-Path $DistDir $Name) -Algorithm SHA256).Hash.ToLowerInvariant()
    "$Hash  $Name"
}
[IO.File]::WriteAllText($ChecksumPath, (($Lines -join "`n") + "`n"), $Utf8NoBom)

if ($VersionChanged) {
    Write-Step "Committing version $Version"
    & $Git.Source add -- $PathsFile
    if ($LASTEXITCODE -ne 0) { throw "git add failed." }
    & $Git.Source commit -m "Release v$Version"
    if ($LASTEXITCODE -ne 0) { throw "git commit failed." }
}

$Tag = "v$Version"
& $Git.Source tag -a $Tag -m "Spendly $Version"
if ($LASTEXITCODE -ne 0) { throw "git tag failed." }

$Branch = (& $Git.Source rev-parse --abbrev-ref HEAD).Trim()
Write-Step "Pushing $Branch and $Tag"
& $Git.Source push origin $Branch
if ($LASTEXITCODE -ne 0) { throw "git push of $Branch failed." }
& $Git.Source push origin $Tag
if ($LASTEXITCODE -ne 0) { throw "git push of $Tag failed." }

$NotesPath = Join-Path ([IO.Path]::GetTempPath()) "spendly-$Version-release.md"
[IO.File]::WriteAllText($NotesPath, $Body + "`n", $Utf8NoBom)
$Uploads = @($Assets | ForEach-Object { Join-Path $DistDir $_ }) + $ChecksumPath

Write-Step "Publishing GitHub release $Tag"
& $Gh.Source release create $Tag @Uploads --title "Spendly $Version" --notes-file $NotesPath --latest
if ($LASTEXITCODE -ne 0) {
    throw "GitHub release creation failed. The tag $Tag was pushed; create the release manually with: gh release create $Tag --notes-file $NotesPath"
}

$Release = & $Gh.Source release view $Tag --json assets,url | ConvertFrom-Json
if ($LASTEXITCODE -ne 0) {
    throw "Could not verify the GitHub release."
}
$Uploaded = @($Release.assets | ForEach-Object { $_.name })
foreach ($Name in ($Assets + $ChecksumName)) {
    if ($Uploaded -notcontains $Name) {
        throw "Release asset is missing: $Name"
    }
}

Remove-Item $NotesPath -Force -ErrorAction SilentlyContinue
Write-Step "Release published: $($Release.url)"
