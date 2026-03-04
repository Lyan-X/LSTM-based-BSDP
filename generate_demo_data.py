"""
Generate 2-day demo data covering the current period for YSU parking spots.
Creates snapshots, rides, predictions, and dispatch tasks — all data needed for demo.
Usage: python generate_demo_data.py
"""
import os
import sys
import random
import numpy as np
from datetime import datetime, timedelta

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'bike_dispatch_platform.settings')
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), 'bike_dispatch_platform'))
import django
django.setup()

from django.utils import timezone as tz
from data_process.models import BikeRideData, WeatherData, ParkingSpotSnapshot, DataProcessLog
from demand_prediction.models import PredictionResult, ModelTrainLog, REGION_CHOICES
from operation_management.models import ScheduleTask, ParkingSpot
from system_support.models import User, SystemLog

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from config import PARKING_SPOTS

SPOT_NAMES = list(PARKING_SPOTS.keys())

# Map spot names to regions for predictions
def spot_to_region(name):
    west = ['西区第一教学楼','西区第二教学楼','西区第三教学楼','西区第五教学楼','电气工程学院东','材料学院A楼','艺术学院']
    east = ['东区第一教学楼','东区第二教学楼','东区第三教学楼','东区第四教学楼北侧','建筑系','文法学院','车辆与能源学院']
    dorm = ['学生公寓8号楼','至明楼','至博楼','至雅楼南侧','至雅楼北侧']
    lib  = ['新图书馆西侧','新图书馆东侧','东区图书馆']
    food = ['西区大食堂东侧','西区大食堂西侧','燕园餐厅','中快餐厅2食堂','燕鸣湖餐厅西南侧','燕鸣湖餐厅西北侧']
    if name in west: return 'west_campus'
    if name in east: return 'east_campus'
    if name in dorm: return 'dorm_area'
    if name in lib:  return 'library_area'
    if name in food: return 'canteen_area'
    return 'gate_area'


def get_user():
    user, _ = User.objects.get_or_create(username='data_generator',
                                          defaults={'role': 'admin', 'is_active': True})
    if not user.has_usable_password():
        user.set_password('gen2026')
        user.save()
    return user


def hourly_parked(hour, weekday):
    if 7 <= hour <= 9 or 17 <= hour <= 19:
        return random.randint(3, 12)
    elif 0 <= hour <= 5:
        return random.randint(15, 30)
    elif 11 <= hour <= 13:
        return random.randint(8, 18)
    else:
        return random.randint(10, 22)


def run():
    print("=" * 60)
    print("  Generating 2-day demo data for YSU")
    print("=" * 60)

    user = get_user()
    now = tz.now().replace(minute=0, second=0, microsecond=0)
    start = now - timedelta(days=2)

    # Ensure parking spots exist in DB
    for idx, (name, (lon, lat)) in enumerate(PARKING_SPOTS.items()):
        ParkingSpot.objects.get_or_create(
            id=f'PS{idx+1:03d}',
            defaults={'name': name, 'latitude': lat, 'longitude': lon, 'service_radius': 100}
        )

    snap_batch = []
    ride_batch = []
    pred_batch = []
    task_count = 0

    current = start
    hour_num = 0
    while current <= now:
        h = current.hour
        wd = current.weekday()
        date_key = current.date()

        # Weather
        try:
            WeatherData.objects.update_or_create(
                area='燕山大学', date=date_key,
                defaults={
                    'temperature': round(random.uniform(-2, 18), 1),
                    'humidity': round(random.uniform(35, 75), 1),
                    'wind_speed': round(random.uniform(1, 6), 1),
                    'rainfall': round(random.uniform(0, 5), 1) if random.random() < 0.2 else 0,
                    'weather_type': random.choice(['sunny', 'cloudy', 'rain'])
                }
            )
        except Exception:
            pass

        for idx, spot_name in enumerate(SPOT_NAMES):
            spot_id = f'PS{idx+1:03d}'
            parked = hourly_parked(h, wd) + random.randint(-2, 2)
            parked = max(0, parked)
            riding = random.randint(3, 15)
            fault = random.randint(0, 3)

            snap_batch.append(ParkingSpotSnapshot(
                parking_spot_id=spot_id, parking_spot_name=spot_name,
                timestamp=current, parked_count=parked,
                riding_count=riding, fault_count=fault,
            ))

            # Rides
            if 6 <= h <= 22:
                for _ in range(random.randint(0, 2)):
                    end_spot = random.choice([s for s in SPOT_NAMES if s != spot_name])
                    ride_batch.append(BikeRideData(
                        data_source='demo_gen', start_point=spot_name, end_point=end_spot,
                        ride_datetime=current + timedelta(minutes=random.randint(0, 59)),
                        duration=round(random.uniform(3, 20), 1),
                        distance=round(random.uniform(0.3, 2.5), 2),
                        temperature=round(random.uniform(-2, 18), 1),
                        wind_speed=round(random.uniform(1, 5), 1),
                        status='cleaned', upload_user=user,
                    ))

        # Every 4 hours: generate predictions for each region
        if hour_num % 4 == 0 and 6 <= h <= 22:
            period = 'morning' if h < 10 else 'noon' if h < 14 else 'evening' if h < 20 else 'night'
            for rk, _ in REGION_CHOICES:
                demand = random.randint(15, 65)
                supply = random.randint(10, 50)
                try:
                    PredictionResult.objects.update_or_create(
                        region=rk, predict_date=date_key, predict_hour=h,
                        defaults={
                            'time_period': period, 'demand_count': demand,
                            'supply_count': supply, 'model_used': 'LSTM',
                            'accuracy': round(random.uniform(79, 86), 1),
                            'user': user,
                        }
                    )
                except Exception:
                    pass

        # Every 6 hours: generate dispatch tasks
        if hour_num % 6 == 0 and 7 <= h <= 20:
            s1 = random.choice(SPOT_NAMES)
            s2 = random.choice([s for s in SPOT_NAMES if s != s1])
            ScheduleTask.objects.create(
                task_type='vehicle_dispatch',
                start_location=s1, end_location=s2,
                dispatch_count=random.randint(5, 20),
                priority=random.choice(['high', 'medium', 'low']),
                status=random.choice(['pending', 'in_progress', 'completed', 'completed']),
                predicted_time=current,
            )
            task_count += 1

        hour_num += 1
        current += timedelta(hours=1)

    # Bulk insert
    print(f"  Inserting {len(snap_batch)} snapshots...")
    ParkingSpotSnapshot.objects.bulk_create(snap_batch, batch_size=2000, ignore_conflicts=True)
    print(f"  Inserting {len(ride_batch)} rides...")
    BikeRideData.objects.bulk_create(ride_batch, batch_size=2000)

    # Create train log entries for the demo period
    for d_offset in [2, 1]:
        train_date = (now - timedelta(days=d_offset)).date()
        for mtype, mfile, r2 in [('lstm', 'latest_lstm.h5', 81.24), ('bp', 'latest_bp.h5', 81.33)]:
            st = tz.make_aware(datetime.combine(train_date, datetime.min.time().replace(hour=2, minute=0)))
            ModelTrainLog.objects.get_or_create(
                model_filename=f'{mfile}_{train_date:%Y%m%d}',
                defaults={
                    'train_date': train_date, 'start_time': st,
                    'end_time': st + timedelta(minutes=random.randint(4, 8)),
                    'duration': random.randint(240, 480),
                    'mae': round(random.uniform(3.5, 5.0), 2),
                    'rmse': round(random.uniform(4.5, 6.0), 2),
                    'r2': r2 + random.uniform(-1, 1),
                    'status': 'success',
                }
            )

    # System logs
    SystemLog.objects.create(
        user=user, action='upload',
        description=f'Demo data generated: {len(snap_batch)} snapshots, {len(ride_batch)} rides, {task_count} tasks'
    )

    DataProcessLog.objects.create(
        parking_spot_name=f'2天演示数据: {len(snap_batch)}快照+{len(ride_batch)}骑行+{task_count}调度',
        actual_count=len(snap_batch), status='normal'
    )

    print(f"\n  Done! Snapshots={len(snap_batch)}, Rides={len(ride_batch)}, Tasks={task_count}")
    print(f"  DB totals: Snapshots={ParkingSpotSnapshot.objects.count()}, "
          f"Rides={BikeRideData.objects.count()}, Tasks={ScheduleTask.objects.count()}")
    print("=" * 60)


if __name__ == '__main__':
    run()
