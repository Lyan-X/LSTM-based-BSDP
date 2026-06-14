"""SRS-compliant parallel training pipeline for station-level 48-hour net-flow forecasting."""

from __future__ import annotations

import json
import pickle
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Tuple

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import tensorflow as tf
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.preprocessing import MinMaxScaler
from tensorflow.keras import Sequential
from tensorflow.keras.layers import LSTM, Dense, Dropout
from tensorflow.keras.utils import Sequence

from bike_dispatch_platform.demand_prediction.services.calendar_features import attach_temporal_features


BASE_DIR = Path(__file__).resolve().parent
DATASET_PATH = BASE_DIR / "ysu_62_stations_hourly_core_dataset.csv"
MODEL_ASSETS_DIR = BASE_DIR / "bike_dispatch_platform" / "demand_prediction" / "model_assets"

STATION_COUNT = 62
INPUT_WINDOW_HOURS = 48
OUTPUT_WINDOW_HOURS = 48
TRAIN_RATIO = 0.7
VALIDATION_RATIO = 0.2
WINDOW_STRIDE_HOURS = 24
FEATURE_COLUMNS = [
    "inflow",
    "outflow",
    "net_flow",
    "hour_of_day",
    "day_of_week",
    "is_holiday",
    "hour_sin",
    "hour_cos",
    "weekday_sin",
    "weekday_cos",
]
TARGET_COLUMN = "net_flow"
MODEL_FILENAME = "bike_sharing_lstm_model_srs.keras"
SCALER_FILENAME = "scaler_srs.pkl"
METRICS_FILENAME = "model_metrics_srs.json"
LOSS_CURVE_FILENAME = "training_loss_curve_srs.png"
PREDICTION_CURVE_FILENAME = "sample_prediction_curve_srs.png"


def configure_runtime() -> str:
    gpus = tf.config.list_physical_devices("GPU")
    if not gpus:
        raise RuntimeError("SRS 并行训练脚本要求使用 GPU 环境。")
    for gpu in gpus:
        tf.config.experimental.set_memory_growth(gpu, True)
    return "gpu"


@dataclass(frozen=True)
class StationSeries:
    station_id: int
    hours: np.ndarray
    features: np.ndarray
    targets: np.ndarray


@dataclass(frozen=True)
class DatasetSplits:
    train_samples: List[Tuple[int, int]]
    validation_samples: List[Tuple[int, int]]
    test_samples: List[Tuple[int, int]]
    train_end_hour: pd.Timestamp
    validation_end_hour: pd.Timestamp


class WindowSequence(Sequence):
    def __init__(
        self,
        station_series: Dict[int, StationSeries],
        sample_index: List[Tuple[int, int]],
        feature_scaler: MinMaxScaler,
        target_scaler: MinMaxScaler,
        batch_size: int = 32,
    ) -> None:
        self.station_series = station_series
        self.sample_index = sample_index
        self.feature_scaler = feature_scaler
        self.target_scaler = target_scaler
        self.batch_size = batch_size

    def __len__(self) -> int:
        return int(np.ceil(len(self.sample_index) / self.batch_size))

    def __getitem__(self, idx: int) -> Tuple[np.ndarray, np.ndarray]:
        batch_items = self.sample_index[idx * self.batch_size : (idx + 1) * self.batch_size]
        features_batch: List[np.ndarray] = []
        targets_batch: List[np.ndarray] = []

        for station_id, end_index in batch_items:
            series = self.station_series[station_id]
            feature_window = series.features[end_index - INPUT_WINDOW_HOURS : end_index]
            target_window = series.targets[end_index : end_index + OUTPUT_WINDOW_HOURS]

            scaled_features = self.feature_scaler.transform(feature_window)
            scaled_targets = self.target_scaler.transform(target_window.reshape(-1, 1)).reshape(-1)
            features_batch.append(scaled_features.astype(np.float32))
            targets_batch.append(scaled_targets.astype(np.float32))

        return np.asarray(features_batch, dtype=np.float32), np.asarray(targets_batch, dtype=np.float32)


class SRSTrainingPipeline:
    def __init__(self) -> None:
        self.dataset_path = DATASET_PATH
        self.model_assets_dir = MODEL_ASSETS_DIR
        self.device_type = configure_runtime()
        self.model_path = self.model_assets_dir / MODEL_FILENAME
        self.scaler_path = self.model_assets_dir / SCALER_FILENAME
        self.metrics_path = self.model_assets_dir / METRICS_FILENAME
        self.loss_curve_path = self.model_assets_dir / LOSS_CURVE_FILENAME
        self.prediction_curve_path = self.model_assets_dir / PREDICTION_CURVE_FILENAME
        self.feature_scaler = MinMaxScaler()
        self.target_scaler = MinMaxScaler()

    def load_dataset(self) -> pd.DataFrame:
        frame = pd.read_csv(self.dataset_path, parse_dates=["hour"])
        frame = attach_temporal_features(frame)
        frame = frame.sort_values(["ysu_id", "hour"]).reset_index(drop=True)
        if frame["ysu_id"].nunique() != STATION_COUNT:
            raise ValueError(f"Expected {STATION_COUNT} stations, got {frame['ysu_id'].nunique()}")
        return frame

    def build_station_series(self, frame: pd.DataFrame) -> Dict[int, StationSeries]:
        station_series: Dict[int, StationSeries] = {}
        for station_id in sorted(frame["ysu_id"].unique()):
            station_frame = frame[frame["ysu_id"] == station_id].copy()
            station_series[station_id] = StationSeries(
                station_id=int(station_id),
                hours=station_frame["hour"].to_numpy(),
                features=station_frame[FEATURE_COLUMNS].to_numpy(dtype=np.float32),
                targets=station_frame[TARGET_COLUMN].to_numpy(dtype=np.float32),
            )
        return station_series

    def split_by_time(self, station_series: Dict[int, StationSeries]) -> DatasetSplits:
        reference_hours = pd.to_datetime(station_series[1].hours)
        total_hours = len(reference_hours)
        train_end_idx = int(total_hours * TRAIN_RATIO)
        validation_end_idx = train_end_idx + int(total_hours * VALIDATION_RATIO)

        train_end_hour = pd.Timestamp(reference_hours[train_end_idx])
        validation_end_hour = pd.Timestamp(reference_hours[validation_end_idx])

        train_samples: List[Tuple[int, int]] = []
        validation_samples: List[Tuple[int, int]] = []
        test_samples: List[Tuple[int, int]] = []

        for station_id, series in station_series.items():
            series_hours = pd.to_datetime(series.hours)
            max_end_index = len(series.targets) - OUTPUT_WINDOW_HOURS + 1
            for end_index in range(INPUT_WINDOW_HOURS, max_end_index, WINDOW_STRIDE_HOURS):
                target_start_hour = pd.Timestamp(series_hours[end_index])
                if target_start_hour < train_end_hour:
                    train_samples.append((station_id, end_index))
                elif target_start_hour < validation_end_hour:
                    validation_samples.append((station_id, end_index))
                else:
                    test_samples.append((station_id, end_index))

        if not train_samples or not validation_samples or not test_samples:
            raise ValueError("Chronological 7:2:1 split failed to produce all three partitions")

        return DatasetSplits(
            train_samples=train_samples,
            validation_samples=validation_samples,
            test_samples=test_samples,
            train_end_hour=train_end_hour,
            validation_end_hour=validation_end_hour,
        )

    def fit_scalers(self, station_series: Dict[int, StationSeries], splits: DatasetSplits) -> None:
        feature_rows: List[np.ndarray] = []
        target_rows: List[np.ndarray] = []
        for station_id, end_index in splits.train_samples:
            series = station_series[station_id]
            feature_rows.append(series.features[end_index - INPUT_WINDOW_HOURS : end_index])
            target_rows.append(series.targets[end_index : end_index + OUTPUT_WINDOW_HOURS].reshape(-1, 1))

        self.feature_scaler.fit(np.concatenate(feature_rows, axis=0))
        self.target_scaler.fit(np.concatenate(target_rows, axis=0))

    def build_model(self) -> tf.keras.Model:
        model = Sequential(
            [
                LSTM(64, return_sequences=True, input_shape=(INPUT_WINDOW_HOURS, len(FEATURE_COLUMNS))),
                Dropout(0.2),
                LSTM(32),
                Dropout(0.2),
                Dense(64, activation="relu"),
                Dense(OUTPUT_WINDOW_HOURS),
            ]
        )
        model.compile(optimizer="adam", loss="mse")
        return model

    def collect_predictions(
        self,
        model: tf.keras.Model,
        sequence: WindowSequence,
    ) -> Tuple[np.ndarray, np.ndarray]:
        predictions: List[np.ndarray] = []
        labels: List[np.ndarray] = []

        for batch_index in range(len(sequence)):
            X_batch, y_batch = sequence[batch_index]
            batch_pred = model.predict(X_batch, verbose=0)
            predictions.append(batch_pred)
            labels.append(y_batch)

        y_pred_scaled = np.concatenate(predictions, axis=0)
        y_true_scaled = np.concatenate(labels, axis=0)
        y_pred = self.target_scaler.inverse_transform(y_pred_scaled.reshape(-1, 1)).reshape(y_pred_scaled.shape)
        y_true = self.target_scaler.inverse_transform(y_true_scaled.reshape(-1, 1)).reshape(y_true_scaled.shape)
        return y_true, y_pred

    def evaluate_partition(self, y_true: np.ndarray, y_pred: np.ndarray) -> Dict[str, float]:
        flattened_true = y_true.reshape(-1)
        flattened_pred = y_pred.reshape(-1)
        t_plus_1_true = y_true[:, 0]
        t_plus_1_pred = y_pred[:, 0]
        nonzero_mask = np.abs(t_plus_1_true) > 1e-6
        if nonzero_mask.any():
            relative_accuracy = 1.0 - (
                np.abs(t_plus_1_pred[nonzero_mask] - t_plus_1_true[nonzero_mask])
                / np.maximum(np.abs(t_plus_1_true[nonzero_mask]), 1e-6)
            )
            t_plus_1_accuracy = float(np.clip(relative_accuracy, 0.0, 1.0).mean() * 100.0)
        else:
            t_plus_1_accuracy = 100.0
        return {
            "mae": float(mean_absolute_error(flattened_true, flattened_pred)),
            "rmse": float(np.sqrt(mean_squared_error(flattened_true, flattened_pred))),
            "r2": float(r2_score(flattened_true, flattened_pred)),
            "t_plus_1_mae": float(mean_absolute_error(t_plus_1_true, t_plus_1_pred)),
            "t_plus_1_rmse": float(np.sqrt(mean_squared_error(t_plus_1_true, t_plus_1_pred))),
            "t_plus_1_nonzero_accuracy": t_plus_1_accuracy,
        }

    def save_artifacts(
        self,
        model: tf.keras.Model,
        history: tf.keras.callbacks.History,
        sample_true: np.ndarray,
        sample_pred: np.ndarray,
        metrics: Dict[str, object],
    ) -> None:
        self.model_assets_dir.mkdir(parents=True, exist_ok=True)
        model.save(self.model_path)

        with open(self.scaler_path, "wb") as scaler_file:
            pickle.dump(
                {
                    "feature_scaler": self.feature_scaler,
                    "target_scaler": self.target_scaler,
                    "feature_columns": FEATURE_COLUMNS,
                    "target_column": TARGET_COLUMN,
                },
                scaler_file,
            )

        with open(self.metrics_path, "w", encoding="utf-8") as metrics_file:
            json.dump(metrics, metrics_file, ensure_ascii=False, indent=2)

        plt.figure(figsize=(10, 5))
        plt.plot(history.history["loss"], label="train_loss")
        plt.plot(history.history["val_loss"], label="val_loss")
        plt.xlabel("epoch")
        plt.ylabel("mse_loss")
        plt.title("SRS LSTM Training Loss")
        plt.legend()
        plt.tight_layout()
        plt.savefig(self.loss_curve_path, dpi=200)
        plt.close()

        plt.figure(figsize=(12, 5))
        plt.plot(sample_true.reshape(-1), label="actual_net_flow")
        plt.plot(sample_pred.reshape(-1), label="predicted_net_flow")
        plt.xlabel("forecast_hour")
        plt.ylabel("net_flow")
        plt.title("SRS Sample 48-Hour Prediction")
        plt.legend()
        plt.tight_layout()
        plt.savefig(self.prediction_curve_path, dpi=200)
        plt.close()

    def run(self) -> Dict[str, object]:
        start_time = time.time()
        dataset = self.load_dataset()
        station_series = self.build_station_series(dataset)
        splits = self.split_by_time(station_series)
        self.fit_scalers(station_series, splits)

        train_sequence = WindowSequence(station_series, splits.train_samples, self.feature_scaler, self.target_scaler)
        validation_sequence = WindowSequence(
            station_series,
            splits.validation_samples,
            self.feature_scaler,
            self.target_scaler,
        )
        test_sequence = WindowSequence(station_series, splits.test_samples, self.feature_scaler, self.target_scaler)

        model = self.build_model()
        history = model.fit(
            train_sequence,
            validation_data=validation_sequence,
            epochs=50,
            shuffle=False,
            verbose=1,
        )

        train_true, train_pred = self.collect_predictions(model, train_sequence)
        validation_true, validation_pred = self.collect_predictions(model, validation_sequence)
        test_true, test_pred = self.collect_predictions(model, test_sequence)

        metrics = {
            "device": self.device_type,
            "dataset_path": str(self.dataset_path),
            "station_count": STATION_COUNT,
            "input_window_hours": INPUT_WINDOW_HOURS,
            "output_window_hours": OUTPUT_WINDOW_HOURS,
            "window_stride_hours": WINDOW_STRIDE_HOURS,
            "feature_columns": FEATURE_COLUMNS,
            "split": {
                "train": len(splits.train_samples),
                "validation": len(splits.validation_samples),
                "test": len(splits.test_samples),
            },
            "train_end_hour": splits.train_end_hour.isoformat(),
            "validation_end_hour": splits.validation_end_hour.isoformat(),
            "metrics": {
                "train": self.evaluate_partition(train_true, train_pred),
                "validation": self.evaluate_partition(validation_true, validation_pred),
                "test": self.evaluate_partition(test_true, test_pred),
            },
            "training_seconds": round(time.time() - start_time, 2),
        }

        self.save_artifacts(model, history, test_true[:1], test_pred[:1], metrics)
        return metrics


if __name__ == "__main__":
    pipeline = SRSTrainingPipeline()
    training_metrics = pipeline.run()
    print(json.dumps(training_metrics, ensure_ascii=False, indent=2))
