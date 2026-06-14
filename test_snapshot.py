"""Test runtime snapshot to verify dynamic data."""
import os, sys, django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'django_project.settings')
sys.path.insert(0, 'e:/develop/BSDP-Bike Sharing Demand Prediction Based on LSTM Model/BSDP')
django.setup()

from bike_dispatch_platform.operation_management.services.runtime_service import runtime_service
from collections import Counter

snapshot = runtime_service.ensure_snapshot()
print('快照时间:', snapshot.bucket_time)
print('站点数量:', len(snapshot.station_rows))
print('全局车辆总数:', snapshot.metrics['global_vehicle_total'])
print('状态分布:')
states = Counter(row['current_state_group'] for row in snapshot.station_rows)
print('  scarce:', states.get('scarce', 0))
print('  balanced:', states.get('balanced', 0))
print('  saturated:', states.get('saturated', 0))
print('前10个站点的颜色分布:')
for row in snapshot.station_rows[:10]:
    print(f"  {row['station_id']}: {row['name']} count={row['count']} state={row['current_state_label']} color={row['current_state_color']}")
