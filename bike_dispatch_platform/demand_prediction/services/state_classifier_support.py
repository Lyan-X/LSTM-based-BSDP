from __future__ import annotations

import json
import math
import pickle
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


ROOT_DIR = Path(__file__).resolve().parents[3]
MODEL_ASSETS_DIR = ROOT_DIR / "bike_dispatch_platform" / "demand_prediction" / "model_assets"
MODEL_SELECTION_PATH = MODEL_ASSETS_DIR / "model_selection.json"
STATE_SCHEME_EXPLORATION_PATH = MODEL_ASSETS_DIR / "state_scheme_exploration.json"

CLASSIFICATION_FEATURE_COLUMNS = [
    "inventory",
    "inflow",
    "outflow",
    "net_flow",
    "hour_sin",
    "hour_cos",
    "weekday_sin",
    "weekday_cos",
    "low_warning_threshold",
    "high_warning_threshold",
    "max_capacity",
]

STATE_SCHEME_ORDER = ["state_5", "state_7", "state_9", "state_11"]

STATE_SCHEME_CONFIGS: dict[str, dict[str, Any]] = {
    "state_5": {
        "scheme_key": "state_5",
        "class_count": 5,
        "zone_bins": {"scarce": 2, "balanced": 1, "saturated": 2},
        "description": "五档状态：稀少两级 / 适中 / 盈余两级",
    },
    "state_7": {
        "scheme_key": "state_7",
        "class_count": 7,
        "zone_bins": {"scarce": 2, "balanced": 3, "saturated": 2},
        "description": "七档状态：稀少两级、适中三级、盈余两级",
    },
    "state_9": {
        "scheme_key": "state_9",
        "class_count": 9,
        "zone_bins": {"scarce": 3, "balanced": 3, "saturated": 3},
        "description": "九档状态：稀少三级、适中三级、盈余三级",
    },
    "state_11": {
        "scheme_key": "state_11",
        "class_count": 11,
        "zone_bins": {"scarce": 3, "balanced": 5, "saturated": 3},
        "description": "十一档状态：稀少三级、适中五级、盈余三级",
    },
}

ZONE_LABELS = {
    "scarce": {
        2: ["严重稀少", "轻度稀少"],
        3: ["严重稀少", "中度稀少", "轻度稀少"],
    },
    "balanced": {
        1: ["适中"],
        3: ["偏低适中", "适中", "偏高适中"],
        5: ["明显偏低适中", "轻度偏低适中", "适中", "轻度偏高适中", "明显偏高适中"],
    },
    "saturated": {
        2: ["轻度盈余", "严重盈余"],
        3: ["轻度盈余", "中度盈余", "严重盈余"],
    },
}

ZONE_CODES = {
    "scarce": {
        2: ["severe_scarce", "scarce"],
        3: ["severe_scarce", "moderate_scarce", "scarce"],
    },
    "balanced": {
        1: ["balanced"],
        3: ["low_balanced", "balanced", "high_balanced"],
        5: ["very_low_balanced", "low_balanced", "balanced", "high_balanced", "very_high_balanced"],
    },
    "saturated": {
        2: ["saturated", "severe_saturated"],
        3: ["saturated", "moderate_saturated", "severe_saturated"],
    },
}

ZONE_COLORS = {
    "scarce": {
        2: ["#c0392b", "#e67e22"],
        3: ["#922b21", "#cb4335", "#f39c12"],
    },
    "balanced": {
        1: ["#27ae60"],
        3: ["#7dcea0", "#27ae60", "#16a085"],
        5: ["#abebc6", "#7dcea0", "#27ae60", "#1abc9c", "#148f77"],
    },
    "saturated": {
        2: ["#5dade2", "#2e86c1"],
        3: ["#85c1e9", "#5499c7", "#21618c"],
    },
}

STATE_CLASSIFIER_MODEL_PATH = MODEL_ASSETS_DIR / "bike_sharing_lstm_state_classifier_9class.keras"
STATE_CLASSIFIER_BUNDLE_PATH = MODEL_ASSETS_DIR / "state_classifier_bundle_9class.pkl"
STATE_CLASSIFIER_METRICS_PATH = MODEL_ASSETS_DIR / "model_metrics_state_classifier_9class.json"
STATE_CLASSIFIER_CONFUSION_PATH = MODEL_ASSETS_DIR / "confusion_matrix_state_classifier_9class.json"


def normalize_scheme_key(scheme_key: str | None) -> str:
    if scheme_key in STATE_SCHEME_CONFIGS:
        return str(scheme_key)
    return "state_5"


def get_state_scheme(scheme_key: str | None) -> dict[str, Any]:
    normalized_key = normalize_scheme_key(scheme_key)
    config = STATE_SCHEME_CONFIGS[normalized_key]
    zone_bins = config["zone_bins"]
    labels = (
        ZONE_LABELS["scarce"][zone_bins["scarce"]]
        + ZONE_LABELS["balanced"][zone_bins["balanced"]]
        + ZONE_LABELS["saturated"][zone_bins["saturated"]]
    )
    codes = (
        ZONE_CODES["scarce"][zone_bins["scarce"]]
        + ZONE_CODES["balanced"][zone_bins["balanced"]]
        + ZONE_CODES["saturated"][zone_bins["saturated"]]
    )
    colors = (
        ZONE_COLORS["scarce"][zone_bins["scarce"]]
        + ZONE_COLORS["balanced"][zone_bins["balanced"]]
        + ZONE_COLORS["saturated"][zone_bins["saturated"]]
    )
    definitions = {
        index: {"label": labels[index], "code": codes[index], "color": colors[index]}
        for index in range(len(labels))
    }
    return {
        **config,
        "labels": labels,
        "codes": codes,
        "colors": colors,
        "definitions": definitions,
    }


def available_state_schemes() -> list[dict[str, Any]]:
    return [get_state_scheme(key) for key in STATE_SCHEME_ORDER]


def classifier_artifact_paths(scheme_key: str | None) -> tuple[Path, Path, Path, Path]:
    scheme = get_state_scheme(scheme_key)
    suffix = f"{scheme['class_count']}class"
    return (
        MODEL_ASSETS_DIR / f"bike_sharing_lstm_state_classifier_{suffix}.keras",
        MODEL_ASSETS_DIR / f"state_classifier_bundle_{suffix}.pkl",
        MODEL_ASSETS_DIR / f"model_metrics_state_classifier_{suffix}.json",
        MODEL_ASSETS_DIR / f"confusion_matrix_state_classifier_{suffix}.json",
    )


def load_state_classifier_bundle(bundle_path: Path | None = None, scheme_key: str | None = None) -> dict[str, Any]:
    resolved_path = bundle_path or classifier_artifact_paths(scheme_key)[1]
    with open(resolved_path, "rb") as bundle_file:
        return pickle.load(bundle_file)


def default_model_selection() -> dict[str, Any]:
    return {
        "active_model_alias": "production",
        "active_state_scheme_key": "state_9",
        "recommended_state_scheme_key": "state_9",
        "aliases": {
            "production": {
                "type": "keras_forecaster",
                "asset_path": "bike_sharing_lstm_model.keras",
                "scaler_path": "scaler.pkl",
                "metrics_path": "model_metrics.json",
                "description": "冻结生产 48→48 净流量预测模型",
            },
            "t1_state_classifier": {
                "type": "t1_state_classifier",
                "base_model_path": "bike_sharing_lstm_model.keras",
                "base_scaler_path": "scaler.pkl",
                "description": "并行 T+1 多档供需状态分类模型，仅覆盖第一小时业务决策",
            },
        },
    }


def resolve_model_selection() -> dict[str, Any]:
    default_selection = default_model_selection()
    aliases = default_selection["aliases"].copy()
    active_alias = default_selection["active_model_alias"]
    active_state_scheme_key = default_selection["active_state_scheme_key"]
    recommended_state_scheme_key = default_selection["recommended_state_scheme_key"]
    if MODEL_SELECTION_PATH.exists():
        with open(MODEL_SELECTION_PATH, "r", encoding="utf-8") as selection_file:
            loaded = json.load(selection_file)
        for alias, spec in loaded.get("aliases", {}).items():
            if alias in aliases:
                aliases[alias].update(spec)
        if loaded.get("active_model_alias") in aliases:
            active_alias = loaded["active_model_alias"]
        active_state_scheme_key = normalize_scheme_key(loaded.get("active_state_scheme_key", active_state_scheme_key))
        recommended_state_scheme_key = normalize_scheme_key(
            loaded.get("recommended_state_scheme_key", recommended_state_scheme_key)
        )
    return {
        "active_model_alias": active_alias,
        "active_state_scheme_key": active_state_scheme_key,
        "recommended_state_scheme_key": recommended_state_scheme_key,
        "active_spec": aliases[active_alias],
        "active_state_scheme": get_state_scheme(active_state_scheme_key),
        "recommended_state_scheme": get_state_scheme(recommended_state_scheme_key),
        "aliases": aliases,
        "available_state_schemes": available_state_schemes(),
    }


def save_model_selection(selection: dict[str, Any]) -> None:
    default_selection = default_model_selection()
    aliases = default_selection["aliases"].copy()
    for alias, spec in selection.get("aliases", {}).items():
        if alias in aliases:
            aliases[alias].update(spec)
    active_alias = selection.get("active_model_alias", default_selection["active_model_alias"])
    if active_alias not in aliases:
        active_alias = default_selection["active_model_alias"]
    active_state_scheme_key = normalize_scheme_key(selection.get("active_state_scheme_key"))
    recommended_state_scheme_key = normalize_scheme_key(
        selection.get("recommended_state_scheme_key", active_state_scheme_key)
    )
    MODEL_ASSETS_DIR.mkdir(parents=True, exist_ok=True)
    with open(MODEL_SELECTION_PATH, "w", encoding="utf-8") as selection_file:
        json.dump(
            {
                "active_model_alias": active_alias,
                "active_state_scheme_key": active_state_scheme_key,
                "recommended_state_scheme_key": recommended_state_scheme_key,
                "aliases": aliases,
            },
            selection_file,
            ensure_ascii=False,
            indent=2,
        )


def _partition_bounds(start: int, end: int, bins: int, bin_index: int) -> tuple[int, int]:
    if bins <= 1:
        return start, end
    if end < start:
        return start, start
    count = max(end - start + 1, 1)
    lower = start + math.floor((bin_index * count) / bins)
    upper = start + math.floor(((bin_index + 1) * count) / bins) - 1
    if bin_index == bins - 1:
        upper = end
    lower = min(max(lower, start), end)
    upper = min(max(upper, lower), end)
    return lower, upper


def state_boundaries(low_warning_threshold: float, high_warning_threshold: float, max_capacity: float) -> tuple[int, int, int]:
    low = max(0, int(round(low_warning_threshold)))
    high = max(low + 1, int(round(high_warning_threshold)))
    capacity = max(high, int(round(max_capacity)))
    return low, high, capacity


def _zone_partition(
    inventory: int,
    *,
    start: int,
    end: int,
    bins: int,
) -> int:
    if bins <= 1 or end <= start:
        return 0
    count = max(end - start + 1, 1)
    offset = min(max(inventory, start), end) - start
    return min(int((offset * bins) / count), bins - 1)


def classify_inventory_state(
    inventory: float,
    low_warning_threshold: float,
    high_warning_threshold: float,
    max_capacity: float | None = None,
    *,
    scheme_key: str | None = None,
) -> int:
    scheme = get_state_scheme(scheme_key)
    zone_bins = scheme["zone_bins"]
    low, high, capacity = state_boundaries(
        low_warning_threshold,
        high_warning_threshold,
        max_capacity if max_capacity is not None else high_warning_threshold,
    )
    inventory_value = int(round(inventory))
    if inventory_value <= low:
        sparse_index = _zone_partition(inventory_value, start=0, end=low, bins=zone_bins["scarce"])
        return sparse_index
    if inventory_value < high:
        balanced_index = _zone_partition(
            inventory_value,
            start=low + 1,
            end=max(low + 1, high - 1),
            bins=zone_bins["balanced"],
        )
        return zone_bins["scarce"] + balanced_index
    saturated_index = _zone_partition(
        inventory_value,
        start=high,
        end=capacity,
        bins=zone_bins["saturated"],
    )
    return zone_bins["scarce"] + zone_bins["balanced"] + saturated_index


def _state_bounds(
    scheme_key: str | None,
    state_index: int,
    *,
    low_warning_threshold: float,
    high_warning_threshold: float,
    max_capacity: float,
) -> tuple[int, int]:
    scheme = get_state_scheme(scheme_key)
    zone_bins = scheme["zone_bins"]
    low, high, capacity = state_boundaries(low_warning_threshold, high_warning_threshold, max_capacity)
    if state_index < zone_bins["scarce"]:
        return _partition_bounds(0, low, zone_bins["scarce"], state_index)
    balanced_start = zone_bins["scarce"]
    balanced_end = balanced_start + zone_bins["balanced"]
    if balanced_start <= state_index < balanced_end:
        return _partition_bounds(low + 1, max(low + 1, high - 1), zone_bins["balanced"], state_index - balanced_start)
    saturated_start = balanced_end
    return _partition_bounds(high, capacity, zone_bins["saturated"], state_index - saturated_start)


def state_label(state_index: int, *, scheme_key: str | None = None) -> str:
    return get_state_scheme(scheme_key)["definitions"][int(state_index)]["label"]


def state_code(state_index: int, *, scheme_key: str | None = None) -> str:
    return get_state_scheme(scheme_key)["definitions"][int(state_index)]["code"]


def state_color(state_index: int, *, scheme_key: str | None = None) -> str:
    return get_state_scheme(scheme_key)["definitions"][int(state_index)]["color"]


def state_range_text(
    state_index: int,
    *,
    low_warning_threshold: float,
    high_warning_threshold: float,
    max_capacity: float,
    scheme_key: str | None = None,
) -> str:
    lower, upper = _state_bounds(
        scheme_key,
        int(state_index),
        low_warning_threshold=low_warning_threshold,
        high_warning_threshold=high_warning_threshold,
        max_capacity=max_capacity,
    )
    return f"{lower}" if lower == upper else f"{lower} - {upper}"


def state_midpoint_inventory(
    state_index: int,
    *,
    low_warning_threshold: float,
    high_warning_threshold: float,
    max_capacity: float,
    scheme_key: str | None = None,
) -> float:
    lower, upper = _state_bounds(
        scheme_key,
        int(state_index),
        low_warning_threshold=low_warning_threshold,
        high_warning_threshold=high_warning_threshold,
        max_capacity=max_capacity,
    )
    return (lower + upper) / 2.0


def build_state_feature_window(station_frame: pd.DataFrame) -> np.ndarray:
    ordered_frame = station_frame.sort_values("hour").reset_index(drop=True)
    if len(ordered_frame) < 48:
        raise ValueError("At least 48 hours of history are required for state classification input.")
    feature_window = ordered_frame.tail(48)[CLASSIFICATION_FEATURE_COLUMNS].to_numpy(dtype=np.float32)
    return feature_window
