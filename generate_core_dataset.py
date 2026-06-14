"""Generate the canonical 62-station hourly core dataset and Django fixtures."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List

import numpy as np
import pandas as pd

from station_info.master_data import (
    OFFICIAL_PROJECT_NAME,
    STATION_COUNT,
    TOTAL_SYSTEM_VEHICLES,
    build_station_mapping_frame,
    build_station_master_frame,
    export_master_data_assets,
)

BASE_DIR = Path(__file__).resolve().parent
RAW_DATASET_PATH = BASE_DIR / "bike_demand_research" / "dataset" / "daily_rent_detail.csv"
OUTPUT_DATASET_PATH = BASE_DIR / "ysu_62_stations_hourly_core_dataset.csv"
STATION_FIXTURE_PATH = BASE_DIR / "station_master_fixture.json"
SNAPSHOT_FIXTURE_PATH = BASE_DIR / "station_hourly_data_fixture.json"


def _normalize_station_id(value: object) -> str:
    if pd.isna(value):
        return ""
    text = str(value).strip()
    if text.endswith(".0"):
        text = text[:-2]
    return text


def _rebalance_inventory(values: np.ndarray, capacities: np.ndarray) -> np.ndarray:
    """Rebalance one hour inventory vector while strictly preserving 1200 vehicles."""

    balanced = np.clip(values.astype(float), 0, capacities)
    difference = TOTAL_SYSTEM_VEHICLES - float(balanced.sum())
    if abs(difference) < 1e-6:
        return balanced.astype(int)

    if difference > 0:
        slack = capacities - balanced
        if float(slack.sum()) <= 0:
            raise ValueError("No remaining station capacity to preserve total inventory")
        balanced += difference * (slack / float(slack.sum()))
    else:
        removable = balanced.copy()
        if float(removable.sum()) <= 0:
            raise ValueError("No inventory available to rebalance totals")
        balanced += difference * (removable / float(removable.sum()))

    rounded = np.floor(np.clip(balanced, 0, capacities)).astype(int)
    remainder = TOTAL_SYSTEM_VEHICLES - int(rounded.sum())

    if remainder > 0:
        order = np.argsort(-(balanced - rounded))
        for idx in order:
            if remainder <= 0:
                break
            if rounded[idx] < capacities[idx]:
                rounded[idx] += 1
                remainder -= 1
    elif remainder < 0:
        order = np.argsort(balanced - rounded)
        for idx in order:
            if remainder >= 0:
                break
            if rounded[idx] > 0:
                rounded[idx] -= 1
                remainder += 1

    rounded = np.clip(rounded, 0, capacities.astype(int))
    if int(rounded.sum()) != TOTAL_SYSTEM_VEHICLES:
        raise ValueError("Failed to preserve the 1200-vehicle invariant during rebalancing")
    return rounded


class CoreDatasetGenerator:
    """Generate compliant hourly core data and fixtures."""

    def __init__(self) -> None:
        self.master_frame = build_station_master_frame().sort_values("ysu_id").reset_index(drop=True)
        self.mapping_frame = build_station_mapping_frame().sort_values("ysu_id").reset_index(drop=True)

    def load_raw_data(self) -> pd.DataFrame:
        if not RAW_DATASET_PATH.exists():
            raise FileNotFoundError(f"Raw dataset not found: {RAW_DATASET_PATH}")
        frame = pd.read_csv(RAW_DATASET_PATH, low_memory=False)
        frame["started_at"] = pd.to_datetime(frame["started_at"], format="mixed", errors="coerce")
        frame["ended_at"] = pd.to_datetime(frame["ended_at"], format="mixed", errors="coerce")
        frame = frame.dropna(subset=["started_at", "ended_at", "start_station_id", "end_station_id"])
        return frame

    def _aggregate_flow(self, raw_frame: pd.DataFrame) -> pd.DataFrame:
        mapping = {
            _normalize_station_id(row.washington_station_id): int(row.ysu_id)
            for row in self.mapping_frame.itertuples()
        }
        washington_ids = set(mapping.keys())
        filtered = raw_frame[
            raw_frame["start_station_id"].map(_normalize_station_id).isin(washington_ids)
            | raw_frame["end_station_id"].map(_normalize_station_id).isin(washington_ids)
        ].copy()
        filtered["start_station_id"] = filtered["start_station_id"].map(_normalize_station_id)
        filtered["end_station_id"] = filtered["end_station_id"].map(_normalize_station_id)

        start_counts = (
            filtered[filtered["start_station_id"].isin(washington_ids)]
            .assign(
                ysu_id=lambda df: df["start_station_id"].map(mapping),
                hour=lambda df: df["started_at"].dt.floor("h"),
            )
            .groupby(["ysu_id", "hour"])
            .size()
            .rename("outflow")
            .reset_index()
        )
        end_counts = (
            filtered[filtered["end_station_id"].isin(washington_ids)]
            .assign(
                ysu_id=lambda df: df["end_station_id"].map(mapping),
                hour=lambda df: df["ended_at"].dt.floor("h"),
            )
            .groupby(["ysu_id", "hour"])
            .size()
            .rename("inflow")
            .reset_index()
        )

        merged = pd.merge(start_counts, end_counts, on=["ysu_id", "hour"], how="outer").fillna(0)
        merged["inflow"] = merged["inflow"].astype(float)
        merged["outflow"] = merged["outflow"].astype(float)
        merged["net_flow"] = merged["inflow"] - merged["outflow"]
        return merged.sort_values(["hour", "ysu_id"]).reset_index(drop=True)

    def generate_dataset(self) -> pd.DataFrame:
        raw_frame = self.load_raw_data()
        flow_frame = self._aggregate_flow(raw_frame)

        station_ids = self.master_frame["ysu_id"].tolist()
        all_hours = pd.date_range(flow_frame["hour"].min(), flow_frame["hour"].max(), freq="h")

        flow_grid = (
            pd.MultiIndex.from_product([all_hours, station_ids], names=["hour", "ysu_id"])
            .to_frame(index=False)
            .merge(flow_frame, on=["ysu_id", "hour"], how="left")
            .fillna(0)
            .sort_values(["hour", "ysu_id"])
            .reset_index(drop=True)
        )

        flow_matrix = (
            flow_grid.pivot(index="hour", columns="ysu_id", values="net_flow")
            .reindex(index=all_hours, columns=station_ids, fill_value=0)
            .astype(float)
        )

        capacities = self.master_frame["max_capacity"].to_numpy(dtype=float)
        current_inventory = self.master_frame["initial_inventory"].to_numpy(dtype=float)
        inventory_by_hour: Dict[pd.Timestamp, np.ndarray] = {}

        for hour in all_hours:
            projected = current_inventory + flow_matrix.loc[hour].to_numpy(dtype=float)
            current_inventory = _rebalance_inventory(projected, capacities).astype(float)
            inventory_by_hour[hour] = current_inventory.copy()

        inventory_frame = (
            pd.DataFrame.from_dict(inventory_by_hour, orient="index", columns=station_ids)
            .reset_index()
            .rename(columns={"index": "hour"})
            .melt(id_vars="hour", var_name="ysu_id", value_name="inventory")
            .sort_values(["hour", "ysu_id"])
            .reset_index(drop=True)
        )

        dataset = (
            flow_grid.merge(inventory_frame, on=["hour", "ysu_id"], how="left")
            .merge(self.master_frame, on="ysu_id", how="left")
            .rename(columns={"station_name": "ysu_name", "station_type": "ysu_type"})
            .sort_values(["ysu_id", "hour"])
            .reset_index(drop=True)
        )
        dataset["hour"] = pd.to_datetime(dataset["hour"])
        dataset["inventory"] = dataset["inventory"].astype(int)
        dataset["max_capacity"] = dataset["max_capacity"].astype(int)
        dataset["net_flow"] = dataset["inflow"] - dataset["outflow"]
        return dataset

    def save_dataset(self, dataset: pd.DataFrame) -> None:
        dataset.to_csv(OUTPUT_DATASET_PATH, index=False, encoding="utf-8-sig")

    def save_fixtures(self, dataset: pd.DataFrame) -> None:
        station_fixture = []
        for row in self.master_frame.itertuples():
            station_fixture.append(
                {
                    "model": "operation_management.parkingspot",
                    "pk": int(row.ysu_id),
                    "fields": {
                        "ysu_id": int(row.ysu_id),
                        "spot_name": row.station_name,
                        "longitude": float(row.longitude),
                        "latitude": float(row.latitude),
                        "max_capacity": int(row.max_capacity),
                        "washington_station_id": row.washington_station_id,
                        "washington_station_name": row.washington_station_name,
                        "initial_inventory": int(row.initial_inventory),
                        "low_warning_threshold": int(row.low_warning_threshold),
                        "high_warning_threshold": int(row.high_warning_threshold),
                        "notes": row.notes,
                        "is_active": bool(row.is_active),
                        "campus_area": "west" if float(row.longitude) < 119.533 else "east",
                        "spot_type": row.station_type,
                        "service_radius": 100,
                    },
                }
            )
        with open(STATION_FIXTURE_PATH, "w", encoding="utf-8") as fixture_file:
            json.dump(station_fixture, fixture_file, ensure_ascii=False, indent=2)

        snapshot_fixture = []
        for pk, row in enumerate(dataset.itertuples(), start=1):
            snapshot_fixture.append(
                {
                    "model": "data_process.parkingspotsnapshot",
                    "pk": pk,
                    "fields": {
                        "parking_spot": int(row.ysu_id),
                        "timestamp": pd.Timestamp(row.hour).isoformat(),
                        "parked_count": int(row.inventory),
                        "riding_count": 0,
                        "fault_count": 0,
                    },
                }
            )
        with open(SNAPSHOT_FIXTURE_PATH, "w", encoding="utf-8") as fixture_file:
            json.dump(snapshot_fixture, fixture_file, ensure_ascii=False)

    def validate_dataset(self, dataset: pd.DataFrame) -> None:
        if dataset["ysu_id"].nunique() != STATION_COUNT:
            raise ValueError("Station count validation failed")

        duplicate_count = int(dataset.duplicated(["ysu_id", "hour"]).sum())
        if duplicate_count:
            raise ValueError(f"Duplicate station-hour rows found: {duplicate_count}")

        inventory_sum = dataset.groupby("hour")["inventory"].sum()
        if not bool((inventory_sum == TOTAL_SYSTEM_VEHICLES).all()):
            raise ValueError("Global vehicle conservation validation failed")

        invalid_capacity = (dataset["inventory"] < 0) | (dataset["inventory"] > dataset["max_capacity"])
        if bool(invalid_capacity.any()):
            raise ValueError("Inventory exceeded station bounds")

        mapping_pairs = dataset[["ysu_id", "washington_station_id"]].drop_duplicates()
        if len(mapping_pairs) != STATION_COUNT or mapping_pairs["washington_station_id"].nunique() != STATION_COUNT:
            raise ValueError("Station mapping is not one-to-one")

    def run(self) -> pd.DataFrame:
        export_master_data_assets()
        dataset = self.generate_dataset()
        self.validate_dataset(dataset)
        self.save_dataset(dataset)
        self.save_fixtures(dataset)
        return dataset


if __name__ == "__main__":
    generator = CoreDatasetGenerator()
    generated = generator.run()
    print(
        f"{OFFICIAL_PROJECT_NAME} 核心数据集已生成: "
        f"{len(generated)} rows, {generated['ysu_id'].nunique()} stations"
    )
