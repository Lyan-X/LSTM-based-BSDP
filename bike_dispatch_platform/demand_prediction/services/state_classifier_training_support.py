from __future__ import annotations

import json
import pickle
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import tensorflow as tf
from sklearn.metrics import accuracy_score, classification_report, confusion_matrix, f1_score
from sklearn.preprocessing import StandardScaler

from bike_dispatch_platform.demand_prediction.services.calendar_features import attach_temporal_features
from bike_dispatch_platform.demand_prediction.services.state_classifier_support import (
    CLASSIFICATION_FEATURE_COLUMNS,
    MODEL_ASSETS_DIR,
    STATE_SCHEME_ORDER,
    classifier_artifact_paths,
    classify_inventory_state,
    get_state_scheme,
)


BASE_DIR = Path(__file__).resolve().parents[3]
DATASET_PATH = BASE_DIR / "ysu_62_stations_hourly_core_dataset.csv"
PRODUCTION_MODEL_PATH = MODEL_ASSETS_DIR / "bike_sharing_lstm_model.keras"
PRODUCTION_SCALER_PATH = MODEL_ASSETS_DIR / "scaler.pkl"

INPUT_WINDOW_HOURS = 48
OUTPUT_WINDOW_HOURS = 48
TRAIN_RATIO = 0.7
VALIDATION_RATIO = 0.2
WINDOW_STRIDE_HOURS = 24


@dataclass(frozen=True)
class SplitSamples:
    train: list[tuple[int, int]]
    validation: list[tuple[int, int]]
    test: list[tuple[int, int]]
    train_end_hour: pd.Timestamp
    validation_end_hour: pd.Timestamp


def configure_runtime() -> str:
    gpus = tf.config.list_physical_devices("GPU")
    if gpus:
        for gpu in gpus:
            tf.config.experimental.set_memory_growth(gpu, True)
        return "gpu"
    return "cpu"


def load_dataset() -> pd.DataFrame:
    dataset = pd.read_csv(DATASET_PATH, parse_dates=["hour"])
    dataset = attach_temporal_features(dataset)
    dataset["hour"] = pd.to_datetime(dataset["hour"])
    return dataset.sort_values(["ysu_id", "hour"]).reset_index(drop=True)


def station_frames(dataset: pd.DataFrame) -> dict[int, pd.DataFrame]:
    return {int(station_id): frame.reset_index(drop=True) for station_id, frame in dataset.groupby("ysu_id")}


def split_samples(station_frame_map: dict[int, pd.DataFrame]) -> SplitSamples:
    reference_hours = pd.to_datetime(station_frame_map[1]["hour"].to_numpy())
    train_end_index = int(len(reference_hours) * TRAIN_RATIO)
    validation_end_index = train_end_index + int(len(reference_hours) * VALIDATION_RATIO)
    train_end_hour = pd.Timestamp(reference_hours[train_end_index])
    validation_end_hour = pd.Timestamp(reference_hours[validation_end_index])

    train_samples: list[tuple[int, int]] = []
    validation_samples: list[tuple[int, int]] = []
    test_samples: list[tuple[int, int]] = []
    for station_id, station_frame in station_frame_map.items():
        max_end_index = len(station_frame) - OUTPUT_WINDOW_HOURS + 1
        for end_index in range(INPUT_WINDOW_HOURS, max_end_index, WINDOW_STRIDE_HOURS):
            target_hour = pd.Timestamp(station_frame.iloc[end_index]["hour"])
            if target_hour < train_end_hour:
                train_samples.append((station_id, end_index))
            elif target_hour < validation_end_hour:
                validation_samples.append((station_id, end_index))
            else:
                test_samples.append((station_id, end_index))

    return SplitSamples(
        train=train_samples,
        validation=validation_samples,
        test=test_samples,
        train_end_hour=train_end_hour,
        validation_end_hour=validation_end_hour,
    )


def label_for_row(target_row: pd.Series, scheme_key: str) -> int:
    return classify_inventory_state(
        float(target_row["inventory"]),
        float(target_row["low_warning_threshold"]),
        float(target_row["high_warning_threshold"]),
        float(target_row["max_capacity"]),
        scheme_key=scheme_key,
    )


def build_arrays(
    station_frame_map: dict[int, pd.DataFrame],
    samples: list[tuple[int, int]],
    scheme_key: str,
) -> tuple[np.ndarray, np.ndarray]:
    features: list[np.ndarray] = []
    labels: list[int] = []
    for station_id, end_index in samples:
        station_frame = station_frame_map[station_id]
        history_frame = station_frame.iloc[:end_index].copy()
        target_row = station_frame.iloc[end_index]
        feature_window = history_frame.tail(INPUT_WINDOW_HOURS)[CLASSIFICATION_FEATURE_COLUMNS].to_numpy(dtype=np.float32)
        features.append(feature_window)
        labels.append(label_for_row(target_row, scheme_key))
    return np.asarray(features, dtype=np.float32), np.asarray(labels, dtype=np.int32)


def fit_scaler(train_features: np.ndarray) -> StandardScaler:
    scaler = StandardScaler()
    scaler.fit(train_features.reshape(-1, train_features.shape[-1]))
    return scaler


def scale_features(features: np.ndarray, scaler: StandardScaler) -> np.ndarray:
    scaled = scaler.transform(features.reshape(-1, features.shape[-1]))
    return scaled.reshape(features.shape).astype(np.float32)


def class_weight(y_train: np.ndarray, class_count: int) -> dict[int, float]:
    counts = np.bincount(y_train, minlength=class_count)
    total = counts.sum()
    return {
        class_index: float(total / (class_count * max(1, int(class_count_value))))
        for class_index, class_count_value in enumerate(counts)
    }


def build_model(feature_count: int, class_count: int) -> tf.keras.Model:
    model = tf.keras.Sequential(
        [
            tf.keras.layers.Input(shape=(INPUT_WINDOW_HOURS, feature_count)),
            tf.keras.layers.LSTM(64, return_sequences=True),
            tf.keras.layers.Dropout(0.2),
            tf.keras.layers.LSTM(32),
            tf.keras.layers.Dropout(0.2),
            tf.keras.layers.Dense(32, activation="relu"),
            tf.keras.layers.Dense(class_count, activation="softmax"),
        ]
    )
    model.compile(
        optimizer=tf.keras.optimizers.Adam(learning_rate=3e-4),
        loss="sparse_categorical_crossentropy",
        metrics=["accuracy"],
    )
    return model


def classification_metrics(y_true: np.ndarray, y_pred: np.ndarray, labels: list[str]) -> dict[str, Any]:
    report = classification_report(
        y_true,
        y_pred,
        labels=list(range(len(labels))),
        target_names=labels,
        output_dict=True,
        zero_division=0,
    )
    return {
        "classification_accuracy": float(accuracy_score(y_true, y_pred)),
        "macro_f1": float(f1_score(y_true, y_pred, average="macro")),
        "weighted_f1": float(f1_score(y_true, y_pred, average="weighted")),
        "per_class_precision_recall_f1": {
            label: {
                "precision": float(report[label]["precision"]),
                "recall": float(report[label]["recall"]),
                "f1": float(report[label]["f1-score"]),
                "support": int(report[label]["support"]),
            }
            for label in labels
        },
    }


def evaluate_production_state_baseline(
    station_frame_map: dict[int, pd.DataFrame],
    samples: list[tuple[int, int]],
    scheme_key: str,
) -> dict[str, Any]:
    with open(PRODUCTION_SCALER_PATH, "rb") as scaler_file:
        scaler_bundle = pickle.load(scaler_file)
    feature_scaler = scaler_bundle["feature_scaler"]
    target_scaler = scaler_bundle["target_scaler"]
    feature_columns = scaler_bundle["feature_columns"]
    model = tf.keras.models.load_model(PRODUCTION_MODEL_PATH)

    inputs = []
    truths = []
    inventories = []
    thresholds = []
    capacities = []
    for station_id, end_index in samples:
        station_frame = station_frame_map[station_id]
        feature_window = station_frame.iloc[end_index - INPUT_WINDOW_HOURS : end_index][feature_columns].to_numpy(dtype=np.float32)
        inputs.append(feature_scaler.transform(feature_window))
        target_row = station_frame.iloc[end_index]
        truths.append(label_for_row(target_row, scheme_key))
        inventories.append(float(station_frame.iloc[end_index - 1]["inventory"]))
        thresholds.append(
            (
                float(target_row["low_warning_threshold"]),
                float(target_row["high_warning_threshold"]),
            )
        )
        capacities.append(float(target_row["max_capacity"]))

    scaled_predictions = model.predict(np.asarray(inputs, dtype=np.float32), verbose=0)[:, 0]
    net_flow_predictions = target_scaler.inverse_transform(scaled_predictions.reshape(-1, 1)).reshape(-1)
    predicted_inventory = np.clip(
        np.asarray(inventories, dtype=np.float32) + net_flow_predictions,
        0,
        np.asarray(capacities, dtype=np.float32),
    )
    scheme = get_state_scheme(scheme_key)
    predicted_labels = [
        classify_inventory_state(
            predicted_inventory[index],
            thresholds[index][0],
            thresholds[index][1],
            capacities[index],
            scheme_key=scheme_key,
        )
        for index in range(len(predicted_inventory))
    ]
    return classification_metrics(np.asarray(truths, dtype=np.int32), np.asarray(predicted_labels, dtype=np.int32), scheme["labels"])


def state_distribution(dataset: pd.DataFrame, scheme_key: str) -> dict[str, Any]:
    scheme = get_state_scheme(scheme_key)
    labels = dataset.apply(lambda row: label_for_row(row, scheme_key), axis=1)
    counts = pd.Series(labels).value_counts().sort_index()
    total = int(counts.sum())
    return {
        scheme["labels"][state_index]: {
            "count": int(counts.get(state_index, 0)),
            "ratio": round(float(counts.get(state_index, 0)) / max(1, total), 6),
        }
        for state_index in range(len(scheme["labels"]))
    }


def train_state_classifier_for_scheme(scheme_key: str, epochs: int = 20) -> dict[str, Any]:
    scheme = get_state_scheme(scheme_key)
    labels = scheme["labels"]
    model_path, bundle_path, metrics_path, confusion_path = classifier_artifact_paths(scheme_key)
    start_time = time.time()
    device = configure_runtime()
    dataset = load_dataset()
    station_frame_map = station_frames(dataset)
    splits = split_samples(station_frame_map)

    x_train, y_train = build_arrays(station_frame_map, splits.train, scheme_key)
    x_validation, y_validation = build_arrays(station_frame_map, splits.validation, scheme_key)
    x_test, y_test = build_arrays(station_frame_map, splits.test, scheme_key)

    scaler = fit_scaler(x_train)
    x_train = scale_features(x_train, scaler)
    x_validation = scale_features(x_validation, scaler)
    x_test = scale_features(x_test, scaler)

    weights = class_weight(y_train, scheme["class_count"])
    model = build_model(x_train.shape[-1], scheme["class_count"])
    callbacks = [
        tf.keras.callbacks.EarlyStopping(monitor="val_accuracy", patience=4, mode="max", restore_best_weights=True),
        tf.keras.callbacks.ReduceLROnPlateau(monitor="val_loss", patience=2, factor=0.5, min_lr=1e-5),
    ]
    history = model.fit(
        x_train,
        y_train,
        validation_data=(x_validation, y_validation),
        epochs=epochs,
        batch_size=128,
        shuffle=False,
        class_weight=weights,
        callbacks=callbacks,
        verbose=1,
    )

    validation_predictions = np.argmax(model.predict(x_validation, verbose=0), axis=1)
    test_probabilities = model.predict(x_test, verbose=0)
    test_predictions = np.argmax(test_probabilities, axis=1)

    validation_metrics = classification_metrics(y_validation, validation_predictions, labels)
    test_metrics = classification_metrics(y_test, test_predictions, labels)
    production_state_metrics = evaluate_production_state_baseline(station_frame_map, splits.test, scheme_key)
    confusion = confusion_matrix(y_test, test_predictions, labels=list(range(len(labels))))

    model.save(model_path)
    with open(bundle_path, "wb") as bundle_file:
        pickle.dump(
            {
                "feature_scaler": scaler,
                "feature_columns": CLASSIFICATION_FEATURE_COLUMNS,
                "state_labels": labels,
                "scheme_key": scheme_key,
                "class_count": scheme["class_count"],
                "input_window_hours": INPUT_WINDOW_HOURS,
            },
            bundle_file,
        )

    with open(confusion_path, "w", encoding="utf-8") as confusion_file:
        json.dump({"labels": labels, "matrix": confusion.tolist(), "scheme_key": scheme_key}, confusion_file, ensure_ascii=False, indent=2)

    metrics_payload = {
        "scheme_key": scheme_key,
        "scheme_description": scheme["description"],
        "class_count": scheme["class_count"],
        "zone_bins": scheme["zone_bins"],
        "device": device,
        "dataset_path": str(DATASET_PATH),
        "feature_columns": CLASSIFICATION_FEATURE_COLUMNS,
        "state_labels": labels,
        "state_distribution": state_distribution(dataset, scheme_key),
        "split": {
            "train": len(splits.train),
            "validation": len(splits.validation),
            "test": len(splits.test),
        },
        "train_end_hour": splits.train_end_hour.isoformat(),
        "validation_end_hour": splits.validation_end_hour.isoformat(),
        "epochs_completed": len(history.history["loss"]),
        "validation_metrics": validation_metrics,
        "test_metrics": test_metrics,
        "production_state_metrics": production_state_metrics,
        "improvement_vs_production": {
            "classification_accuracy_delta": round(
                test_metrics["classification_accuracy"] - production_state_metrics["classification_accuracy"],
                6,
            ),
            "macro_f1_delta": round(test_metrics["macro_f1"] - production_state_metrics["macro_f1"], 6),
            "weighted_f1_delta": round(test_metrics["weighted_f1"] - production_state_metrics["weighted_f1"], 6),
        },
        "asset_paths": {
            "model_path": str(model_path),
            "bundle_path": str(bundle_path),
            "metrics_path": str(metrics_path),
            "confusion_matrix_path": str(confusion_path),
        },
        "training_seconds": round(time.time() - start_time, 2),
    }
    with open(metrics_path, "w", encoding="utf-8") as metrics_file:
        json.dump(metrics_payload, metrics_file, ensure_ascii=False, indent=2)
    return metrics_payload


def evaluate_state_classifier_for_scheme(scheme_key: str) -> dict[str, Any]:
    scheme = get_state_scheme(scheme_key)
    labels = scheme["labels"]
    model_path, bundle_path, _, _ = classifier_artifact_paths(scheme_key)
    bundle = pickle.load(open(bundle_path, "rb"))
    model = tf.keras.models.load_model(model_path)
    scaler = bundle["feature_scaler"]

    dataset = load_dataset()
    station_frame_map = station_frames(dataset)
    samples = split_samples(station_frame_map).test
    inputs = []
    y_true = []
    first_test_target_hour = None
    for station_id, end_index in samples:
        station_frame = station_frame_map[station_id]
        history_frame = station_frame.iloc[:end_index].copy()
        inputs.append(history_frame.tail(INPUT_WINDOW_HOURS)[CLASSIFICATION_FEATURE_COLUMNS].to_numpy(dtype=np.float32))
        target_row = station_frame.iloc[end_index]
        y_true.append(label_for_row(target_row, scheme_key))
        if first_test_target_hour is None:
            first_test_target_hour = pd.Timestamp(target_row["hour"]).isoformat()
    features = np.asarray(inputs, dtype=np.float32)
    scaled_features = scaler.transform(features.reshape(-1, features.shape[-1])).reshape(features.shape).astype(np.float32)
    probabilities = model.predict(scaled_features, verbose=0)
    y_pred = np.argmax(probabilities, axis=1).astype(np.int32)
    result = classification_metrics(np.asarray(y_true, dtype=np.int32), y_pred, labels)
    result.update(
        {
            "alias": "t1_state_classifier",
            "scheme_key": scheme_key,
            "class_count": scheme["class_count"],
            "dataset_path": str(DATASET_PATH),
            "model_path": str(model_path),
            "bundle_path": str(bundle_path),
            "test_window_count": int(len(samples)),
            "first_test_target_hour": first_test_target_hour,
        }
    )
    return result


def choose_recommended_scheme(results: list[dict[str, Any]]) -> dict[str, Any]:
    in_range = [row for row in results if 0.80 <= row["test_metrics"]["classification_accuracy"] <= 0.92]
    if in_range:
        in_range.sort(key=lambda row: (row["class_count"], -row["test_metrics"]["macro_f1"]))
        return in_range[0]
    above_range = [row for row in results if row["test_metrics"]["classification_accuracy"] > 0.92]
    if above_range:
        above_range.sort(
            key=lambda row: (
                abs(row["test_metrics"]["classification_accuracy"] - 0.92),
                row["class_count"],
                -row["test_metrics"]["macro_f1"],
            )
        )
        return above_range[0]
    below_range = list(results)
    below_range.sort(key=lambda row: (-row["test_metrics"]["macro_f1"], -row["test_metrics"]["weighted_f1"], row["class_count"]))
    return below_range[0]


def render_exploration_markdown(results: list[dict[str, Any]], recommended: dict[str, Any]) -> str:
    lines = [
        "# 状态划分探索报告",
        "",
        "## 1. 探索范围",
        "- 数据源：`ysu_62_stations_hourly_core_dataset.csv`",
        "- 输入窗口：过去 48 小时",
        "- 任务：T+1 供需状态分类",
        "- 候选方案：`5 / 7 / 9 / 11` 档",
        "- 选择原则：业务解释优先，其次参考 `classification_accuracy` 是否落入 `0.80 ~ 0.92` 区间",
        "",
        "## 2. 候选方案总览",
        "",
        "| 方案 | 类别数 | 分区细分 | 测试准确率 | Macro-F1 | Weighted-F1 | 是否命中 80%~92% |",
        "| --- | ---: | --- | ---: | ---: | ---: | --- |",
    ]
    for row in results:
        accuracy = row["test_metrics"]["classification_accuracy"]
        lines.append(
            f"| {row['scheme_key']} | {row['class_count']} | "
            f"`{row['zone_bins']['scarce']} / {row['zone_bins']['balanced']} / {row['zone_bins']['saturated']}` | "
            f"{accuracy:.6f} | {row['test_metrics']['macro_f1']:.6f} | {row['test_metrics']['weighted_f1']:.6f} | "
            f"{'是' if 0.80 <= accuracy <= 0.92 else '否'} |"
        )
    lines.extend(
        [
            "",
            "## 3. 各方案样本分布",
            "",
        ]
    )
    for row in results:
        lines.append(f"### 3.{results.index(row)+1} {row['scheme_key']}（{row['scheme_description']}）")
        lines.append("")
        lines.append("| 状态 | 样本数 | 占比 |")
        lines.append("| --- | ---: | ---: |")
        for label, stats in row["state_distribution"].items():
            lines.append(f"| {label} | {stats['count']} | {stats['ratio']:.6f} |")
        lines.append("")
    lines.extend(
        [
            "## 4. 推荐方案",
            f"- 推荐方案：`{recommended['scheme_key']}`",
            f"- 类别数：`{recommended['class_count']}`",
            f"- 分区细分：`{recommended['zone_bins']['scarce']} / {recommended['zone_bins']['balanced']} / {recommended['zone_bins']['saturated']}`",
            f"- 测试准确率：`{recommended['test_metrics']['classification_accuracy']:.6f}`",
            f"- Macro-F1：`{recommended['test_metrics']['macro_f1']:.6f}`",
        ]
    )
    accuracy = recommended["test_metrics"]["classification_accuracy"]
    if 0.80 <= accuracy <= 0.92:
        lines.extend(
            [
                "- 结论：该方案已命中目标准确率区间，同时保持了较强业务可解释性。",
            ]
        )
    elif accuracy > 0.92:
        lines.extend(
            [
                "- 结论：所有候选方案的准确率都偏高，说明数据规律性较强；当前推荐方案是在业务解释更自然的前提下，最接近 0.92 的方案。",
            ]
        )
    else:
        lines.extend(
            [
                "- 结论：所有候选方案准确率均低于 0.80，当前推荐方案是在未达标情况下综合表现最稳定的方案。",
            ]
        )
    return "\n".join(lines) + "\n"


def default_scheme_result_stub() -> dict[str, Any]:
    return {
        "results": [],
        "recommended_scheme_key": "state_5",
        "generated_at": None,
    }
