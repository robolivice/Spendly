[CmdletBinding()]
param(
    [switch]$SkipVenv,
    [switch]$SkipIcon,
    [switch]$SkipInstaller
)

$ErrorActionPreference = "Stop"

$BuildDir = $PSScriptRoot
$RepoDir = Split-Path -Parent $BuildDir
$AppDir = Join-Path $RepoDir "Spendly"
$PathsFile = Join-Path $AppDir "paths.py"
$DistDir = Join-Path $RepoDir "dist"
$VenvDir = Join-Path $RepoDir ".venv"
$VenvPython = Join-Path $VenvDir "Scripts\python.exe"
$SpecFile = Join-Path $BuildDir "Spendly.spec"
$IssFile = Join-Path $BuildDir "installer.iss"
$AppIcon = Join-Path $BuildDir "icon.ico"
$VersionTemplate = Join-Path $BuildDir "version_info.template.txt"
$VersionInfo = Join-Path $BuildDir "version_info.generated.txt"
$WebView2Installer = Join-Path $BuildDir "MicrosoftEdgeWebView2RuntimeInstallerX64.exe"
$WebView2Url = "https://go.microsoft.com/fwlink/?linkid=2124701"
$Utf8NoBom = New-Object System.Text.UTF8Encoding -ArgumentList $false

$VersionSource = [IO.File]::ReadAllText($PathsFile)
$VersionMatch = [regex]::Match($VersionSource, '(?m)^APP_VERSION\s*=\s*"([0-9]+\.[0-9]+\.[0-9]+)"')
if (-not $VersionMatch.Success) {
    throw "APP_VERSION was not found in $PathsFile."
}
$Version = $VersionMatch.Groups[1].Value
$VersionParts = $Version.Split(".")
$VersionQuad = "{0}.{1}.{2}.0" -f $VersionParts[0], $VersionParts[1], $VersionParts[2]
$VersionTuple = "{0}, {1}, {2}, 0" -f $VersionParts[0], $VersionParts[1], $VersionParts[2]

if ($SkipVenv -and -not (Test-Path $VenvPython)) {
    $VenvPython = (Get-Command python -ErrorAction Stop).Source
}

function Write-Step([string]$Message) {
    Write-Host "==> $Message" -ForegroundColor Cyan
}

function Invoke-Iscc([string[]]$ExtraArgs, [string]$Label) {
    $Attempt = 0
    while ($true) {
        $Attempt += 1
        & $Iscc @ExtraArgs $IssFile
        if ($LASTEXITCODE -eq 0) { return }
        if ($Attempt -ge 2) { throw "Inno Setup failed for the $Label installer." }
        Start-Sleep -Seconds 2
    }
}

if (-not $SkipVenv) {
    if (-not (Test-Path $VenvPython)) {
        Write-Step "Creating virtual environment"
        $launcher = Get-Command py -ErrorAction SilentlyContinue
        if ($launcher) {
            & py -3 -m venv $VenvDir
        } else {
            & python -m venv $VenvDir
        }
        if ($LASTEXITCODE -ne 0) { throw "Could not create the virtual environment." }
    }

    Write-Step "Installing dependencies"
    & $VenvPython -m pip install --upgrade pip | Out-Null
    & $VenvPython -m pip install -r (Join-Path $AppDir "requirements-dev.txt")
    if ($LASTEXITCODE -ne 0) { throw "Dependency installation failed." }
}

if (-not (Test-Path $VenvPython)) {
    throw "Python was not found at $VenvPython. Run without -SkipVenv first."
}

if (-not $SkipIcon) {
    Write-Step "Applying app icon from build\icon.ico"
    if (-not (Test-Path $AppIcon)) { throw "App icon not found at $AppIcon." }
    Copy-Item $AppIcon (Join-Path $AppDir "assets\Spendly.ico") -Force
}

Write-Step "Generating version metadata for $Version"
if (-not (Test-Path $VersionTemplate)) { throw "Version template not found at $VersionTemplate." }
$TemplateText = [IO.File]::ReadAllText($VersionTemplate)
$VersionText = $TemplateText.Replace("@VERSION_TUPLE@", $VersionTuple).Replace("@VERSION_QUAD@", $VersionQuad).Replace("@VERSION@", $Version)
[IO.File]::WriteAllText($VersionInfo, $VersionText, $Utf8NoBom)

Write-Step "Cleaning previous output"
foreach ($path in @($DistDir, (Join-Path $BuildDir "pyinstaller"), (Join-Path $BuildDir "portable"))) {
    if (Test-Path $path) { Remove-Item -Recurse -Force $path }
}

Write-Step "Building Spendly $Version"
& $VenvPython -m PyInstaller --noconfirm --clean `
    --distpath $DistDir `
    --workpath (Join-Path $BuildDir "pyinstaller") `
    $SpecFile
if ($LASTEXITCODE -ne 0) { throw "PyInstaller failed." }

Write-Step "Creating portable package"
$PortableDir = Join-Path $BuildDir "portable"
Copy-Item -Recurse (Join-Path $DistDir "Spendly") $PortableDir
New-Item -ItemType File -Path (Join-Path $PortableDir "portable.txt") | Out-Null
$ZipPath = Join-Path $DistDir "Spendly-$Version-portable.zip"
Compress-Archive -Path (Join-Path $PortableDir "*") -DestinationPath $ZipPath -Force

if (-not $SkipInstaller) {
    $Iscc = $null
    $Command = Get-Command iscc -ErrorAction SilentlyContinue
    if ($Command) {
        $Iscc = $Command.Source
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

    if ($Iscc) {
        if (-not (Test-Path $WebView2Installer)) {
            Write-Step "Downloading WebView2 offline runtime"
            try {
                Invoke-WebRequest -Uri $WebView2Url -OutFile $WebView2Installer -UseBasicParsing
            } catch {
                throw "Could not download the WebView2 offline runtime: $($_.Exception.Message)"
            }
        }

        Write-Step "Building full installer"
        Invoke-Iscc -ExtraArgs @("/DAppVersion=$Version") -Label "full"

        Write-Step "Building update installer"
        Invoke-Iscc -ExtraArgs @("/DAppVersion=$Version", "/DLiteUpdate=1") -Label "update"
    } else {
        Write-Warning "Inno Setup (ISCC.exe) not found. Install it from https://jrsoftware.org/isinfo.php to build the installers."
    }
}

Write-Step "Done"
Get-ChildItem $DistDir | Select-Object Name, Length
exit 0
