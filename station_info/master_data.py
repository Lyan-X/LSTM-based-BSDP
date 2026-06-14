"""Canonical station master data for 基于深度学习的校园共享单车调度需求预测与运维管理平台."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Tuple

import pandas as pd

from allocate_vehicles_1200 import VehicleAllocator
from config import PARKING_SPOTS

OFFICIAL_PROJECT_NAME = "基于深度学习的校园共享单车调度需求预测与运维管理平台"
TOTAL_SYSTEM_VEHICLES = 1200
STATION_COUNT = 62
DISPATCH_THRESHOLD = 15
DEFAULT_REFRESH_SECONDS = 10
PREDICTION_HORIZON_HOURS = 48

ROOT_DIR = Path(__file__).resolve().parents[1]
ALLOCATION_PATH = ROOT_DIR / "vehicle_allocation_1200.csv"
STATION_MASTER_DATA_PATH = ROOT_DIR / "ysu_62_station_master_data.csv"
STATION_MAPPING_PATH = ROOT_DIR / "ysu_62_station_mapping.csv"

# 修复旧版 ysu_id=49 与 ysu_id=61 重复映射同一华盛顿站点的问题。
MAPPING_OVERRIDE: Dict[int, Dict[str, str]] = {
    61: {
        "washington_station_id": "31241",
        "washington_station_name": "Thomas Circle",
    }
}


@dataclass(frozen=True)
class StationMasterRecord:
    """Immutable canonical master record for one YSU station."""

    ysu_id: int
    station_name: str
    station_type: str
    latitude: float
    longitude: float
    max_capacity: int
    initial_inventory: int
    washington_station_id: str
    washington_station_name: str
    low_warning_threshold: int
    high_warning_threshold: int
    is_active: bool
    notes: str


def _normalize_name(value: str) -> str:
    return "".join(str(value).split())


def _round_up_to_five(value: float) -> int:
    return int(((int(value) + 4) // 5) * 5)


def _derive_capacity(initial_inventory: int, station_type: str, priority: int) -> int:
    type_factor = {
        "academic": 1.85,
        "residential": 1.75,
        "comprehensive": 1.90,
        "transit": 2.10,
    }
    base_capacity = initial_inventory * type_factor.get(station_type, 1.8) + 8
    if priority <= 5:
        base_capacity += 5
    return max(initial_inventory + 10, _round_up_to_five(base_capacity))


def _derive_warning_thresholds(max_capacity: int) -> Tuple[int, int]:
    low_warning = max(5, int(round(max_capacity * 0.25)))
    high_warning = min(max_capacity - 2, max(low_warning + 5, int(round(max_capacity * 0.80))))
    return low_warning, high_warning


def _load_allocation_map() -> Dict[int, Dict[str, int]]:
    allocation_frame = pd.read_csv(ALLOCATION_PATH)
    allocation_map: Dict[int, Dict[str, int]] = {}
    for _, row in allocation_frame.iterrows():
        ysu_id = int(row["映射ID"])
        allocation_map[ysu_id] = {
            "initial_inventory": int(row["分配车辆数"]),
            "priority": int(row["优先级"]),
        }
    return allocation_map


def _load_mapping_rows() -> Iterable[List[object]]:
    return VehicleAllocator().mapping_data


def _lookup_coordinates(station_name: str) -> Tuple[float, float]:
    if station_name in PARKING_SPOTS:
        longitude, latitude = PARKING_SPOTS[station_name]
        return float(latitude), float(longitude)

    normalized = _normalize_name(station_name)
    for candidate, coordinates in PARKING_SPOTS.items():
        if _normalize_name(candidate) == normalized:
            longitude, latitude = coordinates
            return float(latitude), float(longitude)
    raise KeyError(f"Missing coordinate mapping for station {station_name}")


def load_station_master_data() -> List[StationMasterRecord]:
    """Load the canonical 62-station master data set."""

    allocation_map = _load_allocation_map()
    records: List[StationMasterRecord] = []

    for row in sorted(_load_mapping_rows(), key=lambda item: int(item[0])):
        ysu_id = int(row[0])
        station_name = str(row[1])
        station_type = str(row[2])
        washington_station_id = str(int(row[3]))
        washington_station_name = str(row[4])

        if ysu_id in MAPPING_OVERRIDE:
            washington_station_id = MAPPING_OVERRIDE[ysu_id]["washington_station_id"]
            washington_station_name = MAPPING_OVERRIDE[ysu_id]["washington_station_name"]

        latitude, longitude = _lookup_coordinates(station_name)
        allocation_info = allocation_map[ysu_id]
        max_capacity = _derive_capacity(
            initial_inventory=allocation_info["initial_inventory"],
            station_type=station_type,
            priority=allocation_info["priority"],
        )
        low_warning, high_warning = _derive_warning_thresholds(max_capacity)

        records.append(
            StationMasterRecord(
                ysu_id=ysu_id,
                station_name=station_name,
                station_type=station_type,
                latitude=latitude,
                longitude=longitude,
                max_capacity=max_capacity,
                initial_inventory=allocation_info["initial_inventory"],
                washington_station_id=washington_station_id,
                washington_station_name=washington_station_name,
                low_warning_threshold=low_warning,
                high_warning_threshold=high_warning,
                is_active=True,
                notes=f"{OFFICIAL_PROJECT_NAME} 62站点主数据锁定记录",
            )
        )

    if len(records) != STATION_COUNT:
        raise ValueError(f"Expected {STATION_COUNT} stations, got {len(records)}")

    inventory_total = sum(record.initial_inventory for record in records)
    if inventory_total != TOTAL_SYSTEM_VEHICLES:
        raise ValueError(
            f"Expected total inventory {TOTAL_SYSTEM_VEHICLES}, got {inventory_total}"
        )

    washington_ids = [record.washington_station_id for record in records]
    if len(set(washington_ids)) != len(washington_ids):
        raise ValueError("Washington station mapping must remain one-to-one")

    ysu_ids = [record.ysu_id for record in records]
    if ysu_ids != list(range(1, STATION_COUNT + 1)):
        raise ValueError("YSU station ids must remain continuous from 1 to 62")

    return records


def build_station_master_frame() -> pd.DataFrame:
    """Return the canonical station master data as a DataFrame."""

    return pd.DataFrame(
        [
            {
                "ysu_id": record.ysu_id,
                "station_name": record.station_name,
                "station_type": record.station_type,
                "latitude": record.latitude,
                "longitude": record.longitude,
                "max_capacity": record.max_capacity,
                "initial_inventory": record.initial_inventory,
                "washington_station_id": record.washington_station_id,
                "washington_station_name": record.washington_station_name,
                "low_warning_threshold": record.low_warning_threshold,
                "high_warning_threshold": record.high_warning_threshold,
                "is_active": record.is_active,
                "notes": record.notes,
            }
            for record in load_station_master_data()
        ]
    )


def build_station_mapping_frame() -> pd.DataFrame:
    """Return the one-to-one YSU-to-Washington mapping table."""

    return pd.DataFrame(
        [
            {
                "ysu_id": record.ysu_id,
                "ysu_station_name": record.station_name,
                "ysu_station_type": record.station_type,
                "washington_station_id": record.washington_station_id,
                "washington_station_name": record.washington_station_name,
            }
            for record in load_station_master_data()
        ]
    )


def export_master_data_assets() -> None:
    """Persist the canonical master-data CSV files used by the project."""

    build_station_master_frame().to_csv(STATION_MASTER_DATA_PATH, index=False, encoding="utf-8-sig")
    build_station_mapping_frame().to_csv(STATION_MAPPING_PATH, index=False, encoding="utf-8-sig")
