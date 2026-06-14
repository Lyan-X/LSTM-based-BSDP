"""Verify state classification with state_9 scheme and peak hour data."""
import os, sys, django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'django_project.settings')
sys.path.insert(0, 'e:/develop/BSDP-Bike Sharing Demand Prediction Based on LSTM Model/BSDP')
django.setup()

from bike_dispatch_platform.demand_prediction.services.station_prediction_service import station_prediction_service
from bike_dispatch_platform.demand_prediction.services.state_classifier_support import (
    classify_inventory_state, state_color, state_label
)
import pandas as pd

dataset = station_prediction_service.dataset.copy()
dataset["source_date"] = dataset["hour"].dt.date

daily_span = (
    dataset.groupby("source_date")["inventory"]
    .agg(["min", "max"])
    .assign(range=lambda frame: frame["max"] - frame["min"])
    .sort_values("range", ascending=False)
)
playback_date = daily_span.index[0]
print(f"使用日期: {playback_date}")

day_frame = dataset[dataset["source_date"] == playback_date].copy()
peak_hour_data = day_frame[day_frame["hour"].dt.hour == 16].copy()
print(f"\n下午4点(16:00)的库存分布:")
print(f"  站点数: {len(peak_hour_data)}")
print(f"  库存范围: {peak_hour_data['inventory'].min()} - {peak_hour_data['inventory'].max()}")

print(f"\n各站点状态分布 (state_9):")
state_counts = {}
for _, row in peak_hour_data.iterrows():
    inv = row["inventory"]
    state_idx = classify_inventory_state(inv, 8, 40, scheme_key="state_9")
    label = state_label(state_idx, scheme_key="state_9")
    state_counts[label] = state_counts.get(label, 0) + 1

for label, count in sorted(state_counts.items()):
    print(f"  {label}: {count}")

print(f"\n库存最高和最低的站点:")
top_low = peak_hour_data.nsmallest(5, "inventory")[["ysu_id", "ysu_name", "inventory", "net_flow"]]
top_high = peak_hour_data.nlargest(5, "inventory")[["ysu_id", "ysu_name", "inventory", "net_flow"]]
print("最低库存:")
for _, row in top_low.iterrows():
    state_idx = classify_inventory_state(row["inventory"], 8, 40, scheme_key="state_9")
    print(f"  {row['ysu_id']} {row['ysu_name']}: {row['inventory']} -> {state_label(state_idx, 'state_9')} ({state_color(state_idx, 'state_9')})")
print("最高库存:")
for _, row in top_high.iterrows():
    state_idx = classify_inventory_state(row["inventory"], 8, 40, scheme_key="state_9")
    print(f"  {row['ysu_id']} {row['ysu_name']}: {row['inventory']} -> {state_label(state_idx, 'state_9')} ({state_color(state_idx, 'state_9')})")
