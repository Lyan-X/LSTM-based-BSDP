import os, json
from datetime import datetime
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'bike_dispatch_platform.settings')
import django
django.setup()
from django.utils import timezone
from operation_management.views import _simulate_realtime_snapshot, _build_parking_spot_runtime_data, _build_dispatch_suggestions, DEMO_MODE
from data_process.models import WeatherData

naive = datetime(2026, 4, 10, 8, 10, 0)
now = timezone.make_aware(naive)
snapshot_time = _simulate_realtime_snapshot(now)
weather = WeatherData.objects.filter(date=now.date()).first()
temp = weather.temperature if weather else 15
wind = weather.wind_speed if weather else 2
rain = weather.rainfall if weather else 0
parking_spots_data, surplus_spots, deficit_spots, metrics = _build_parking_spot_runtime_data(now, temp, wind, rain, snapshot_time, DEMO_MODE)
suggestions = _build_dispatch_suggestions(surplus_spots, deficit_spots, metrics, now)
print(json.dumps({'time': now.strftime('%Y-%m-%d %H:%M:%S'), 'total': metrics['global_total_check'], 'surplus': metrics['total_surplus'], 'shortage': metrics['total_shortage'], 'matching_rate': metrics.get('matching_rate', 0), 'suggestions': len(suggestions), 'global_balance_ok': metrics['global_balance_ok']}, ensure_ascii=False))
