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
$DistDir = Join-Path $RepoDir "dist"
$VenvDir = Join-Path $RepoDir ".venv"
$VenvPython = Join-Path $VenvDir "Scripts\python.exe"
$SpecFile = Join-Path $BuildDir "Spendly.spec"
$IssFile = Join-Path $BuildDir "installer.iss"
$AppIcon = Join-Path $BuildDir "icon.ico"
$WebView2Installer = Join-Path $BuildDir "MicrosoftEdgeWebView2RuntimeInstallerX64.exe"
$WebView2Url = "https://go.microsoft.com/fwlink/?linkid=2124701"
$Version = "1.0.0"

if ($SkipVenv) {
    $VenvPython = (Get-Command python -ErrorAction Stop).Source
}

function Write-Step([string]$Message) {
    Write-Host "==> $Message" -ForegroundColor Cyan
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

        Write-Step "Building installer"
        & $Iscc $IssFile
        if ($LASTEXITCODE -ne 0) { throw "Inno Setup failed." }
    } else {
        Write-Warning "Inno Setup (ISCC.exe) not found. Install it from https://jrsoftware.org/isinfo.php to build the installer."
    }
}

Write-Step "Done"
Get-ChildItem $DistDir | Select-Object Name, Length
exit 0
