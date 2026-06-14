param(
    [string]$PythonPath = ".\\bike_demand_research\\venv\\Scripts\\python.exe"
)

$ErrorActionPreference = "Stop"

function Get-DllStatus {
    param(
        [string[]]$SearchRoots,
        [string[]]$DllNames
    )

    $result = @{}
    foreach ($dll in $DllNames) {
        $result[$dll] = @()
        foreach ($root in $SearchRoots) {
            if ([string]::IsNullOrWhiteSpace($root)) {
                continue
            }
            if (-not (Test-Path -LiteralPath $root)) {
                continue
            }
            $matches = Get-ChildItem -Path $root -Filter $dll -Recurse -ErrorAction SilentlyContinue |
                Select-Object -ExpandProperty FullName
            if ($matches) {
                $result[$dll] += $matches
            }
        }
    }
    return $result
}

if (-not (Test-Path -LiteralPath $PythonPath)) {
    throw "Python path not found: $PythonPath"
}

$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$nvidiaSmi = Get-Command nvidia-smi -ErrorAction SilentlyContinue
$gpuVisible = $false
$gpuInfo = @()
if ($nvidiaSmi) {
    $gpuInfo = & nvidia-smi --query-gpu=name,driver_version,memory.total --format=csv,noheader
    if ($LASTEXITCODE -eq 0 -and $gpuInfo.Count -gt 0) {
        $gpuVisible = $true
    }
}

$pythonJson = & $PythonPath -c "import json, sys; print(json.dumps({'python_executable': sys.executable, 'python_version': sys.version.split()[0]}))"
$tfJson = & $PythonPath -c "import json; result={};`ntry:`n import tensorflow as tf`n build_info = tf.sysconfig.get_build_info()`n result={'tensorflow_version': tf.__version__, 'gpu_devices': [device.name for device in tf.config.list_physical_devices('GPU')], 'cuda_version': build_info.get('cuda_version'), 'cudnn_version': build_info.get('cudnn_version'), 'is_built_with_cuda': bool(tf.test.is_built_with_cuda())}`nexcept Exception as exc:`n result={'tensorflow_error': str(exc)}`nprint(json.dumps(result, ensure_ascii=False))"

$pythonInfo = $pythonJson | ConvertFrom-Json
$tfInfo = $tfJson | ConvertFrom-Json

$cudaPath = [Environment]::GetEnvironmentVariable("CUDA_PATH", "Machine")
if (-not $cudaPath) {
    $cudaPath = $env:CUDA_PATH
}
$cudaHome = [Environment]::GetEnvironmentVariable("CUDA_HOME", "Machine")
if (-not $cudaHome) {
    $cudaHome = $env:CUDA_HOME
}

$candidateRoots = @(
    $cudaPath,
    $cudaHome,
    "C:\\Program Files\\NVIDIA GPU Computing Toolkit\\CUDA\\v11.2",
    "C:\\tools\\cuda"
)

$dllNames = @(
    "cudart64_110.dll",
    "cublas64_11.dll",
    "cublasLt64_11.dll",
    "cufft64_10.dll",
    "curand64_10.dll",
    "cusolver64_11.dll",
    "cusparse64_11.dll",
    "cudnn64_8.dll"
)

$dllStatus = Get-DllStatus -SearchRoots $candidateRoots -DllNames $dllNames
$missingDlls = @(
    $dllStatus.GetEnumerator() |
    Where-Object { $_.Value.Count -eq 0 } |
    ForEach-Object { $_.Key }
)

$compatibility = "PASS"
$issues = New-Object System.Collections.Generic.List[string]
if (-not $gpuVisible) {
    $compatibility = "FAIL"
    $issues.Add("nvidia-smi did not detect the RTX 3060 Laptop GPU.")
}
if ($tfInfo.tensorflow_version -ne "2.10.0") {
    $compatibility = "FAIL"
    $issues.Add("The selected Python environment is not using TensorFlow 2.10.0.")
}
if (-not $tfInfo.is_built_with_cuda) {
    $compatibility = "FAIL"
    $issues.Add("The selected TensorFlow build does not report CUDA support.")
}
if ($missingDlls.Count -gt 0) {
    $compatibility = "FAIL"
    $issues.Add("Missing CUDA/cuDNN DLLs: $($missingDlls -join ', ')")
}
if ($tfInfo.gpu_devices.Count -eq 0) {
    $compatibility = "FAIL"
    $issues.Add("TensorFlow did not detect any GPU devices.")
}

$report = [ordered]@{
    generated_at = (Get-Date).ToString("yyyy-MM-dd HH:mm:ss")
    project_root = $projectRoot
    python = $pythonInfo
    tensorflow = $tfInfo
    nvidia_smi_visible = $gpuVisible
    nvidia_gpu_info = $gpuInfo
    environment_variables = [ordered]@{
        CUDA_PATH = $cudaPath
        CUDA_HOME = $cudaHome
    }
    dll_status = $dllStatus
    compatibility_result = $compatibility
    issues = $issues
}

$reportPath = Join-Path $projectRoot "gpu_environment_report.json"
$report | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath $reportPath -Encoding UTF8

Write-Host "=== GPU Environment Check ==="
Write-Host "Python: $($pythonInfo.python_version) [$($pythonInfo.python_executable)]"
if ($tfInfo.tensorflow_version) {
    Write-Host "TensorFlow: $($tfInfo.tensorflow_version)"
    Write-Host "CUDA Build: $($tfInfo.cuda_version)"
    Write-Host "cuDNN Build: $($tfInfo.cudnn_version)"
    Write-Host "GPU Devices: $($tfInfo.gpu_devices -join ', ')"
} else {
    Write-Host "TensorFlow Error: $($tfInfo.tensorflow_error)"
}
Write-Host "GPU Visible: $gpuVisible"
Write-Host "Compatibility Result: $compatibility"
if ($issues.Count -gt 0) {
    Write-Host "Issues:"
    foreach ($issue in $issues) {
        Write-Host " - $issue"
    }
}
Write-Host "Report saved to: $reportPath"
