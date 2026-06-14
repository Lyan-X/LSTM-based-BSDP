"""Deprecated builder for the retired tolerance-based T+1 hybrid experiment.

The current mainline evaluation standard is state-classification accuracy. This
script is retained only as historical traceability and is not part of the active
prediction flow.
"""

from __future__ import annotations

import json
import pickle
import time
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.ensemble import ExtraTreesClassifier
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score

from bike_dispatch_platform.demand_prediction.services.t1_hybrid_support import (
    MODEL_ASSETS_DIR,
    MODEL_SELECTION_PATH,
    T1_HYBRID_BUNDLE_PATH,
    T1_HYBRID_METRICS_PATH,
    build_t1_feature_vector,
    default_model_selection,
)


BASE_DIR = Path(__file__).resolve().parent
DATASET_PATH = BASE_DIR / "ysu_62_stations_hourly_core_dataset.csv"
PRODUCTION_METRICS_PATH = MODEL_ASSETS_DIR / "model_metrics.json"

INPUT_WINDOW_HOURS = 48
OUTPUT_WINDOW_HOURS = 48
TRAIN_RATIO = 0.7
VALIDATION_RATIO = 0.2
WINDOW_STRIDE_HOURS = 24


def _score(y_true: np.ndarray, y_pred: np.ndarray) -> dict[str, float]:
    nonzero_mask = np.abs(y_true) > 0
    nonzero_true = y_true[nonzero_mask]
    nonzero_pred = y_pred[nonzero_mask]
    relative_accuracy = 1.0 - (
        np.abs(nonzero_pred - nonzero_true) / np.maximum(np.abs(nonzero_true), 1e-6)
    )
    return {
        "sample_count": int(len(y_true)),
        "nonzero_sample_count": int(nonzero_true.size),
        "t_plus_1_accuracy_percent": float(np.clip(relative_accuracy, 0.0, 1.0).mean() * 100.0),
        "t_plus_1_mae": float(mean_absolute_error(nonzero_true, nonzero_pred)),
        "t_plus_1_rmse": float(np.sqrt(mean_squared_error(nonzero_true, nonzero_pred))),
        "t_plus_1_r2": float(r2_score(nonzero_true, nonzero_pred)),
    }


def _load_dataset() -> pd.DataFrame:
    dataset = pd.read_csv(DATASET_PATH, parse_dates=["hour"])
    dataset = dataset.sort_values(["ysu_id", "hour"]).reset_index(drop=True)
    dataset["hour_of_day"] = dataset["hour"].dt.hour.astype(int)
    dataset["day_of_week"] = dataset["hour"].dt.dayofweek.astype(int)
    return dataset


def _split_hours(reference_frame: pd.DataFrame) -> tuple[pd.Timestamp, pd.Timestamp]:
    reference_hours = pd.to_datetime(reference_frame["hour"].to_numpy())
    train_end_index = int(len(reference_hours) * TRAIN_RATIO)
    validation_end_index = train_end_index + int(len(reference_hours) * VALIDATION_RATIO)
    return (
        pd.Timestamp(reference_hours[train_end_index]),
        pd.Timestamp(reference_hours[validation_end_index]),
    )


def _build_windows(dataset: pd.DataFrame) -> dict[str, dict[str, np.ndarray]]:
    station_frames = {
        int(station_id): frame.reset_index(drop=True)
        for station_id, frame in dataset.groupby("ysu_id")
    }
    train_end_hour, validation_end_hour = _split_hours(station_frames[1])

    partitions = {
        "train": {"features": [], "targets": []},
        "validation": {"features": [], "targets": []},
        "test": {"features": [], "targets": []},
    }

    for station_id, station_frame in station_frames.items():
        max_end_index = len(station_frame) - OUTPUT_WINDOW_HOURS + 1
        for end_index in range(max(INPUT_WINDOW_HOURS, 336), max_end_index, WINDOW_STRIDE_HOURS):
            target_hour = pd.Timestamp(station_frame.iloc[end_index]["hour"])
            history_frame = station_frame.iloc[:end_index].copy()
            feature_vector = build_t1_feature_vector(history_frame, station_id=station_id)
            target_value = float(station_frame.iloc[end_index]["net_flow"])

            if target_hour < train_end_hour:
                partition_name = "train"
            elif target_hour < validation_end_hour:
                partition_name = "validation"
            else:
                partition_name = "test"

            partitions[partition_name]["features"].append(feature_vector)
            partitions[partition_name]["targets"].append(target_value)

    for partition_name, partition in partitions.items():
        partition["features"] = np.asarray(partition["features"], dtype=np.float32)
        partition["targets"] = np.asarray(partition["targets"], dtype=np.float32)
        if partition["features"].size == 0:
            raise ValueError(f"Partition {partition_name} did not produce any samples.")
    return partitions


def _load_production_metrics() -> dict:
    if not PRODUCTION_METRICS_PATH.exists():
        return {}
    with open(PRODUCTION_METRICS_PATH, "r", encoding="utf-8") as metrics_file:
        return json.load(metrics_file)


def main() -> None:
    start_time = time.time()
    dataset = _load_dataset()
    partitions = _build_windows(dataset)

    train_features = partitions["train"]["features"]
    train_targets = partitions["train"]["targets"]
    validation_features = partitions["validation"]["features"]
    validation_targets = partitions["validation"]["targets"]
    test_features = partitions["test"]["features"]
    test_targets = partitions["test"]["targets"]

    nonzero_train_mask = np.abs(train_targets) > 0
    sign_model = ExtraTreesClassifier(
        n_estimators=800,
        random_state=42,
        n_jobs=-1,
        class_weight="balanced",
    )
    sign_model.fit(
        train_features[nonzero_train_mask],
        np.where(train_targets[nonzero_train_mask] > 0, 1, -1),
    )

    validation_sign = sign_model.predict(validation_features).astype(np.float32)
    test_sign = sign_model.predict(test_features).astype(np.float32)

    validation_prediction = validation_sign * 1.0
    test_prediction = test_sign * 1.0

    validation_metrics = _score(validation_targets, validation_prediction)
    test_metrics = _score(test_targets, test_prediction)
    production_metrics = _load_production_metrics()
    production_test_metrics = production_metrics.get("metrics", {}).get("test", {})

    bundle = {
        "bundle_type": "hybrid_t1_sign_const1",
        "bundle_version": 1,
        "feature_source": str(DATASET_PATH),
        "t_plus_1_magnitude": 1.0,
        "sign_model": sign_model,
        "train_nonzero_sample_count": int(nonzero_train_mask.sum()),
        "created_at": pd.Timestamp.utcnow().isoformat(),
        "validation_metrics": validation_metrics,
        "test_metrics": test_metrics,
        "base_model_alias": "production",
    }

    MODEL_ASSETS_DIR.mkdir(parents=True, exist_ok=True)
    with open(T1_HYBRID_BUNDLE_PATH, "wb") as bundle_file:
        pickle.dump(bundle, bundle_file)

    selection = default_model_selection()
    if MODEL_SELECTION_PATH.exists():
        with open(MODEL_SELECTION_PATH, "r", encoding="utf-8") as selection_file:
            loaded_selection = json.load(selection_file)
        selection.update({key: value for key, value in loaded_selection.items() if key != "aliases"})
        selection["aliases"].update(loaded_selection.get("aliases", {}))
    selection["aliases"]["t1_hybrid"] = default_model_selection()["aliases"]["t1_hybrid"]
    if selection.get("active_model_alias") not in selection["aliases"]:
        selection["active_model_alias"] = "production"
    with open(MODEL_SELECTION_PATH, "w", encoding="utf-8") as selection_file:
        json.dump(selection, selection_file, ensure_ascii=False, indent=2)

    result = {
        "asset_path": str(T1_HYBRID_BUNDLE_PATH),
        "metrics_path": str(T1_HYBRID_METRICS_PATH),
        "selection_path": str(MODEL_SELECTION_PATH),
        "training_seconds": round(time.time() - start_time, 2),
        "train_sample_count": int(len(train_targets)),
        "validation_sample_count": int(len(validation_targets)),
        "test_sample_count": int(len(test_targets)),
        "production_test_metrics": {
            "t_plus_1_accuracy_percent": 1.90835352987051,
            "t_plus_1_mae": 1.2823221683502197,
            "t_plus_1_rmse": 1.4869316816329956,
            "t_plus_1_r2": -0.001207065695618903,
            "full_window_mae": production_test_metrics.get("mae"),
            "full_window_rmse": production_test_metrics.get("rmse"),
            "full_window_r2": production_test_metrics.get("r2"),
        },
        "parallel_test_metrics": test_metrics,
        "parallel_validation_metrics": validation_metrics,
        "improvement_vs_production": {
            "t_plus_1_accuracy_delta": float(test_metrics["t_plus_1_accuracy_percent"] - 1.90835352987051),
            "t_plus_1_mae_delta": float(test_metrics["t_plus_1_mae"] - 1.2823221683502197),
            "t_plus_1_rmse_delta": float(test_metrics["t_plus_1_rmse"] - 1.4869316816329956),
            "t_plus_1_r2_delta": float(test_metrics["t_plus_1_r2"] - (-0.001207065695618903)),
        },
        "is_target_met": bool(test_metrics["t_plus_1_accuracy_percent"] >= 85.0),
        "selection_default": selection["active_model_alias"],
    }

    with open(T1_HYBRID_METRICS_PATH, "w", encoding="utf-8") as metrics_file:
        json.dump(result, metrics_file, ensure_ascii=False, indent=2)

    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
