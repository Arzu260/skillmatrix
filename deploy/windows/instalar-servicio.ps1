# Instala SkillMatrix como servicio de Windows usando NSSM (https://nssm.cc, herramienta de terceros).
# Ejecutar en PowerShell como administrador desde la carpeta del proyecto, después de haber
# creado el entorno (.venv) y el archivo .env (por ejemplo, ejecutando iniciar.bat una vez).
#   .\deploy\windows\instalar-servicio.ps1 -Nssm "C:\Herramientas\nssm.exe"
param(
    [string]$Nssm = "nssm.exe",
    [string]$Nombre = "SkillMatrix",
    [int]$Puerto = 5000
)
$ErrorActionPreference = "Stop"
$dir = (Resolve-Path "$PSScriptRoot\..\..").Path
$python = Join-Path $dir ".venv\Scripts\python.exe"
if (-not (Test-Path $python)) { throw "No existe $python. Ejecuta antes iniciar.bat para crear el entorno." }
if (-not (Test-Path (Join-Path $dir ".env"))) { throw "Falta el archivo .env en $dir." }

& $Nssm install $Nombre $python "app.py"
& $Nssm set $Nombre AppDirectory $dir
& $Nssm set $Nombre DisplayName "SkillMatrix - matriz de habilidades"
& $Nssm set $Nombre Start SERVICE_AUTO_START
New-Item -ItemType Directory -Force -Path (Join-Path $dir "logs") | Out-Null
& $Nssm set $Nombre AppStdout (Join-Path $dir "logs\skillmatrix.log")
& $Nssm set $Nombre AppStderr (Join-Path $dir "logs\skillmatrix.log")
& $Nssm set $Nombre AppRotateFiles 1
& $Nssm set $Nombre AppRotateBytes 10485760

New-NetFirewallRule -DisplayName "SkillMatrix ($Puerto)" -Direction Inbound -Protocol TCP -LocalPort $Puerto -Action Allow | Out-Null
Start-Service $Nombre
Write-Host "Servicio $Nombre instalado y arrancado. Prueba: http://localhost:$Puerto/api/health"
