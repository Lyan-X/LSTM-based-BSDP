"""
Generate 14-day historical hourly data for all 62 YSU parking spots.
Creates ParkingSpotSnapshot, BikeRideData, and WeatherData records.
Usage: python generate_historical_data.py
"""
import os
import sys
import random
import numpy as np
from datetime import datetime, timedelta

# Django setup
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'bike_dispatch_platform.settings')
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), 'bike_dispatch_platform'))
import django
django.setup()

from django.utils import timezone as tz
from data_process.models import BikeRideData, WeatherData, ParkingSpotSnapshot, DataProcessLog
from system_support.models import User

# Import YSU parking spots (DO NOT MODIFY config.py)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from config import PARKING_SPOTS

SPOT_NAMES = list(PARKING_SPOTS.keys())
TOTAL_VEHICLES = 520  # Total fleet size


def get_system_user():
    user, _ = User.objects.get_or_create(
        username='data_generator',
        defaults={'role': 'admin', 'is_active': True}
    )
    if not user.has_usable_password():
        user.set_password('gen2026')
        user.save()
    return user


def hourly_parked_count(hour, weekday):
    """YSU-aligned hourly parked vehicle count per spot.
    Peak hours (7-9, 17-19): fewer parked (students riding).
    Night/early morning: more parked. Weekend: slightly more parked overall."""
    if 7 <= hour <= 9 or 17 <= hour <= 19:
        base = random.randint(3, 12)
    elif 11 <= hour <= 13:
        base = random.randint(8, 18)
    elif 0 <= hour <= 5:
        base = random.randint(15, 30)
    else:
        base = random.randint(10, 22)
    # Weekend: more parked at teaching spots
    if weekday >= 5:
        base = int(base * 1.2)
    return max(0, base + random.randint(-3, 3))


def daily_weather(date_obj):
    """Generate plausible Qinhuangdao/YSU weather for a date."""
    month = date_obj.month
    if month in (12, 1, 2):
        temp = random.uniform(-12, 3)
        weather = random.choice(['sunny', 'cloudy', 'cloudy', 'sunny'])
    elif month in (3, 4, 5):
        temp = random.uniform(3, 22)
        weather = random.choice(['sunny', 'sunny', 'cloudy', 'rain'])
    elif month in (6, 7, 8):
        temp = random.uniform(22, 35)
        weather = random.choice(['sunny', 'sunny', 'cloudy', 'rain', 'rain'])
    else:
        temp = random.uniform(5, 20)
        weather = random.choice(['sunny', 'cloudy', 'cloudy', 'rain'])
    humidity = random.uniform(30, 85)
    wind = random.uniform(0.5, 8)
    rainfall = random.uniform(2, 20) if weather == 'rain' else 0
    return round(temp, 1), round(humidity, 1), round(wind, 1), round(rainfall, 1), weather


def run():
    print("=" * 60)
    print("  Generating 14-day historical data for YSU parking spots")
    print("=" * 60)

    user = get_system_user()

    # Time range: 14 days ending 3 days ago (leave room for demo data)
    end_dt = tz.now().replace(minute=0, second=0, microsecond=0) - timedelta(days=2)
    start_dt = end_dt - timedelta(days=14)

    print(f"  Range: {start_dt:%Y-%m-%d %H:00} → {end_dt:%Y-%m-%d %H:00}")
    print(f"  Spots: {len(SPOT_NAMES)}")

    # Clear old generated data to avoid duplicates
    ParkingSpotSnapshot.objects.filter(parking_spot_id__startswith='PS').delete()
    BikeRideData.objects.filter(data_source='historical_gen').delete()
    WeatherData.objects.filter(area='燕山大学').delete()

    snapshot_batch = []
    ride_batch = []
    weather_cache = {}
    total_hours = int((end_dt - start_dt).total_seconds() / 3600)

    current = start_dt
    hour_idx = 0
    while current <= end_dt:
        hour = current.hour
        weekday = current.weekday()
        date_key = current.date()

        # Generate weather once per day
        if date_key not in weather_cache:
            temp, hum, wind, rain, wtype = daily_weather(date_key)
            weather_cache[date_key] = (temp, hum, wind, rain, wtype)
            try:
                WeatherData.objects.update_or_create(
                    area='燕山大学', date=date_key,
                    defaults={
                        'temperature': temp, 'humidity': hum,
                        'wind_speed': wind, 'rainfall': rain,
                        'weather_type': wtype
                    }
                )
            except Exception:
                pass
        temp, hum, wind, rain, wtype = weather_cache[date_key]

        for idx, spot_name in enumerate(SPOT_NAMES):
            spot_id = f'PS{idx+1:03d}'
            parked = hourly_parked_count(hour, weekday)
            riding = random.randint(3, 18)
            fault = random.randint(0, 3)

            snapshot_batch.append(ParkingSpotSnapshot(
                parking_spot_id=spot_id,
                parking_spot_name=spot_name,
                timestamp=current,
                parked_count=parked,
                riding_count=riding,
                fault_count=fault,
            ))

            # Generate 1-3 ride records per spot per hour
            num_rides = random.randint(0, 3) if 6 <= hour <= 22 else 0
            for _ in range(num_rides):
                end_spot = random.choice([s for s in SPOT_NAMES if s != spot_name])
                ride_time = current + timedelta(minutes=random.randint(0, 59))
                ride_batch.append(BikeRideData(
                    data_source='historical_gen',
                    start_point=spot_name,
                    end_point=end_spot,
                    ride_datetime=ride_time,
                    duration=round(random.uniform(3, 25), 1),
                    distance=round(random.uniform(0.3, 3.0), 2),
                    temperature=temp,
                    wind_speed=wind,
                    status='cleaned',
                    upload_user=user,
                ))

        hour_idx += 1
        if hour_idx % 24 == 0:
            day_num = hour_idx // 24
            print(f"  Day {day_num}/14 generated ({current:%Y-%m-%d})")

        current += timedelta(hours=1)

    # Bulk insert
    print(f"\n  Inserting {len(snapshot_batch)} snapshots...")
    ParkingSpotSnapshot.objects.bulk_create(snapshot_batch, batch_size=2000, ignore_conflicts=True)

    print(f"  Inserting {len(ride_batch)} ride records...")
    BikeRideData.objects.bulk_create(ride_batch, batch_size=2000)

    # Log
    DataProcessLog.objects.create(
        parking_spot_name=f"14天历史数据生成: {len(snapshot_batch)}条快照 + {len(ride_batch)}条骑行",
        actual_count=len(snapshot_batch),
        status='normal'
    )

    print(f"\n  Done! Snapshots: {len(snapshot_batch)}, Rides: {len(ride_batch)}")
    print(f"  Weather records: {len(weather_cache)}")
    print(f"  DB totals: Snapshots={ParkingSpotSnapshot.objects.count()}, "
          f"Rides={BikeRideData.objects.count()}, Weather={WeatherData.objects.count()}")
    print("=" * 60)


if __name__ == '__main__':
    run()
