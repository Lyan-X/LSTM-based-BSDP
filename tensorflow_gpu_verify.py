"""TensorFlow GPU verification script for 基于深度学习的城市共享单车调度需求预测与运维管理平台."""

from __future__ import annotations

import json
import platform
import sys
from pathlib import Path


def main() -> int:
    report_path = Path(__file__).resolve().with_name("tensorflow_gpu_verify_report.json")

    try:
        import tensorflow as tf
    except Exception as exc:
        report = {
            "python_executable": sys.executable,
            "python_version": platform.python_version(),
            "status": "FAIL",
            "error": str(exc),
        }
        report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 1

    build_info = tf.sysconfig.get_build_info()
    gpu_devices = tf.config.list_physical_devices("GPU")

    report = {
        "python_executable": sys.executable,
        "python_version": platform.python_version(),
        "tensorflow_version": tf.__version__,
        "tensorflow_built_with_cuda": bool(tf.test.is_built_with_cuda()),
        "cuda_build_version": build_info.get("cuda_version"),
        "cudnn_build_version": build_info.get("cudnn_version"),
        "gpu_devices": [device.name for device in gpu_devices],
        "gpu_count": len(gpu_devices),
        "gpu_available": len(gpu_devices) > 0,
        "status": "PASS" if len(gpu_devices) > 0 else "FAIL",
    }

    if report["status"] == "FAIL":
        report["recommended_fix"] = (
            "Install CUDA 11.2 and cuDNN 8.1, then rerun gpu_env_check.ps1 and this script."
        )

    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
