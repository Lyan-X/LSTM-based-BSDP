"""P0-P4 compliance verification for 基于深度学习的城市共享单车调度需求预测与运维管理平台."""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Dict, List

import pandas as pd

BASE_DIR = Path(__file__).resolve().parent
APP_DIR = BASE_DIR / "bike_dispatch_platform"
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "bike_dispatch_platform.settings")

import django

django.setup()
MANAGE_PATH = BASE_DIR / "manage.py"
MAIN_SETTINGS_IMPORT = "bike_dispatch_platform.settings"
MASTER_PATH = BASE_DIR / "ysu_62_station_master_data.csv"
MAPPING_PATH = BASE_DIR / "ysu_62_station_mapping.csv"
CORE_DATASET_PATH = BASE_DIR / "ysu_62_stations_hourly_core_dataset.csv"
REQUIREMENTS_PATH = BASE_DIR / "requirements.txt"
VERIFY_REPORT_PATH = BASE_DIR / "verify_system_report.json"
MODEL_ASSETS_DIR = BASE_DIR / "bike_dispatch_platform" / "demand_prediction" / "model_assets"

REMOVED_LEGACY_FILES = [
    BASE_DIR / "generate_1day_training_data.py",
    BASE_DIR / "generate_ysu_bike_data.py",
    BASE_DIR / "generate_loss_curve.py",
    BASE_DIR / "scheduling_system.py",
    BASE_DIR / "bike_dispatch_platform" / "system_support" / "services" / "visualization_service.py",
    BASE_DIR / "bike_dispatch_platform" / "operation_management" / "management" / "commands" / "generate_test_data.py",
]

REQUIRED_MODEL_ASSETS = [
    MODEL_ASSETS_DIR / "bike_sharing_lstm_model.keras",
    MODEL_ASSETS_DIR / "scaler.pkl",
    MODEL_ASSETS_DIR / "model_metrics.json",
    MODEL_ASSETS_DIR / "training_loss_curve.png",
    MODEL_ASSETS_DIR / "sample_prediction_curve.png",
]

REQUIRED_DOCS = [
    BASE_DIR / "LSTM_model_accuracy_report.md",
    BASE_DIR / "项目启动与部署文档.md",
    BASE_DIR / "项目验收报告.md",
]

REQUIRED_TEMPLATES = [
    BASE_DIR / "bike_dispatch_platform" / "templates" / "base.html",
    BASE_DIR / "bike_dispatch_platform" / "templates" / "system_support" / "dashboard.html",
    BASE_DIR / "bike_dispatch_platform" / "templates" / "system_support" / "settings.html",
    BASE_DIR / "bike_dispatch_platform" / "templates" / "system_support" / "backup_list.html",
    BASE_DIR / "bike_dispatch_platform" / "templates" / "system_support" / "system_logs.html",
    BASE_DIR / "bike_dispatch_platform" / "templates" / "operation_management" / "station_list.html",
    BASE_DIR / "bike_dispatch_platform" / "templates" / "operation_management" / "station_edit.html",
]

SCAN_SUFFIXES = {".py", ".ps1", ".html", ".js", ".css", ".md"}
SKIP_DIR_NAMES = {
    ".git",
    "__pycache__",
    "bike_demand_research",
    "bsdp_env",
    "cache",
    "logs",
    "models",
    "output",
    "predict_results",
    "results",
    "static",
    "temp",
    "test_data",
    ".cursor",
    ".idea",
    "django_project",
    "venv",
}

RANDOM_PATTERNS = [
    re.compile(r"\brandom\b"),
    re.compile(r"\bnp\.random\b"),
]
HARDCODED_1000_PATTERN = re.compile(r"(?<!\d)1000(?!\d)")


@dataclass
class CheckResult:
    name: str
    passed: bool
    details: Dict[str, object]


def run_subprocess(args: List[str]) -> subprocess.CompletedProcess:
    return subprocess.run(
        args,
        cwd=str(BASE_DIR),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )


def _tail_lines(text: str, limit: int = 6) -> List[str]:
    lines = [line for line in text.strip().splitlines() if line]
    return lines[-limit:]


def check_engineering_convergence() -> CheckResult:
    manage_text = MANAGE_PATH.read_text(encoding="utf-8")
    django_check = run_subprocess([sys.executable, "manage.py", "check"])
    no_migration_drift = run_subprocess([sys.executable, "manage.py", "makemigrations", "--check", "--dry-run"])
    passed = (
        MAIN_SETTINGS_IMPORT in manage_text
        and "django_project.settings" not in manage_text
        and django_check.returncode == 0
        and no_migration_drift.returncode == 0
    )
    return CheckResult(
        name="工程收敛校验",
        passed=passed,
        details={
            "manage_points_to_mainline": MAIN_SETTINGS_IMPORT in manage_text,
            "legacy_django_project_entry_removed": "django_project.settings" not in manage_text,
            "django_check_returncode": django_check.returncode,
            "migration_drift_returncode": no_migration_drift.returncode,
            "django_check_stdout_tail": _tail_lines(django_check.stdout, 3),
            "migration_check_stdout_tail": _tail_lines(no_migration_drift.stdout, 3),
            "migration_check_stderr_tail": _tail_lines(no_migration_drift.stderr, 6),
        },
    )


def check_master_data_integrity() -> CheckResult:
    master = pd.read_csv(MASTER_PATH)
    mapping = pd.read_csv(MAPPING_PATH)
    expected_ids = list(range(1, 63))
    passed = (
        master.shape[0] == 62
        and mapping.shape[0] == 62
        and master["ysu_id"].tolist() == expected_ids
        and mapping["ysu_id"].tolist() == expected_ids
        and master["ysu_id"].is_unique
        and mapping["ysu_id"].is_unique
        and mapping["washington_station_id"].is_unique
        and not master.isna().any().any()
        and not mapping.isna().any().any()
        and int(master["initial_inventory"].sum()) == 1200
    )
    return CheckResult(
        name="主数据完整性校验",
        passed=passed,
        details={
            "master_station_count": int(master.shape[0]),
            "mapping_station_count": int(mapping.shape[0]),
            "master_missing_ids": sorted(set(expected_ids) - set(master["ysu_id"].astype(int).tolist())),
            "mapping_missing_ids": sorted(set(expected_ids) - set(mapping["ysu_id"].astype(int).tolist())),
            "master_duplicate_ids": int(master["ysu_id"].duplicated().sum()),
            "mapping_duplicate_ids": int(mapping["ysu_id"].duplicated().sum()),
            "mapping_duplicate_washington_ids": int(mapping["washington_station_id"].duplicated().sum()),
            "master_has_null": bool(master.isna().any().any()),
            "mapping_has_null": bool(mapping.isna().any().any()),
            "inventory_total": int(master["initial_inventory"].sum()),
        },
    )


def check_dataset_compliance() -> CheckResult:
    dataset = pd.read_csv(CORE_DATASET_PATH, parse_dates=["hour"])
    hour_totals = dataset.groupby("hour")["inventory"].sum()
    passed = (
        dataset["ysu_id"].nunique() == 62
        and int(dataset.duplicated(["ysu_id", "hour"]).sum()) == 0
        and bool((hour_totals == 1200).all())
        and bool((((dataset["inventory"] >= 0) & (dataset["inventory"] <= dataset["max_capacity"]))).all())
    )
    return CheckResult(
        name="数据集合规性校验",
        passed=passed,
        details={
            "row_count": int(dataset.shape[0]),
            "station_count": int(dataset["ysu_id"].nunique()),
            "duplicate_station_hour_rows": int(dataset.duplicated(["ysu_id", "hour"]).sum()),
            "global_inventory_min": int(hour_totals.min()),
            "global_inventory_max": int(hour_totals.max()),
            "all_hours_equal_1200": bool((hour_totals == 1200).all()),
            "inventory_out_of_bounds_rows": int(
                ((dataset["inventory"] < 0) | (dataset["inventory"] > dataset["max_capacity"])).sum()
            ),
        },
    )


def collect_source_files() -> List[Path]:
    source_files: List[Path] = []
    for path in BASE_DIR.rglob("*"):
        if not path.is_file():
            continue
        if path.resolve() == Path(__file__).resolve():
            continue
        if path.suffix.lower() not in SCAN_SUFFIXES:
            continue
        if any(part in SKIP_DIR_NAMES for part in path.parts):
            continue
        if "migrations" in path.parts:
            continue
        source_files.append(path)
    return source_files


def check_no_violation_logic() -> CheckResult:
    source_files = collect_source_files()
    random_hits: List[str] = []
    hardcoded_1000_hits: List[str] = []

    for path in source_files:
        content = path.read_text(encoding="utf-8", errors="ignore")
        if any(pattern.search(content) for pattern in RANDOM_PATTERNS):
            random_hits.append(str(path.relative_to(BASE_DIR)).replace("\\", "/"))

        if HARDCODED_1000_PATTERN.search(content):
            if "setInterval" not in content and "z-index: 1000" not in content:
                hardcoded_1000_hits.append(str(path.relative_to(BASE_DIR)).replace("\\", "/"))

    removed_status = {str(path.relative_to(BASE_DIR)).replace("\\", "/"): path.exists() for path in REMOVED_LEGACY_FILES}
    passed = not random_hits and not hardcoded_1000_hits and all(not exists for exists in removed_status.values())
    return CheckResult(
        name="违规逻辑清零校验",
        passed=passed,
        details={
            "removed_legacy_files": removed_status,
            "random_hits": random_hits,
            "hardcoded_1000_hits": hardcoded_1000_hits,
            "scanned_file_count": len(source_files),
        },
    )


def check_requirements() -> CheckResult:
    requirements = [line.strip() for line in REQUIREMENTS_PATH.read_text(encoding="utf-8").splitlines() if line.strip()]
    package_map = {}
    for line in requirements:
        if "==" in line:
            name, version = line.split("==", 1)
            package_map[name.lower()] = version
    expected_versions = {
        "tensorflow": "2.10.0",
        "keras": "2.10.0",
        "tensorboard": "2.10.1",
        "protobuf": "3.19.6",
        "numpy": "1.23.5",
        "pandas": "1.5.3",
        "scikit-learn": "1.2.2",
        "scipy": "1.10.1",
    }
    mismatches = {
        name: {"expected": version, "actual": package_map.get(name)}
        for name, version in expected_versions.items()
        if package_map.get(name) != version
    }
    passed = not mismatches
    return CheckResult(
        name="依赖合规性校验",
        passed=passed,
        details={
            "tensorflow_line": next((line for line in requirements if line.startswith("tensorflow==")), None),
            "package_count": len(requirements),
            "mismatches": mismatches,
        },
    )


def check_django_health() -> CheckResult:
    django_check = run_subprocess([sys.executable, "manage.py", "check"])
    migration_check = run_subprocess([sys.executable, "manage.py", "makemigrations", "--check", "--dry-run"])
    passed = django_check.returncode == 0 and migration_check.returncode == 0
    return CheckResult(
        name="Django工程健康度校验",
        passed=passed,
        details={
            "django_check_returncode": django_check.returncode,
            "migration_check_returncode": migration_check.returncode,
            "django_check_stdout_tail": _tail_lines(django_check.stdout, 3),
            "django_check_stderr_tail": _tail_lines(django_check.stderr, 6),
            "migration_check_stdout_tail": _tail_lines(migration_check.stdout, 3),
            "migration_check_stderr_tail": _tail_lines(migration_check.stderr, 6),
        },
    )


def check_model_assets() -> CheckResult:
    missing = [str(path.relative_to(BASE_DIR)).replace("\\", "/") for path in REQUIRED_MODEL_ASSETS if not path.exists()]
    metrics_data = {}
    metrics_path = MODEL_ASSETS_DIR / "model_metrics.json"
    if metrics_path.exists():
        metrics_data = json.loads(metrics_path.read_text(encoding="utf-8"))

    passed = not missing and metrics_data.get("device") == "gpu" and metrics_data.get("station_count") == 62
    return CheckResult(
        name="模型资产齐备性校验",
        passed=passed,
        details={
            "missing_assets": missing,
            "device": metrics_data.get("device"),
            "station_count": metrics_data.get("station_count"),
            "metrics_keys": sorted(metrics_data.keys()),
        },
    )


def check_prediction_service() -> CheckResult:
    from demand_prediction.services.station_prediction_service import station_prediction_service

    payload = station_prediction_service.get_batch_response(force=False)
    station_rows = payload.get("stations", [])
    passed = (
        payload.get("success", True) is not False
        and len(station_rows) == 62
        and all(len(row.get("predictions", [])) == 48 for row in station_rows)
    )
    return CheckResult(
        name="预测服务接口校验",
        passed=passed,
        details={
            "batch_time": payload.get("batch_time"),
            "model_version": payload.get("model_version"),
            "station_count": len(station_rows),
            "prediction_length_set": sorted({len(row.get("predictions", [])) for row in station_rows}),
        },
    )


def check_runtime_chain() -> CheckResult:
    from operation_management.services.runtime_service import runtime_service

    snapshot = runtime_service.ensure_snapshot()
    passed = (
        snapshot.metrics.get("global_vehicle_total") == 1200
        and len(snapshot.station_rows) == 62
        and snapshot.metrics.get("global_total_check") == 1200
    )
    return CheckResult(
        name="实时运行链路校验",
        passed=passed,
        details={
            "global_vehicle_total": snapshot.metrics.get("global_vehicle_total"),
            "station_count": len(snapshot.station_rows),
            "dispatch_suggestion_count": len(snapshot.dispatch_suggestions),
            "global_total_check": snapshot.metrics.get("global_total_check"),
            "bucket_time": snapshot.bucket_time.isoformat(),
        },
    )


def check_templates_and_docs() -> CheckResult:
    missing_templates = [str(path.relative_to(BASE_DIR)).replace("\\", "/") for path in REQUIRED_TEMPLATES if not path.exists()]
    missing_docs = [str(path.relative_to(BASE_DIR)).replace("\\", "/") for path in REQUIRED_DOCS if not path.exists()]
    passed = not missing_templates and not missing_docs
    return CheckResult(
        name="文档与页面交付镜像校验",
        passed=passed,
        details={
            "missing_templates": missing_templates,
            "missing_docs": missing_docs,
        },
    )


def main() -> int:
    checks = [
        check_engineering_convergence(),
        check_master_data_integrity(),
        check_dataset_compliance(),
        check_no_violation_logic(),
        check_requirements(),
        check_django_health(),
        check_model_assets(),
        check_prediction_service(),
        check_runtime_chain(),
        check_templates_and_docs(),
    ]

    report = {
        "project": "基于深度学习的城市共享单车调度需求预测与运维管理平台",
        "checks": [asdict(check) for check in checks],
        "passed": all(check.passed for check in checks),
    }
    VERIFY_REPORT_PATH.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    print("=== P0-P4 Compliance Verification ===")
    for check in checks:
        status = "PASS" if check.passed else "FAIL"
        print(f"[{status}] {check.name}")
    print(f"Report saved to: {VERIFY_REPORT_PATH}")
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
