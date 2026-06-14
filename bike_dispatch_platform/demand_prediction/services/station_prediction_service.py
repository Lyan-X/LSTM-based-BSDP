from __future__ import annotations

import json
import pickle
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List

import numpy as np
import pandas as pd
import tensorflow as tf
from django.utils import timezone

from bike_dispatch_platform.demand_prediction.models import StationPrediction
from bike_dispatch_platform.demand_prediction.services.calendar_features import attach_temporal_features
from bike_dispatch_platform.demand_prediction.services.state_classifier_support import (
    MODEL_ASSETS_DIR,
    STATE_SCHEME_EXPLORATION_PATH,
    build_state_feature_window,
    classifier_artifact_paths,
    classify_inventory_state,
    get_state_scheme,
    load_state_classifier_bundle,
    resolve_model_selection,
    state_code,
    state_color,
    state_label,
    state_midpoint_inventory,
    state_range_text,
)
from bike_dispatch_platform.operation_management.models import ParkingSpot
from bike_dispatch_platform.operation_management.services.station_service import get_runtime_settings, sync_parking_spots
from station_info.master_data import (
    OFFICIAL_PROJECT_NAME,
    PREDICTION_HORIZON_HOURS,
    STATION_COUNT,
    TOTAL_SYSTEM_VEHICLES,
)


ROOT_DIR = Path(__file__).resolve().parents[3]
DATASET_PATH = ROOT_DIR / "ysu_62_stations_hourly_core_dataset.csv"
PRODUCTION_MODEL_PATH = MODEL_ASSETS_DIR / "bike_sharing_lstm_model.keras"
PRODUCTION_SCALER_PATH = MODEL_ASSETS_DIR / "scaler.pkl"
PRODUCTION_METRICS_PATH = MODEL_ASSETS_DIR / "model_metrics.json"
INPUT_WINDOW_HOURS = 48


@dataclass
class PredictionBatch:
    batch_time: pd.Timestamp
    model_version: str
    station_payloads: Dict[int, Dict[str, object]]


def _load_dataset() -> pd.DataFrame:
    dataset = pd.read_csv(DATASET_PATH)
    dataset = attach_temporal_features(dataset)
    dataset["hour"] = pd.to_datetime(dataset["hour"])
    return dataset.sort_values(["ysu_id", "hour"]).reset_index(drop=True)


def _rebalance_vector(values: np.ndarray, mins: np.ndarray, maxs: np.ndarray) -> np.ndarray:
    balanced = np.clip(values.astype(float), mins, maxs)
    difference = float(TOTAL_SYSTEM_VEHICLES - balanced.sum())
    if abs(difference) < 1e-6:
        return balanced

    if difference > 0:
        slack = maxs - balanced
        total_slack = float(slack.sum())
        if total_slack > 0:
            balanced += difference * (slack / total_slack)
    else:
        removable = balanced - mins
        total_removable = float(removable.sum())
        if total_removable > 0:
            balanced += difference * (removable / total_removable)

    rounded = np.floor(balanced).astype(int)
    remainder = TOTAL_SYSTEM_VEHICLES - int(rounded.sum())
    if remainder != 0:
        if remainder > 0:
            order = np.argsort(-(balanced - rounded))
            for idx in order:
                if remainder <= 0:
                    break
                if rounded[idx] < maxs[idx]:
                    rounded[idx] += 1
                    remainder -= 1
        else:
            order = np.argsort(balanced - rounded)
            for idx in order:
                if remainder >= 0:
                    break
                if rounded[idx] > mins[idx]:
                    rounded[idx] -= 1
                    remainder += 1
    return np.clip(rounded.astype(float), mins, maxs)


class StationPredictionService:
    """Load active assets and expose both numeric forecasts and T+1 state fields."""

    def __init__(self) -> None:
        self._dataset = None
        self._loaded_alias = None
        self._base_model = None
        self._base_scaler_bundle = None
        self._classifier_model = None
        self._classifier_bundle = None

    @property
    def dataset(self) -> pd.DataFrame:
        if self._dataset is None:
            self._dataset = _load_dataset()
        return self._dataset

    def active_model_alias(self) -> str:
        return resolve_model_selection()["active_model_alias"]

    def active_state_scheme_key(self) -> str:
        return resolve_model_selection()["active_state_scheme_key"]

    def _active_spec(self) -> dict[str, Any]:
        return resolve_model_selection()["active_spec"]

    def _resolve_asset_path(self, relative_path: str) -> Path:
        return MODEL_ASSETS_DIR / relative_path

    def active_artifact_paths(self) -> tuple[Path, Path, Path]:
        selection = resolve_model_selection()
        spec = self._active_spec()
        if spec["type"] == "t1_state_classifier":
            model_path, bundle_path, metrics_path, _ = classifier_artifact_paths(selection["active_state_scheme_key"])
            return model_path, bundle_path, metrics_path
        return (
            self._resolve_asset_path(spec["asset_path"]),
            self._resolve_asset_path(spec["scaler_path"]),
            self._resolve_asset_path(spec["metrics_path"]),
        )

    def _load_base_model_assets(self) -> tuple[tf.keras.Model, dict]:
        if self._base_model is None:
            self._base_model = tf.keras.models.load_model(PRODUCTION_MODEL_PATH)
        if self._base_scaler_bundle is None:
            with open(PRODUCTION_SCALER_PATH, "rb") as scaler_file:
                self._base_scaler_bundle = pickle.load(scaler_file)
        return self._base_model, self._base_scaler_bundle

    def _load_state_classifier_assets(self) -> tuple[tf.keras.Model, dict]:
        if self._classifier_model is None:
            classifier_path, _, _ = self.active_artifact_paths()
            self._classifier_model = tf.keras.models.load_model(classifier_path)
        if self._classifier_bundle is None:
            bundle_path = self.active_artifact_paths()[1]
            self._classifier_bundle = load_state_classifier_bundle(bundle_path=bundle_path)
        return self._classifier_model, self._classifier_bundle

    def load_artifacts(self) -> dict[str, Any]:
        selection = resolve_model_selection()
        alias = selection["active_model_alias"]
        spec = selection["active_spec"]
        if alias != self._loaded_alias:
            self._loaded_alias = alias
            self._classifier_model = None
            self._classifier_bundle = None

        base_model, base_scaler_bundle = self._load_base_model_assets()
        if spec["type"] == "t1_state_classifier":
            classifier_model, classifier_bundle = self._load_state_classifier_assets()
            return {
                "alias": alias,
                "type": spec["type"],
                "base_model": base_model,
                "base_scaler_bundle": base_scaler_bundle,
                "classifier_model": classifier_model,
                "classifier_bundle": classifier_bundle,
            }
        return {
            "alias": alias,
            "type": spec["type"],
            "base_model": base_model,
            "base_scaler_bundle": base_scaler_bundle,
            "classifier_model": None,
            "classifier_bundle": None,
        }

    def available_model_options(self) -> list[dict[str, object]]:
        selection = resolve_model_selection()
        return [
            {
                "alias": alias,
                "description": spec.get("description", alias),
                "selected": alias == selection["active_model_alias"],
            }
            for alias, spec in selection["aliases"].items()
        ]

    def available_state_scheme_options(self) -> list[dict[str, object]]:
        selection = resolve_model_selection()
        return [
            {
                "scheme_key": scheme["scheme_key"],
                "class_count": scheme["class_count"],
                "description": scheme["description"],
                "labels": scheme["labels"],
                "selected": scheme["scheme_key"] == selection["active_state_scheme_key"],
                "recommended": scheme["scheme_key"] == selection["recommended_state_scheme_key"],
            }
            for scheme in selection["available_state_schemes"]
        ]

    def _load_json(self, path: Path) -> dict:
        if path.exists():
            with open(path, "r", encoding="utf-8") as metrics_file:
                return json.load(metrics_file)
        return {}

    def model_runtime_summary(self) -> dict[str, Any]:
        selection = resolve_model_selection()
        active_metrics_path = self.active_artifact_paths()[2]
        exploration_summary = self._load_json(STATE_SCHEME_EXPLORATION_PATH)
        scheme_metrics = self._load_json(classifier_artifact_paths(selection["active_state_scheme_key"])[2])
        return {
            "active_alias": selection["active_model_alias"],
            "active_description": selection["active_spec"].get("description", ""),
            "active_state_scheme_key": selection["active_state_scheme_key"],
            "active_state_scheme": selection["active_state_scheme"],
            "recommended_state_scheme_key": selection["recommended_state_scheme_key"],
            "recommended_state_scheme": selection["recommended_state_scheme"],
            "active_metrics": self._load_json(active_metrics_path),
            "production_metrics": self._load_json(PRODUCTION_METRICS_PATH),
            "active_state_scheme_metrics": scheme_metrics,
            "state_classifier_metrics": scheme_metrics,
            "state_scheme_exploration": exploration_summary,
            "available_models": self.available_model_options(),
            "available_state_schemes": self.available_state_scheme_options(),
        }

    def _station_history_frame(self, station_id: int) -> pd.DataFrame:
        station_frame = self.dataset[self.dataset["ysu_id"] == station_id].copy()
        if len(station_frame) < 48:
            raise ValueError(f"Station {station_id} does not have 48 hours of history")
        return station_frame.sort_values("hour").reset_index(drop=True)

    def _latest_station_frame(self, station_id: int) -> pd.DataFrame:
        return self._station_history_frame(station_id).tail(48)

    def _latest_runtime_inventory(self, station_ids: List[int]) -> np.ndarray:
        inventory_map: Dict[int, float] = {}
        from bike_dispatch_platform.data_process.models import ParkingSpotRealTime

        latest_time = ParkingSpotRealTime.objects.order_by("-collect_time").values_list("collect_time", flat=True).first()
        if latest_time:
            latest_rows = ParkingSpotRealTime.objects.filter(collect_time=latest_time).select_related("parking_spot")
            inventory_map = {row.parking_spot.ysu_id: float(row.parked_count) for row in latest_rows}

        inventories = []
        for station_id in station_ids:
            if station_id in inventory_map:
                inventories.append(inventory_map[station_id])
            else:
                station_frame = self._latest_station_frame(station_id)
                inventories.append(float(station_frame.iloc[-1]["inventory"]))
        return np.asarray(inventories, dtype=float)

    def _model_version(self) -> str:
        alias = self.active_model_alias()
        if alias == "t1_state_classifier":
            classifier_path = self.active_artifact_paths()[0]
            return (
                f"{alias}:{self.active_state_scheme_key()}:"
                f"{classifier_path.stem}@{classifier_path.stat().st_mtime_ns}|base@{PRODUCTION_MODEL_PATH.stat().st_mtime_ns}"
            )
        return f"production:{PRODUCTION_MODEL_PATH.stem}@{PRODUCTION_MODEL_PATH.stat().st_mtime_ns}"

    def _predict_numeric_matrix(
        self,
        station_ids: List[int],
        station_history_frames: Dict[int, pd.DataFrame],
        base_model: tf.keras.Model,
        base_scaler_bundle: dict,
    ) -> np.ndarray:
        feature_scaler = base_scaler_bundle["feature_scaler"]
        target_scaler = base_scaler_bundle["target_scaler"]
        feature_columns = base_scaler_bundle["feature_columns"]

        inputs = []
        for station_id in station_ids:
            station_frame = station_history_frames[station_id].tail(48)
            feature_window = station_frame[feature_columns].to_numpy(dtype=np.float32)
            inputs.append(feature_scaler.transform(feature_window))
        inputs = np.asarray(inputs, dtype=np.float32)
        scaled_predictions = base_model.predict(inputs, verbose=0)
        return target_scaler.inverse_transform(scaled_predictions.reshape(-1, 1)).reshape(scaled_predictions.shape)

    def _predict_state_vector(
        self,
        station_queryset: List[ParkingSpot],
        station_history_frames: Dict[int, pd.DataFrame],
        classifier_model: tf.keras.Model,
        classifier_bundle: dict,
    ) -> tuple[np.ndarray, List[int], List[List[float]]]:
        scaler = classifier_bundle["feature_scaler"]
        feature_windows = []
        for station in station_queryset:
            history_frame = station_history_frames[station.ysu_id]
            feature_windows.append(build_state_feature_window(history_frame))
        features = np.asarray(feature_windows, dtype=np.float32)
        scaled_features = scaler.transform(features.reshape(-1, features.shape[-1])).reshape(features.shape).astype(np.float32)
        probabilities = classifier_model.predict(scaled_features, verbose=0)
        states = np.argmax(probabilities, axis=1).astype(int).tolist()
        return probabilities, states, probabilities.round(6).tolist()

    def _state_payload(
        self,
        *,
        station: ParkingSpot,
        state_index: int,
        inventory_value: float,
    ) -> dict[str, object]:
        scheme_key = self.active_state_scheme_key()
        return {
            "t_plus_1_state_index": int(state_index),
            "t_plus_1_state_code": state_code(state_index, scheme_key=scheme_key),
            "t_plus_1_state_label": state_label(state_index, scheme_key=scheme_key),
            "t_plus_1_state_color": state_color(state_index, scheme_key=scheme_key),
            "t_plus_1_state_scheme_key": scheme_key,
            "t_plus_1_state_range": state_range_text(
                state_index,
                low_warning_threshold=station.low_warning_threshold,
                high_warning_threshold=station.high_warning_threshold,
                max_capacity=station.max_capacity,
                scheme_key=scheme_key,
            ),
            "t_plus_1_state_midpoint": round(float(inventory_value), 2),
        }

    def _build_station_payload(
        self,
        *,
        station: ParkingSpot,
        timestamps: List[str],
        net_flows: List[float],
        inventories: List[float],
        state_payload: dict[str, object],
    ) -> Dict[str, object]:
        t_plus_1_prediction = float(net_flows[0]) if net_flows else 0.0
        t_plus_1_inventory = float(inventories[0]) if inventories else float(station.initial_inventory)
        t_plus_1_gap = float(station.initial_inventory) - t_plus_1_inventory
        return {
            "station_id": station.ysu_id,
            "station_name": station.spot_name,
            "timestamps": timestamps,
            "predictions": net_flows,
            "inventory_predictions": inventories,
            "inventories": inventories,
            "decision_basis_hour": timestamps[0] if timestamps else None,
            "t_plus_1_prediction": round(t_plus_1_prediction, 4),
            "t_plus_1_inventory": round(t_plus_1_inventory, 4),
            "t_plus_1_gap": round(t_plus_1_gap, 4),
            "summary": {
                "total_abs_demand": round(float(sum(abs(value) for value in net_flows)), 4),
                "peak_abs_demand": round(float(max((abs(value) for value in net_flows), default=0.0)), 4),
                "t_plus_1_gap": round(t_plus_1_gap, 4),
            },
            **state_payload,
        }

    def generate_predictions(self, force: bool = False) -> PredictionBatch:
        sync_parking_spots()
        settings_obj = get_runtime_settings()
        artifacts = self.load_artifacts()
        base_model = artifacts["base_model"]
        base_scaler_bundle = artifacts["base_scaler_bundle"]
        classifier_model = artifacts["classifier_model"]
        classifier_bundle = artifacts["classifier_bundle"]

        batch_time = timezone.now().replace(minute=0, second=0, microsecond=0)
        model_version = self._model_version()
        if settings_obj.model_version != model_version:
            settings_obj.model_version = model_version
            settings_obj.save(update_fields=["model_version", "updated_at"])

        if not force:
            existing = StationPrediction.objects.filter(batch_time=batch_time).select_related("station")
            if existing.count() == STATION_COUNT * PREDICTION_HORIZON_HOURS:
                payloads: Dict[int, Dict[str, object]] = {}
                for row in existing.order_by("station__ysu_id", "prediction_hour"):
                    payload = payloads.setdefault(
                        row.station.ysu_id,
                        {
                            "station_id": row.station.ysu_id,
                            "station_name": row.station.spot_name,
                            "timestamps": [],
                            "predictions": [],
                            "inventory_predictions": [],
                        },
                    )
                    payload["timestamps"].append(row.prediction_hour.isoformat())
                    payload["predictions"].append(float(row.net_flow_prediction))
                    payload["inventory_predictions"].append(float(row.inventory_prediction))
                    payload["inventories"] = payload["inventory_predictions"]
                for station_id, payload in list(payloads.items()):
                    station = ParkingSpot.objects.get(ysu_id=station_id)
                    predicted_inventory = float(payload["inventory_predictions"][0])
                    predicted_state = classify_inventory_state(
                        predicted_inventory,
                        station.low_warning_threshold,
                        station.high_warning_threshold,
                        station.max_capacity,
                    )
                    payloads[station_id] = self._build_station_payload(
                        station=station,
                        timestamps=payload["timestamps"],
                        net_flows=payload["predictions"],
                        inventories=payload["inventory_predictions"],
                        state_payload=self._state_payload(
                            station=station,
                            state_index=predicted_state,
                            inventory_value=predicted_inventory,
                        ),
                    )
                return PredictionBatch(
                    batch_time=pd.Timestamp(batch_time),
                    model_version=model_version,
                    station_payloads=payloads,
                )

        station_queryset = list(ParkingSpot.objects.filter(is_active=True).order_by("ysu_id"))
        if len(station_queryset) != STATION_COUNT:
            raise ValueError(f"Expected {STATION_COUNT} active stations, got {len(station_queryset)}")

        station_ids = [station.ysu_id for station in station_queryset]
        station_history_frames = {station_id: self._station_history_frame(station_id) for station_id in station_ids}
        current_inventory = self._latest_runtime_inventory(station_ids)
        prediction_array = self._predict_numeric_matrix(station_ids, station_history_frames, base_model, base_scaler_bundle)
        active_scheme_key = self.active_state_scheme_key()

        predicted_state_payloads: Dict[int, dict[str, object]] = {}
        if classifier_model is not None and classifier_bundle is not None:
            _, predicted_states, probabilities = self._predict_state_vector(
                station_queryset,
                station_history_frames,
                classifier_model,
                classifier_bundle,
            )
            desired_inventory = []
            for station, predicted_state in zip(station_queryset, predicted_states):
                midpoint = state_midpoint_inventory(
                    predicted_state,
                    low_warning_threshold=station.low_warning_threshold,
                    high_warning_threshold=station.high_warning_threshold,
                    max_capacity=station.max_capacity,
                    scheme_key=active_scheme_key,
                )
                desired_inventory.append(midpoint)
            desired_inventory = np.asarray(desired_inventory, dtype=float)
            balanced_inventory = _rebalance_vector(
                desired_inventory,
                mins=np.zeros_like(desired_inventory),
                maxs=np.asarray([station.max_capacity for station in station_queryset], dtype=float),
            )
            prediction_array[:, 0] = balanced_inventory - current_inventory
            for index, station in enumerate(station_queryset):
                predicted_state_payloads[station.ysu_id] = {
                    **self._state_payload(
                        station=station,
                        state_index=predicted_states[index],
                        inventory_value=float(balanced_inventory[index]),
                    ),
                    "t_plus_1_state_probabilities": probabilities[index],
                }

        capacities = np.asarray([station.max_capacity * 1.5 for station in station_queryset], dtype=float)
        inventory_paths = np.zeros_like(prediction_array)
        running_inventory = current_inventory.copy()
        for hour_index in range(PREDICTION_HORIZON_HOURS):
            projected = running_inventory + prediction_array[:, hour_index]
            running_inventory = _rebalance_vector(projected, np.zeros_like(capacities), capacities)
            inventory_paths[:, hour_index] = running_inventory

        StationPrediction.objects.filter(batch_time=batch_time).delete()
        prediction_records: List[StationPrediction] = []
        payloads: Dict[int, Dict[str, object]] = {}

        for station_index, station in enumerate(station_queryset):
            timestamps: List[str] = []
            net_flows: List[float] = []
            inventories: List[float] = []
            for offset in range(PREDICTION_HORIZON_HOURS):
                prediction_hour = batch_time + pd.Timedelta(hours=offset + 1)
                net_flow = float(prediction_array[station_index, offset])
                inventory_value = float(inventory_paths[station_index, offset])
                prediction_records.append(
                    StationPrediction(
                        station=station,
                        batch_time=batch_time,
                        prediction_hour=prediction_hour,
                        net_flow_prediction=net_flow,
                        inventory_prediction=inventory_value,
                        model_version=model_version,
                    )
                )
                timestamps.append(prediction_hour.isoformat())
                net_flows.append(net_flow)
                inventories.append(inventory_value)

            state_payload = predicted_state_payloads.get(station.ysu_id)
            if state_payload is None:
                predicted_inventory = inventories[0]
                predicted_state = classify_inventory_state(
                    predicted_inventory,
                    station.low_warning_threshold,
                    station.high_warning_threshold,
                    station.max_capacity,
                    scheme_key=active_scheme_key,
                )
                state_payload = self._state_payload(
                    station=station,
                    state_index=predicted_state,
                    inventory_value=predicted_inventory,
                )

            payloads[station.ysu_id] = self._build_station_payload(
                station=station,
                timestamps=timestamps,
                net_flows=net_flows,
                inventories=inventories,
                state_payload=state_payload,
            )

        if prediction_records:
            StationPrediction.objects.bulk_create(prediction_records, batch_size=1000)

        return PredictionBatch(
            batch_time=pd.Timestamp(batch_time),
            model_version=model_version,
            station_payloads=payloads,
        )

    def _recent_history_indices(self, station_frame: pd.DataFrame, hours: int) -> List[int]:
        max_end_index = len(station_frame) - 1
        start_index = max(INPUT_WINDOW_HOURS, len(station_frame) - hours)
        return list(range(start_index, max_end_index + 1))

    def _predict_production_inventory(self, station_frame: pd.DataFrame, target_index: int) -> float:
        base_model, base_scaler_bundle = self._load_base_model_assets()
        feature_scaler = base_scaler_bundle["feature_scaler"]
        target_scaler = base_scaler_bundle["target_scaler"]
        feature_columns = base_scaler_bundle["feature_columns"]
        feature_window = station_frame.iloc[target_index - INPUT_WINDOW_HOURS : target_index][feature_columns].to_numpy(dtype=np.float32)
        scaled_window = feature_scaler.transform(feature_window).reshape(1, INPUT_WINDOW_HOURS, len(feature_columns))
        predicted_scaled = base_model.predict(scaled_window, verbose=0)[0, 0]
        predicted_net_flow = float(target_scaler.inverse_transform(np.array([[predicted_scaled]], dtype=np.float32))[0, 0])
        baseline_inventory = float(station_frame.iloc[target_index - 1]["inventory"])
        return float(max(0, baseline_inventory + predicted_net_flow))

    def _predict_classifier_inventory(self, station_frame: pd.DataFrame, target_index: int) -> tuple[float, int]:
        classifier_model, classifier_bundle = self._load_state_classifier_assets()
        history_frame = station_frame.iloc[:target_index].copy()
        feature_window = build_state_feature_window(history_frame)
        scaler = classifier_bundle["feature_scaler"]
        scaled_window = scaler.transform(feature_window).reshape(1, INPUT_WINDOW_HOURS, len(classifier_bundle["feature_columns"]))
        probabilities = classifier_model.predict(scaled_window, verbose=0)[0]
        predicted_state = int(np.argmax(probabilities))
        target_row = station_frame.iloc[target_index]
        midpoint = state_midpoint_inventory(
            predicted_state,
            low_warning_threshold=float(target_row["low_warning_threshold"]),
            high_warning_threshold=float(target_row["high_warning_threshold"]),
            max_capacity=float(target_row["max_capacity"]),
            scheme_key=self.active_state_scheme_key(),
        )
        return float(midpoint), predicted_state

    def get_compare_response(self, station_id: int, hours: int = 48) -> Dict[str, object]:
        hours = 24 if int(hours) == 24 else 48
        station = ParkingSpot.objects.get(ysu_id=station_id)
        station_frame = self._station_history_frame(station_id)
        indices = self._recent_history_indices(station_frame, hours)
        timestamps: List[str] = []
        actual_values: List[float] = []
        predicted_values: List[float] = []
        actual_states: List[str] = []
        predicted_states: List[str] = []
        predicted_state_colors: List[str] = []
        state_ranges: List[str] = []

        active_alias = self.active_model_alias()
        scheme_key = self.active_state_scheme_key()
        display_end_time = timezone.now().replace(minute=0, second=0, microsecond=0)
        display_start_time = display_end_time - pd.Timedelta(hours=len(indices) - 1)
        display_times = [display_start_time + pd.Timedelta(hours=offset) for offset in range(len(indices))]

        for offset, target_index in enumerate(indices):
            target_row = station_frame.iloc[target_index]
            actual_inventory = float(target_row["inventory"])
            actual_state = classify_inventory_state(
                actual_inventory,
                float(target_row["low_warning_threshold"]),
                float(target_row["high_warning_threshold"]),
                float(target_row["max_capacity"]),
                scheme_key=scheme_key,
            )

            if active_alias == "t1_state_classifier":
                predicted_inventory, predicted_state = self._predict_classifier_inventory(station_frame, target_index)
            else:
                predicted_inventory = self._predict_production_inventory(station_frame, target_index)
                predicted_state = classify_inventory_state(
                    predicted_inventory,
                    float(target_row["low_warning_threshold"]),
                    float(target_row["high_warning_threshold"]),
                    float(target_row["max_capacity"]),
                    scheme_key=scheme_key,
                )

            timestamps.append(pd.Timestamp(display_times[offset]).isoformat())
            actual_values.append(round(actual_inventory, 2))
            predicted_values.append(round(predicted_inventory, 2))
            actual_states.append(state_label(actual_state, scheme_key=scheme_key))
            predicted_states.append(state_label(predicted_state, scheme_key=scheme_key))
            predicted_state_colors.append(state_color(predicted_state, scheme_key=scheme_key))
            state_ranges.append(
                state_range_text(
                    predicted_state,
                    low_warning_threshold=float(target_row["low_warning_threshold"]),
                    high_warning_threshold=float(target_row["high_warning_threshold"]),
                    max_capacity=float(target_row["max_capacity"]),
                    scheme_key=scheme_key,
                )
            )

        return {
            "station_id": station.ysu_id,
            "station_name": station.spot_name,
            "model_alias": active_alias,
            "state_scheme_key": scheme_key,
            "state_scheme": get_state_scheme(scheme_key),
            "hours": hours,
            "timestamps": timestamps,
            "actual_values": actual_values,
            "predicted_values": predicted_values,
            "actual_states": actual_states,
            "predicted_states": predicted_states,
            "predicted_state_colors": predicted_state_colors,
            "state_ranges": state_ranges,
        }

    def get_batch_response(self, force: bool = False) -> Dict[str, object]:
        batch = self.generate_predictions(force=force)
        runtime_summary = self.model_runtime_summary()
        settings_obj = get_runtime_settings()
        return {
            "batch_time": batch.batch_time.isoformat(),
            "model_version": batch.model_version,
            "model_alias": runtime_summary["active_alias"],
            "model_description": runtime_summary["active_description"],
            "metrics": {
                **runtime_summary["active_metrics"],
                "refresh_seconds": settings_obj.dashboard_refresh_seconds,
            },
            "model_runtime_summary": runtime_summary,
            "stations": [batch.station_payloads[key] for key in sorted(batch.station_payloads)],
        }


station_prediction_service = StationPredictionService()
