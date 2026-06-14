"""GPU-first LSTM training pipeline for station-level 48-hour net-flow forecasting."""

from __future__ import annotations

import json
import pickle
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Tuple

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


BASE_DIR = Path(__file__).resolve().parent
DATASET_PATH = BASE_DIR / "ysu_62_stations_hourly_core_dataset.csv"
MODEL_ASSETS_DIR = BASE_DIR / "bike_dispatch_platform" / "demand_prediction" / "model_assets"

STATION_COUNT = 62
INPUT_WINDOW_HOURS = 48
OUTPUT_WINDOW_HOURS = 48
TRAIN_RATIO = 0.7
VALIDATION_RATIO = 0.2
TEST_RATIO = 0.1
WINDOW_STRIDE_HOURS = 24
FEATURE_COLUMNS = [
    "inflow",
    "outflow",
    "net_flow",
    "hour_sin",
    "hour_cos",
    "weekday_sin",
    "weekday_cos",
]
TARGET_COLUMN = "net_flow"
MODEL_FILENAME = "bike_sharing_lstm_model.keras"
SCALER_FILENAME = "scaler.pkl"
METRICS_FILENAME = "model_metrics.json"
LOSS_CURVE_FILENAME = "training_loss_curve.png"
PREDICTION_CURVE_FILENAME = "sample_prediction_curve.png"


def configure_runtime() -> str:
    """Require GPU training and enable memory growth."""

    gpus = tf.config.list_physical_devices("GPU")
    if not gpus:
        raise RuntimeError(
            "基于深度学习的城市共享单车调度需求预测与运维管理平台要求使用 RTX 3060 GPU 训练，"
            "当前 TensorFlow 未识别到 GPU。"
        )

    for gpu in gpus:
        tf.config.experimental.set_memory_growth(gpu, True)
    return "gpu"


@dataclass(frozen=True)
class StationSeries:
    """One station's chronological feature and target arrays."""

    station_id: int
    hours: np.ndarray
    features: np.ndarray
    targets: np.ndarray


@dataclass(frozen=True)
class DatasetSplits:
    """Sample index splits for training, validation, and test partitions."""

    train_samples: List[Tuple[int, int]]
    validation_samples: List[Tuple[int, int]]
    test_samples: List[Tuple[int, int]]
    train_end_hour: pd.Timestamp
    validation_end_hour: pd.Timestamp


class WindowSequence(Sequence):
    """Keras sequence that streams station windows from the compliant dataset."""

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


class LSTMTrainingPipeline:
    """Train and evaluate the station-level shared 48-hour LSTM."""

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
        """Load the compliant hourly core dataset and derive temporal features."""

        frame = pd.read_csv(self.dataset_path, parse_dates=["hour"])
        frame = frame.sort_values(["ysu_id", "hour"]).reset_index(drop=True)
        if frame["ysu_id"].nunique() != STATION_COUNT:
            raise ValueError(f"Expected {STATION_COUNT} stations, got {frame['ysu_id'].nunique()}")

        frame["hour_sin"] = np.sin(2 * np.pi * frame["hour"].dt.hour / 24.0)
        frame["hour_cos"] = np.cos(2 * np.pi * frame["hour"].dt.hour / 24.0)
        frame["weekday_sin"] = np.sin(2 * np.pi * frame["hour"].dt.dayofweek / 7.0)
        frame["weekday_cos"] = np.cos(2 * np.pi * frame["hour"].dt.dayofweek / 7.0)
        return frame

    def build_station_series(self, frame: pd.DataFrame) -> Dict[int, StationSeries]:
        """Prepare per-station feature arrays without materializing all windows."""

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
        """Split station samples chronologically using 7:2:1 hour boundaries."""

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
            raise ValueError("Chronological 7:2:1 split failed to produce all three dataset partitions")

        return DatasetSplits(
            train_samples=train_samples,
            validation_samples=validation_samples,
            test_samples=test_samples,
            train_end_hour=train_end_hour,
            validation_end_hour=validation_end_hour,
        )

    def fit_scalers(self, station_series: Dict[int, StationSeries], splits: DatasetSplits) -> None:
        """Fit feature and target scalers using the training partition only."""

        feature_rows: List[np.ndarray] = []
        target_rows: List[np.ndarray] = []
        for station_id, end_index in splits.train_samples:
            series = station_series[station_id]
            feature_rows.append(series.features[end_index - INPUT_WINDOW_HOURS : end_index])
            target_rows.append(series.targets[end_index : end_index + OUTPUT_WINDOW_HOURS].reshape(-1, 1))

        feature_matrix = np.concatenate(feature_rows, axis=0)
        target_matrix = np.concatenate(target_rows, axis=0)
        self.feature_scaler.fit(feature_matrix)
        self.target_scaler.fit(target_matrix)

    def build_model(self) -> tf.keras.Model:
        """Build the fixed LSTM architecture defined by the project constraints."""

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
        """Collect inverse-scaled predictions and labels from one dataset partition."""

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
        """Evaluate the full 48-hour horizon after inverse scaling."""

        flattened_true = y_true.reshape(-1)
        flattened_pred = y_pred.reshape(-1)
        return {
            "mae": float(mean_absolute_error(flattened_true, flattened_pred)),
            "rmse": float(np.sqrt(mean_squared_error(flattened_true, flattened_pred))),
            "r2": float(r2_score(flattened_true, flattened_pred)),
        }

    def save_artifacts(
        self,
        model: tf.keras.Model,
        history: tf.keras.callbacks.History,
        sample_true: np.ndarray,
        sample_pred: np.ndarray,
        metrics: Dict[str, object],
    ) -> None:
        """Save model assets and evaluation outputs to the fixed directory."""

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
        plt.title("LSTM Training Loss")
        plt.legend()
        plt.tight_layout()
        plt.savefig(self.loss_curve_path, dpi=200)
        plt.close()

        plt.figure(figsize=(12, 5))
        plt.plot(sample_true.reshape(-1), label="actual_net_flow")
        plt.plot(sample_pred.reshape(-1), label="predicted_net_flow")
        plt.xlabel("forecast_hour")
        plt.ylabel("net_flow")
        plt.title("Sample 48-Hour Prediction")
        plt.legend()
        plt.tight_layout()
        plt.savefig(self.prediction_curve_path, dpi=200)
        plt.close()

    def run(self) -> Dict[str, object]:
        """Execute the full GPU training pipeline."""

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
    pipeline = LSTMTrainingPipeline()
    training_metrics = pipeline.run()
    print(json.dumps(training_metrics, ensure_ascii=False, indent=2))
