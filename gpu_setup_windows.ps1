param(
    [string]$CudaInstallerUrl = "https://developer.download.nvidia.com/compute/cuda/11.2.2/local_installers/cuda_11.2.2_461.33_win10.exe",
    [string]$CudaInstallerPath = "$env:TEMP\cuda_11.2.2_win10.exe",
    [string]$CudnnArchivePath = "$PWD\cudnn-windows-x86_64-8.1.1.33_cuda11.2-archive.zip",
    [string]$CudaRoot = "C:\Program Files\NVIDIA GPU Computing Toolkit\CUDA\v11.2"
)

$ErrorActionPreference = "Stop"

function Add-MachinePathEntry {
    param([string]$Entry)

    if (-not (Test-Path -LiteralPath $Entry)) {
        Write-Host "Skip PATH entry because it does not exist: $Entry"
        return
    }

    $machinePath = [Environment]::GetEnvironmentVariable("Path", "Machine")
    $parts = $machinePath -split ";"
    if ($parts -contains $Entry) {
        Write-Host "PATH already contains: $Entry"
        return
    }

    $newPath = ($parts + $Entry | Where-Object { $_ -and $_.Trim() } | Select-Object -Unique) -join ";"
    [Environment]::SetEnvironmentVariable("Path", $newPath, "Machine")
    Write-Host "Added PATH entry: $Entry"
}

Write-Host "=== CUDA 11.2 + cuDNN 8.1 Setup for TensorFlow 2.10.0 on Windows ==="
Write-Host "Target GPU: NVIDIA GeForce RTX 3060 Laptop GPU"
Write-Host "Target TensorFlow: 2.10.0"
Write-Host ""

if (-not (Get-Command nvidia-smi -ErrorAction SilentlyContinue)) {
    throw "nvidia-smi not found. Please install/update the NVIDIA display driver before continuing."
}

Write-Host "Detected GPU:"
& nvidia-smi --query-gpu=name,driver_version,memory.total --format=csv,noheader
Write-Host ""

if (-not (Test-Path -LiteralPath $CudaInstallerPath)) {
    Write-Host "Downloading CUDA 11.2.2 installer..."
    Invoke-WebRequest -Uri $CudaInstallerUrl -OutFile $CudaInstallerPath
} else {
    Write-Host "CUDA installer already present: $CudaInstallerPath"
}

Write-Host "Launching CUDA 11.2.2 installer..."
Start-Process -FilePath $CudaInstallerPath -ArgumentList "-s" -Wait

if (-not (Test-Path -LiteralPath $CudaRoot)) {
    throw "CUDA installation did not create expected directory: $CudaRoot"
}

[Environment]::SetEnvironmentVariable("CUDA_PATH", $CudaRoot, "Machine")
[Environment]::SetEnvironmentVariable("CUDA_HOME", $CudaRoot, "Machine")
Add-MachinePathEntry -Entry (Join-Path $CudaRoot "bin")
Add-MachinePathEntry -Entry (Join-Path $CudaRoot "libnvvp")

if (-not (Test-Path -LiteralPath $CudnnArchivePath)) {
    throw "cuDNN archive not found: $CudnnArchivePath`nDownload cuDNN 8.1.1 for CUDA 11.2 from https://developer.nvidia.com/rdp/cudnn-archive and place it at the path above."
}

$extractRoot = Join-Path $env:TEMP "cudnn_8_1_cuda11_2"
if (Test-Path -LiteralPath $extractRoot) {
    Remove-Item -LiteralPath $extractRoot -Recurse -Force
}

Write-Host "Extracting cuDNN archive..."
Expand-Archive -LiteralPath $CudnnArchivePath -DestinationPath $extractRoot -Force

$cudnnBase = Get-ChildItem -Path $extractRoot -Directory | Select-Object -First 1
if (-not $cudnnBase) {
    throw "Failed to extract cuDNN archive."
}

$cudnnBin = Join-Path $cudnnBase.FullName "bin"
$cudnnInclude = Join-Path $cudnnBase.FullName "include"
$cudnnLib = Join-Path $cudnnBase.FullName "lib\x64"

Write-Host "Copying cuDNN files into CUDA 11.2..."
Copy-Item -Path (Join-Path $cudnnBin "*") -Destination (Join-Path $CudaRoot "bin") -Force
Copy-Item -Path (Join-Path $cudnnInclude "*") -Destination (Join-Path $CudaRoot "include") -Force
Copy-Item -Path (Join-Path $cudnnLib "*") -Destination (Join-Path $CudaRoot "lib\x64") -Force

Add-MachinePathEntry -Entry (Join-Path $CudaRoot "lib\x64")

Write-Host ""
Write-Host "CUDA/cuDNN installation and environment configuration completed."
Write-Host "Open a new PowerShell window, then verify with:"
Write-Host "python -c `"import tensorflow as tf; print(tf.__version__); print(tf.config.list_physical_devices('GPU')); print(tf.test.is_built_with_cuda())`""
