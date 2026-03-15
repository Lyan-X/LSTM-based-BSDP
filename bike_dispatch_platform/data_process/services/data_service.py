"""Data-process compatibility service for the mainline deterministic platform."""

from __future__ import annotations

import csv
import logging
from pathlib import Path
from typing import Dict, List, Tuple

import pandas as pd
from django.conf import settings

from data_process.models import BikeRideData, WeatherData
from demand_prediction.services.station_prediction_service import station_prediction_service

logger = logging.getLogger(__name__)


class DataService:
    """Provide read-only dataset access for the mainline Django apps."""

    def __init__(self) -> None:
        project_root = Path(settings.BASE_DIR).resolve().parent
        self.core_dataset_path = project_root / "ysu_62_stations_hourly_core_dataset.csv"
        self.training_dataset_path = project_root / "ysu_bike_data.csv"

    def validate_file(self, file) -> Tuple[bool, str]:
        return False, "基于深度学习的城市共享单车调度需求预测与运维管理平台当前版本禁用手工上传"

    def read_file(self, file) -> Tuple[None, str]:
        return None, "基于深度学习的城市共享单车调度需求预测与运维管理平台当前版本禁用手工上传"

    def clean_data(self, df) -> Tuple[pd.DataFrame, None]:
        return df.copy(), None

    def process_ride_data(self, df, user) -> Tuple[int, str]:
        return 0, "仅允许使用真实映射数据集，不接受手工写入骑行数据"

    def trigger_demand_prediction(self) -> None:
        station_prediction_service.get_batch_response(force=True)
        logger.info("Station-level 48h prediction batch refreshed")

    def process_weather_data(self, df) -> Tuple[int, str]:
        return 0, "当前版本不维护独立天气导入链路"

    def get_data_stats(self, user=None) -> Dict[str, int]:
        return {
            "total_ride_data": BikeRideData.objects.count(),
            "total_weather_data": WeatherData.objects.count(),
            "recent_ride_data": 0,
            "recent_weather_data": 0,
        }

    def export_data(self, data_type, user=None):
        if data_type == "ride" and self.training_dataset_path.exists():
            return pd.read_csv(self.training_dataset_path), None
        if data_type == "weather":
            return pd.DataFrame(columns=["message"], data=[["未配置独立天气导出链路"]]), None
        return None, "不支持的数据类型"

    def get_data_by_date_range(self, start_date, end_date, region=None):
        if not self.core_dataset_path.exists():
            return None, f"核心数据集不存在: {self.core_dataset_path}"
        dataset = pd.read_csv(self.core_dataset_path, parse_dates=["hour"])
        mask = dataset["hour"].dt.date.between(start_date, end_date)
        if region:
            mask &= dataset["ysu_name"].astype(str).str.contains(str(region), na=False)
        return dataset.loc[mask].to_dict("records"), None

    def generate_test_data(self, days=7, rides_per_day=100):
        return None, "为保证真实映射与1200辆守恒，测试数据生成已禁用"

    def sync_campus_vehicle_data(self):
        return [], None

    def start_scheduled_sync(self) -> bool:
        logger.info("Scheduled sync delegates to the deterministic runtime scheduler")
        return True

    def clean_isolated_data(self) -> int:
        return 0

    def batch_upload_excel(self, files, user=None) -> Tuple[int, str]:
        return 0, "当前版本禁用批量上传，请直接使用固定核心数据集"


data_service = DataService()
