# Windows 7 build only: give Python 3.8 an SQLite with the JSON functions.
#
# The python.org Windows build of 3.8 ships an SQLite compiled without JSON1,
# so Django's JSONField fails with "no such function: JSON_VALID". This puts
# the official sqlite.org DLL (static CRT, KERNEL32 only, runs on Windows 7)
# in place of Python's own; _sqlite3.pyd loads it unchanged and PyInstaller
# bundles it into the installer.
#
# Usage (PowerShell, with the Python 3.8 you build with):
#   scripts\win7-sqlite.ps1 -Python C:\Python38\python.exe

param(
    [string]$Python = "python"
)

$ErrorActionPreference = "Stop"

$Url = "https://www.sqlite.org/2024/sqlite-dll-win-x64-3460100.zip"
$Sha256 = "300cb2918946f42a1a2f7f31a8dd89edc202570e4e49d21e13d33ecdf80a6b67"

$work = Join-Path ([System.IO.Path]::GetTempPath()) "mm-sqlite-dll"
New-Item -ItemType Directory -Force -Path $work | Out-Null
$zip = Join-Path $work "sqlite-dll.zip"

Write-Host "==> Downloading $Url"
Invoke-WebRequest -Uri $Url -OutFile $zip -UseBasicParsing
$actual = (Get-FileHash -Path $zip -Algorithm SHA256).Hash
if ($actual -ne $Sha256) {
    throw "SQLite download checksum mismatch: expected $Sha256, got $actual"
}
Expand-Archive -Path $zip -DestinationPath $work -Force

# A venv shares the base install's DLLs folder, so patch the base install.
$dlls = Join-Path (& $Python -c "import sys; print(sys.base_prefix)") "DLLs"
Write-Host "==> Replacing $dlls\sqlite3.dll"
Copy-Item -Path (Join-Path $work "sqlite3.dll") -Destination $dlls -Force

& $Python -c "import sqlite3; sqlite3.connect(':memory:').execute('select json_valid(1)'); print('    SQLite', sqlite3.sqlite_version, 'with JSON support')"
if ($LASTEXITCODE -ne 0) {
    throw "Python still cannot use the SQLite JSON functions."
}
