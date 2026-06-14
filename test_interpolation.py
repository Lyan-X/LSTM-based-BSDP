"""Test runtime snapshot interpolation over time."""
import os, sys, django, time
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'django_project.settings')
sys.path.insert(0, 'e:/develop/BSDP-Bike Sharing Demand Prediction Based on LSTM Model/BSDP')
django.setup()

from bike_dispatch_platform.operation_management.services.runtime_service import runtime_service

print("测试10秒刷新的插值变化...")
print("=" * 60)

# Get snapshots at different times
for i in range(3):
    snapshot = runtime_service.ensure_snapshot()
    print(f"\n第 {i+1} 次快照 (bucket_time: {snapshot.bucket_time})")
    print(f"  插值比率 (推算): {snapshot.bucket_time.minute * 60 + snapshot.bucket_time.second}s into hour")
    # Show first 3 stations
    for row in snapshot.station_rows[:3]:
        print(f"  站点 {row['station_id']}: count={row['count']}, state={row['current_state_label']}, color={row['current_state_color']}")
    if i < 2:
        print("  等待 12 秒...")
        time.sleep(12)

print("\n" + "=" * 60)
print("测试完成")
