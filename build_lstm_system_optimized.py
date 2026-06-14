"""Independent optimization trainer for 基于深度学习的城市共享单车调度需求预测与运维管理平台.

Redline compliance:
- only lives in the project root
- never mutates production code, data, or deployed assets unless --save-model is used manually
- optimized model keeps the same single-input / single-output shape as the production model
- input still follows the 48h->48h sliding-window logic on the compliant mapped dataset
"""

from __future__ import annotations

import argparse
import json
import pickle
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Tuple

import numpy as np
import pandas as pd
import tensorflow as tf
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.preprocessing import StandardScaler
from tensorflow.keras import Model, Sequential
from tensorflow.keras.callbacks import EarlyStopping, ReduceLROnPlateau
from tensorflow.keras.layers import (
    Add,
    Bidirectional,
    Conv1D,
    Dense,
    Dropout,
    GlobalAveragePooling1D,
    Input,
    LayerNormalization,
    LSTM,
    MultiHeadAttention,
)
from tensorflow.keras.optimizers import Adam
from tensorflow.keras.utils import Sequence as KerasSequence


BASE_DIR = Path(__file__).resolve().parent
DATASET_PATH = BASE_DIR / "ysu_62_stations_hourly_core_dataset.csv"
BASELINE_METRICS_PATH = (
    BASE_DIR / "bike_dispatch_platform" / "demand_prediction" / "model_assets" / "model_metrics.json"
)
DEFAULT_EXPORT_MODEL_PATH = BASE_DIR / "bike_sharing_lstm_model_optimized.keras"
DEFAULT_EXPORT_SCALER_PATH = BASE_DIR / "optimized_feature_scaler.pkl"

STATION_COUNT = 62
INPUT_WINDOW_HOURS = 48
OUTPUT_WINDOW_HOURS = 48
TRAIN_RATIO = 0.7
VALIDATION_RATIO = 0.2
WINDOW_STRIDE_HOURS = 24
LSTM_BATCH_SIZE = 128
BP_BATCH_SIZE = 256
LSTM_EPOCHS = 24
BP_EPOCHS = 20
TARGET_COLUMN = "net_flow"

# Only use columns that the current production service can already provide
# after loading the compliant CSV plus the built-in hour/weekday encodings.
COMPATIBLE_FEATURE_COLUMNS = [
    "ysu_id",
    "latitude",
    "longitude",
    "max_capacity",
    "initial_inventory",
    "low_warning_threshold",
    "high_warning_threshold",
    "inflow",
    "outflow",
    "net_flow",
    "inventory",
    "hour_sin",
    "hour_cos",
    "weekday_sin",
    "weekday_cos",
]


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


def configure_runtime() -> str:
    gpus = tf.config.list_physical_devices("GPU")
    if gpus:
        for gpu in gpus:
            tf.config.experimental.set_memory_growth(gpu, True)
        return "gpu"
    return "cpu"


class WindowSequence(KerasSequence):
    def __init__(
        self,
        station_series: Dict[int, StationSeries],
        sample_index: List[Tuple[int, int]],
        feature_scaler: StandardScaler,
        target_scaler: StandardScaler,
        batch_size: int,
        flatten: bool = False,
    ) -> None:
        self.station_series = station_series
        self.sample_index = sample_index
        self.feature_scaler = feature_scaler
        self.target_scaler = target_scaler
        self.batch_size = batch_size
        self.flatten = flatten

    def __len__(self) -> int:
        return int(np.ceil(len(self.sample_index) / self.batch_size))

    def __getitem__(self, idx: int):
        batch_items = self.sample_index[idx * self.batch_size : (idx + 1) * self.batch_size]
        feature_batch = []
        target_batch = []

        for station_id, end_index in batch_items:
            series = self.station_series[station_id]
            feature_window = series.features[end_index - INPUT_WINDOW_HOURS : end_index]
            target_window = series.targets[end_index : end_index + OUTPUT_WINDOW_HOURS]

            scaled_features = self.feature_scaler.transform(feature_window).astype(np.float32)
            if self.flatten:
                scaled_features = scaled_features.reshape(-1)
            scaled_targets = self.target_scaler.transform(target_window.reshape(-1, 1)).reshape(-1).astype(np.float32)
            feature_batch.append(scaled_features)
            target_batch.append(scaled_targets)

        return np.asarray(feature_batch, dtype=np.float32), np.asarray(target_batch, dtype=np.float32)


class CompatibleOptimizedPipeline:
    def __init__(self, save_model: bool = False) -> None:
        self.device_type = configure_runtime()
        self.save_model = save_model
        self.dataset_path = DATASET_PATH
        self.feature_columns = COMPATIBLE_FEATURE_COLUMNS
        self.feature_scaler = StandardScaler()
        self.target_scaler = StandardScaler()

    def baseline_metrics(self) -> Dict[str, object]:
        if not BASELINE_METRICS_PATH.exists():
            return {}
        with open(BASELINE_METRICS_PATH, "r", encoding="utf-8") as metrics_file:
            return json.load(metrics_file)

    def load_dataset(self) -> pd.DataFrame:
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
        station_series: Dict[int, StationSeries] = {}
        for station_id in sorted(frame["ysu_id"].unique()):
            station_frame = frame[frame["ysu_id"] == station_id].copy()
            station_series[station_id] = StationSeries(
                station_id=int(station_id),
                hours=station_frame["hour"].to_numpy(),
                features=station_frame[self.feature_columns].to_numpy(dtype=np.float32),
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
            raise ValueError("Chronological 7:2:1 split failed to produce all partitions")

        return DatasetSplits(
            train_samples=train_samples,
            validation_samples=validation_samples,
            test_samples=test_samples,
            train_end_hour=train_end_hour,
            validation_end_hour=validation_end_hour,
        )

    def fit_scalers(self, frame: pd.DataFrame, splits: DatasetSplits) -> None:
        train_frame = frame[frame["hour"] < splits.train_end_hour]
        self.feature_scaler.fit(train_frame[self.feature_columns].to_numpy(dtype=np.float32))
        self.target_scaler.fit(train_frame[[TARGET_COLUMN]].to_numpy(dtype=np.float32))

    def build_lstm_model(self) -> Model:
        input_layer = Input(shape=(INPUT_WINDOW_HOURS, len(self.feature_columns)), name="sequence_input")
        x = Conv1D(32, kernel_size=3, padding="same", activation="relu")(input_layer)
        x = Bidirectional(LSTM(96, return_sequences=True))(x)
        x = Dropout(0.2)(x)
        attention = MultiHeadAttention(num_heads=4, key_dim=24, dropout=0.1)(x, x)
        x = Add()([x, attention])
        x = LayerNormalization()(x)
        x = Bidirectional(LSTM(64, return_sequences=True))(x)
        x = Dropout(0.2)(x)
        x = GlobalAveragePooling1D()(x)
        x = Dense(128, activation="relu")(x)
        x = Dropout(0.2)(x)
        x = Dense(64, activation="relu")(x)
        x = Dropout(0.1)(x)
        output = Dense(OUTPUT_WINDOW_HOURS, name="forecast_output")(x)

        model = Model(inputs=input_layer, outputs=output, name="compatible_lstm_attention_model")
        model.compile(
            optimizer=Adam(learning_rate=5e-4),
            loss="mse",
            metrics=[tf.keras.metrics.MeanAbsoluteError(name="mae")],
        )
        return model

    def build_bp_model(self) -> Sequential:
        model = Sequential(
            [
                Input(shape=(INPUT_WINDOW_HOURS * len(self.feature_columns),)),
                Dense(512, activation="relu"),
                Dropout(0.2),
                Dense(256, activation="relu"),
                Dropout(0.2),
                Dense(128, activation="relu"),
                Dense(OUTPUT_WINDOW_HOURS),
            ],
            name="bp_baseline_model",
        )
        model.compile(
            optimizer=Adam(learning_rate=1e-3),
            loss="mse",
            metrics=[tf.keras.metrics.MeanAbsoluteError(name="mae")],
        )
        return model

    def collect_predictions(self, model: Model, sequence: WindowSequence) -> Tuple[np.ndarray, np.ndarray]:
        predictions = []
        labels = []
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
        return {
            "mae": float(mean_absolute_error(flattened_true, flattened_pred)),
            "rmse": float(np.sqrt(mean_squared_error(flattened_true, flattened_pred))),
            "r2": float(r2_score(flattened_true, flattened_pred)),
        }

    def export_optional_artifacts(self, model: Model) -> None:
        if not self.save_model:
            return
        model.save(DEFAULT_EXPORT_MODEL_PATH)
        with open(DEFAULT_EXPORT_SCALER_PATH, "wb") as scaler_file:
            pickle.dump(
                {
                    "feature_scaler": self.feature_scaler,
                    "target_scaler": self.target_scaler,
                    "feature_columns": self.feature_columns,
                    "target_column": TARGET_COLUMN,
                },
                scaler_file,
            )

    def run(self) -> Dict[str, object]:
        start_time = time.time()
        frame = self.load_dataset()
        station_series = self.build_station_series(frame)
        splits = self.split_by_time(station_series)
        self.fit_scalers(frame, splits)

        lstm_train_seq = WindowSequence(
            station_series, splits.train_samples, self.feature_scaler, self.target_scaler, LSTM_BATCH_SIZE, flatten=False
        )
        lstm_val_seq = WindowSequence(
            station_series,
            splits.validation_samples,
            self.feature_scaler,
            self.target_scaler,
            LSTM_BATCH_SIZE,
            flatten=False,
        )
        lstm_test_seq = WindowSequence(
            station_series, splits.test_samples, self.feature_scaler, self.target_scaler, LSTM_BATCH_SIZE, flatten=False
        )

        bp_train_seq = WindowSequence(
            station_series, splits.train_samples, self.feature_scaler, self.target_scaler, BP_BATCH_SIZE, flatten=True
        )
        bp_val_seq = WindowSequence(
            station_series,
            splits.validation_samples,
            self.feature_scaler,
            self.target_scaler,
            BP_BATCH_SIZE,
            flatten=True,
        )
        bp_test_seq = WindowSequence(
            station_series, splits.test_samples, self.feature_scaler, self.target_scaler, BP_BATCH_SIZE, flatten=True
        )

        lstm_model = self.build_lstm_model()
        common_callbacks = [
            EarlyStopping(monitor="val_loss", patience=5, restore_best_weights=True),
            ReduceLROnPlateau(monitor="val_loss", factor=0.5, patience=2, min_lr=1e-5),
        ]
        lstm_history = lstm_model.fit(
            lstm_train_seq,
            validation_data=lstm_val_seq,
            epochs=LSTM_EPOCHS,
            shuffle=False,
            callbacks=common_callbacks,
            verbose=1,
        )

        bp_model = self.build_bp_model()
        bp_history = bp_model.fit(
            bp_train_seq,
            validation_data=bp_val_seq,
            epochs=BP_EPOCHS,
            shuffle=False,
            callbacks=common_callbacks,
            verbose=1,
        )

        train_true, train_pred = self.collect_predictions(lstm_model, lstm_train_seq)
        validation_true, validation_pred = self.collect_predictions(lstm_model, lstm_val_seq)
        test_true, test_pred = self.collect_predictions(lstm_model, lstm_test_seq)

        _, bp_test_pred = self.collect_predictions(bp_model, bp_test_seq)
        _, bp_val_pred = self.collect_predictions(bp_model, bp_val_seq)
        _, bp_train_pred = self.collect_predictions(bp_model, bp_train_seq)

        optimized_metrics = {
            "train": self.evaluate_partition(train_true, train_pred),
            "validation": self.evaluate_partition(validation_true, validation_pred),
            "test": self.evaluate_partition(test_true, test_pred),
        }
        bp_metrics = {
            "train": self.evaluate_partition(train_true, bp_train_pred),
            "validation": self.evaluate_partition(validation_true, bp_val_pred),
            "test": self.evaluate_partition(test_true, bp_test_pred),
        }

        baseline = self.baseline_metrics()
        baseline_test = baseline.get("metrics", {}).get("test", {})
        optimized_test = optimized_metrics["test"]
        sample_true = test_true[0]
        sample_pred = test_pred[0]
        sample_abs_error = np.abs(sample_true - sample_pred)

        self.export_optional_artifacts(lstm_model)

        return {
            "device": self.device_type,
            "dataset_path": str(self.dataset_path),
            "station_count": STATION_COUNT,
            "feature_columns": self.feature_columns,
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
            "lstm_epochs_completed": len(lstm_history.history["loss"]),
            "bp_epochs_completed": len(bp_history.history["loss"]),
            "training_seconds": round(time.time() - start_time, 2),
            "baseline_test_metrics": baseline_test,
            "optimized_metrics": optimized_metrics,
            "bp_metrics": bp_metrics,
            "improvement": {
                "test_mae_delta": float(optimized_test["mae"] - baseline_test.get("mae", 0.0)),
                "test_rmse_delta": float(optimized_test["rmse"] - baseline_test.get("rmse", 0.0)),
                "test_r2_delta": float(optimized_test["r2"] - baseline_test.get("r2", 0.0)),
            },
            "sample_compare": {
                "actual_first_12": [round(float(v), 4) for v in sample_true[:12]],
                "predicted_first_12": [round(float(v), 4) for v in sample_pred[:12]],
                "absolute_error_first_12": [round(float(v), 4) for v in sample_abs_error[:12]],
                "sample_window_mae": float(np.mean(sample_abs_error)),
                "sample_window_rmse": float(np.sqrt(np.mean(np.square(sample_true - sample_pred)))),
            },
            "history_tail": {
                "lstm_loss": [round(float(v), 6) for v in lstm_history.history["loss"][-5:]],
                "lstm_val_loss": [round(float(v), 6) for v in lstm_history.history["val_loss"][-5:]],
                "bp_loss": [round(float(v), 6) for v in bp_history.history["loss"][-5:]],
                "bp_val_loss": [round(float(v), 6) for v in bp_history.history["val_loss"][-5:]],
            },
            "exported_model": str(DEFAULT_EXPORT_MODEL_PATH) if self.save_model else None,
            "exported_scaler": str(DEFAULT_EXPORT_SCALER_PATH) if self.save_model else None,
        }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Train a root-only optimized LSTM variant and BP baseline.")
    parser.add_argument(
        "--save-model",
        action="store_true",
        help="Optionally export a compatibility-preserving optimized model and scaler to the project root.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    pipeline = CompatibleOptimizedPipeline(save_model=args.save_model)
    result = pipeline.run()
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
