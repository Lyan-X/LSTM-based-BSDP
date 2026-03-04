"""
Real-Time Data Simulator for YSU Bike Sharing Platform
Generates mock ride records and vehicle status updates every 1 minute,
aligned with YSU peak/off-peak patterns. Writes to Django DB tables.

Usage:
  python simulate_real_time_data.py          # Run continuously (1-min interval)
  python simulate_real_time_data.py --once   # Run once and exit (for testing)
"""
import os
import sys
import random
import math
import time
import logging
from datetime import datetime, timedelta

# Django setup
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'bike_dispatch_platform.settings')
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), 'bike_dispatch_platform'))

import django
django.setup()

from django.utils import timezone
from data_process.models import BikeRideData, DataProcessLog
from operation_management.models import Vehicle, ParkingSpot
from system_support.models import User

import schedule

# ============ Configuration ============
# Import YSU parking spots from config (DO NOT MODIFY these coordinates)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from config import PARKING_SPOTS

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [RealTimeSim] %(levelname)s: %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(os.path.join(os.path.dirname(__file__), 'logs', 'realtime_sim.log'), encoding='utf-8')
    ]
)
logger = logging.getLogger(__name__)

# Ensure logs directory exists
os.makedirs(os.path.join(os.path.dirname(__file__), 'logs'), exist_ok=True)

# YSU peak/off-peak hour multipliers (higher = more rides generated)
HOUR_MULTIPLIER = {
    0: 0.05, 1: 0.02, 2: 0.02, 3: 0.02, 4: 0.03, 5: 0.1,
    6: 0.3,  7: 1.5,  8: 2.0,  9: 1.2,  10: 0.8, 11: 1.3,
    12: 1.5, 13: 1.0, 14: 0.8, 15: 0.7, 16: 0.9, 17: 1.8,
    18: 2.0, 19: 1.3, 20: 0.8, 21: 0.5, 22: 0.3, 23: 0.1,
}


def get_upload_user():
    """Get or create a system user for simulated data uploads."""
    user, _ = User.objects.get_or_create(
        username='system_simulator',
        defaults={'role': 'admin', 'is_active': True}
    )
    if not user.has_usable_password():
        user.set_password('sim_password_2026')
        user.save()
    return user


def generate_ride_records():
    """
    Generate YSU-specific ride records based on current hour.
    Peak hours (7-9 AM, 5-7 PM) produce more rides.
    Late night (2-4 AM) produces very few.
    """
    now = timezone.now()
    hour = now.hour
    multiplier = HOUR_MULTIPLIER.get(hour, 0.5)

    # Base: 2-5 rides per minute, scaled by hour multiplier
    num_rides = max(1, int(random.uniform(2, 5) * multiplier))

    spot_names = list(PARKING_SPOTS.keys())
    user = get_upload_user()
    rides_created = []

    for _ in range(num_rides):
        start_spot = random.choice(spot_names)
        end_spot = random.choice([s for s in spot_names if s != start_spot])

        # Ride time within last 1-5 minutes
        ride_time = now - timedelta(seconds=random.randint(10, 300))

        # Duration: 3-25 minutes (campus rides are short)
        duration = round(random.uniform(3.0, 25.0), 1)

        # Distance: 0.3-3.0 km (campus scale)
        distance = round(random.uniform(0.3, 3.0), 2)

        # Temperature: seasonal estimate (spring ~5-20°C)
        month = now.month
        if month in (12, 1, 2):
            temp = random.uniform(-10, 5)
        elif month in (3, 4, 5):
            temp = random.uniform(5, 22)
        elif month in (6, 7, 8):
            temp = random.uniform(22, 38)
        else:
            temp = random.uniform(5, 20)

        wind = round(random.uniform(0, 6), 1)

        ride = BikeRideData.objects.create(
            data_source='realtime_simulation',
            start_point=start_spot,
            end_point=end_spot,
            ride_datetime=ride_time,
            duration=duration,
            distance=distance,
            temperature=round(temp, 1),
            wind_speed=wind,
            status='cleaned',
            upload_user=user
        )
        rides_created.append(ride)

    return rides_created


def update_vehicle_statuses():
    """
    Update a fraction of vehicle statuses to simulate real-time changes.
    ~10% of vehicles change status each cycle. DO NOT modify parking spot coordinates.
    """
    vehicles = list(Vehicle.objects.all()[:520])
    if not vehicles:
        return 0

    num_to_update = max(1, int(len(vehicles) * 0.10))
    sample = random.sample(vehicles, min(num_to_update, len(vehicles)))

    status_transitions = {
        'available': ['ridden', 'available', 'available'],     # mostly stays available
        'ridden':    ['available', 'available', 'ridden'],     # mostly returns
        'faulty':    ['faulty', 'faulty', 'available'],        # slowly repaired
        'locked':    ['locked', 'available'],                  # unlocked occasionally
    }

    updated = 0
    for v in sample:
        options = status_transitions.get(v.status, ['available'])
        new_status = random.choice(options)
        if new_status != v.status:
            v.status = new_status
            v.save(update_fields=['status'])
            updated += 1

    return updated


def run_simulation_cycle():
    """Run one cycle of real-time data simulation."""
    try:
        now = timezone.now()
        logger.info(f"=== Simulation cycle at {now.strftime('%Y-%m-%d %H:%M:%S')} ===")

        # Generate ride records
        rides = generate_ride_records()
        ride_count = len(rides)

        # Update vehicle statuses
        vehicle_updates = update_vehicle_statuses()

        # Log to DataProcessLog
        DataProcessLog.objects.create(
            parking_spot_name=f"实时模拟: {ride_count}条骑行 + {vehicle_updates}辆车状态更新",
            actual_count=ride_count,
            status='normal'
        )

        logger.info(f"  Rides generated: {ride_count}")
        logger.info(f"  Vehicle statuses updated: {vehicle_updates}")
        logger.info(f"  Total BikeRideData: {BikeRideData.objects.count()}")

    except Exception as e:
        logger.error(f"Simulation cycle failed: {e}", exc_info=True)
        DataProcessLog.objects.create(
            parking_spot_name="实时模拟失败",
            actual_count=0,
            status='error',
            error_message=str(e)
        )


# ============ API endpoint data (called from Django views) ============
def get_realtime_status():
    """Return latest simulation status for API consumption."""
    latest_log = DataProcessLog.objects.filter(
        parking_spot_name__startswith='实时模拟'
    ).order_by('-created_at').first()

    return {
        'last_import_time': latest_log.created_at.strftime('%Y-%m-%d %H:%M:%S') if latest_log else None,
        'last_count': latest_log.actual_count if latest_log else 0,
        'total_rides': BikeRideData.objects.count(),
        'total_vehicles': Vehicle.objects.count(),
        'simulation_active': True,
    }


# ============ Main ============
if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description='YSU Bike Sharing Real-Time Data Simulator')
    parser.add_argument('--once', action='store_true', help='Run one cycle and exit')
    args = parser.parse_args()

    if args.once:
        logger.info("Running single simulation cycle...")
        run_simulation_cycle()
        logger.info("Done.")
    else:
        logger.info("Starting continuous simulation (1-minute interval)...")
        logger.info("Press Ctrl+C to stop.")

        # Run immediately on start
        run_simulation_cycle()

        # Schedule every 1 minute
        schedule.every(1).minutes.do(run_simulation_cycle)

        try:
            while True:
                schedule.run_pending()
                time.sleep(10)
        except KeyboardInterrupt:
            logger.info("Simulation stopped by user.")
