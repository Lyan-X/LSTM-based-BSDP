"""Test inventory variation across different hours in dataset."""
import os, sys, django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'django_project.settings')
sys.path.insert(0, 'e:/develop/BSDP-Bike Sharing Demand Prediction Based on LSTM Model/BSDP')
django.setup()

import pandas as pd
from bike_dispatch_platform.demand_prediction.services.station_prediction_service import station_prediction_service

dataset = station_prediction_service.dataset.copy()
dataset["source_date"] = dataset["hour"].dt.date

# Get the playback date (highest volatility day)
daily_span = (
    dataset.groupby("source_date")["inventory"]
    .agg(["min", "max"])
    .assign(range=lambda frame: frame["max"] - frame["min"])
    .sort_values("range", ascending=False)
)
playback_date = daily_span.index[0]
print(f"播放日期: {playback_date}")
print(f"日期范围差异: {daily_span['range'].describe()}")

day_frame = dataset[dataset["source_date"] == playback_date].copy()
day_hours = sorted(day_frame["hour"].drop_duplicates().tolist())
print(f"\n该日共 {len(day_hours)} 个小时的数据")
print(f"小时示例: {day_hours[:5]}")

# Show inventory for station 1 across different hours
station_1_data = day_frame[day_frame["ysu_id"] == 1].sort_values("hour")
print(f"\n站点1在不同小时的库存和净流量:")
for _, row in station_1_data.iterrows():
    print(f"  {row['hour']}: inventory={row['inventory']}, net_flow={row['net_flow']}, inflow={row['inflow']}, outflow={row['outflow']}")

# Show inventory variation across all stations for a few hours
print(f"\n前3个小时的库存分布统计:")
for hour in day_hours[:3]:
    hour_data = day_frame[day_frame["hour"] == hour]["inventory"]
    print(f"  {hour}: min={hour_data.min()}, max={hour_data.max()}, mean={hour_data.mean():.1f}")
