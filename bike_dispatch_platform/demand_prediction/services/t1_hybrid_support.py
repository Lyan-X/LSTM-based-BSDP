"""Deprecated experimental support for the retired tolerance-based T+1 hybrid scheme.

This module is intentionally kept only for historical traceability and must not be
referenced by the current production or SRS-compliant main flow.
"""

from __future__ import annotations

import json
import pickle
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


ROOT_DIR = Path(__file__).resolve().parents[3]
MODEL_ASSETS_DIR = ROOT_DIR / "bike_dispatch_platform" / "demand_prediction" / "model_assets"
MODEL_SELECTION_PATH = MODEL_ASSETS_DIR / "model_selection.json"
T1_HYBRID_BUNDLE_PATH = MODEL_ASSETS_DIR / "bike_sharing_t1_hybrid.pkl"
T1_HYBRID_METRICS_PATH = MODEL_ASSETS_DIR / "model_metrics_t1_hybrid.json"

LAG_FEATURE_HOURS = (1, 2, 3, 4, 6, 12, 24, 25, 47, 48, 168, 336)
WINDOW_FEATURE_HOURS = (3, 6, 12, 24, 48)


def default_model_selection() -> dict[str, Any]:
    return {
        "active_model_alias": "production",
        "aliases": {
            "production": {
                "type": "keras_forecaster",
                "asset_path": "bike_sharing_lstm_model.keras",
                "scaler_path": "scaler.pkl",
                "metrics_path": "model_metrics.json",
                "description": "Frozen production 48h-to-48h LSTM forecaster.",
            },
            "t1_hybrid": {
                "type": "hybrid_t1_sign_const1",
                "asset_path": "bike_sharing_t1_hybrid.pkl",
                "base_model_path": "bike_sharing_lstm_model.keras",
                "base_scaler_path": "scaler.pkl",
                "metrics_path": "model_metrics_t1_hybrid.json",
                "description": "Parallel T+1-focused hybrid predictor that overrides only the first forecast hour.",
            },
        },
    }


def resolve_model_selection() -> dict[str, Any]:
    if MODEL_SELECTION_PATH.exists():
        with open(MODEL_SELECTION_PATH, "r", encoding="utf-8") as selection_file:
            selection = json.load(selection_file)
    else:
        selection = default_model_selection()
    aliases = selection.get("aliases", {})
    active_alias = selection.get("active_model_alias", "production")
    if active_alias not in aliases:
        active_alias = "production"
    active_spec = aliases.get(active_alias, {})
    return {
        "active_model_alias": active_alias,
        "active_spec": active_spec,
        "aliases": aliases,
    }


def save_model_selection(selection: dict[str, Any]) -> None:
    MODEL_ASSETS_DIR.mkdir(parents=True, exist_ok=True)
    with open(MODEL_SELECTION_PATH, "w", encoding="utf-8") as selection_file:
        json.dump(selection, selection_file, ensure_ascii=False, indent=2)


def load_t1_hybrid_bundle(bundle_path: Path | None = None) -> dict[str, Any]:
    resolved_path = bundle_path or T1_HYBRID_BUNDLE_PATH
    with open(resolved_path, "rb") as bundle_file:
        return pickle.load(bundle_file)


def build_t1_feature_vector(
    station_frame: pd.DataFrame,
    *,
    station_id: int,
    current_inventory: float | None = None,
) -> np.ndarray:
    if len(station_frame) < max(LAG_FEATURE_HOURS):
        raise ValueError(
            f"Station {station_id} requires at least {max(LAG_FEATURE_HOURS)} historical hours, "
            f"but only {len(station_frame)} rows are available."
        )

    ordered_frame = station_frame.sort_values("hour").reset_index(drop=True)
    last_hour = pd.Timestamp(ordered_frame.iloc[-1]["hour"])
    target_hour = last_hour + pd.Timedelta(hours=1)
    feature_row: list[float] = [
        float(station_id),
        float(target_hour.hour),
        float(target_hour.dayofweek),
    ]

    for lag_hour in LAG_FEATURE_HOURS:
        lag_row = ordered_frame.iloc[-lag_hour]
        inventory_value = float(lag_row["inventory"])
        if lag_hour == 1 and current_inventory is not None:
            inventory_value = float(current_inventory)
        feature_row.extend(
            [
                float(lag_row["net_flow"]),
                inventory_value,
                float(lag_row["inflow"]),
                float(lag_row["outflow"]),
            ]
        )

    for window_hour in WINDOW_FEATURE_HOURS:
        window_frame = ordered_frame.tail(window_hour)
        net_flow_series = window_frame["net_flow"].astype(float)
        feature_row.extend(
            [
                float(net_flow_series.sum()),
                float(net_flow_series.mean()),
                float(net_flow_series.std(ddof=0)),
                float(window_frame["inflow"].astype(float).sum()),
                float(window_frame["outflow"].astype(float).sum()),
            ]
        )

    return np.asarray(feature_row, dtype=np.float32)


def predict_t_plus_1_with_bundle(
    bundle: dict[str, Any],
    station_frame: pd.DataFrame,
    *,
    station_id: int,
    current_inventory: float | None = None,
) -> float:
    feature_vector = build_t1_feature_vector(
        station_frame,
        station_id=station_id,
        current_inventory=current_inventory,
    ).reshape(1, -1)
    sign_model = bundle["sign_model"]
    predicted_sign = float(sign_model.predict(feature_vector)[0])
    if predicted_sign == 0:
        predicted_sign = 1.0
    magnitude = float(bundle.get("t_plus_1_magnitude", 1.0))
    return float(predicted_sign * magnitude)
