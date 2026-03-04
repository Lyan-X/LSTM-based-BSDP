#!/usr/bin/env python3
"""
generate_1day_training_data.py

一键生成 1 天 (24 h) 历史训练数据，时间粒度：每 5 分钟一条。
数据写入 ParkingSpotRealTime 表，共 62 个停车点 × 24h × 12条/h = 17,856 条。

执行方式（项目根目录下）：
    python generate_1day_training_data.py
"""
import os
import sys
import random
from datetime import timedelta

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), 'bike_dispatch_platform'))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'bike_dispatch_platform.settings')

import django
django.setup()

from django.utils import timezone
from data_process.models import ParkingSpotRealTime
from operation_management.models import ParkingSpot
from operation_management.scheduler import _spot_type, _gen_counts


def run():
    print('=' * 60)
    print('  Generating 1-day training data (5-min interval × 62 spots)')
    print('=' * 60)

    spots = list(ParkingSpot.objects.all())
    if not spots:
        print('[ERROR] No parking spots found. Please start the server once to seed spots.')
        return

    now       = timezone.now().replace(second=0, microsecond=0)
    start     = now - timedelta(days=1)
    interval  = timedelta(minutes=5)

    total_steps = int(timedelta(days=1) / interval)  # = 288
    expected    = total_steps * len(spots)
    print(f'  Spots: {len(spots)} | Steps: {total_steps} | Expected records: {expected}')
    print(f'  Range: {start:%Y-%m-%d %H:%M} → {now:%Y-%m-%d %H:%M}')

    batch   = []
    written = 0
    step    = 0
    ts      = start

    while ts <= now:
        hour    = ts.hour
        weekday = ts.weekday()
        is_wknd = weekday >= 5

        for spot in spots:
            stype = _spot_type(spot.spot_name)
            parked, riding, fault, demand = _gen_counts(stype, hour, is_wknd)
            batch.append(ParkingSpotRealTime(
                parking_spot=spot,
                collect_time=ts,
                parked_count=parked,
                riding_count=riding,
                fault_count=fault,
                demand_count=demand,
            ))

        if len(batch) >= 2000:
            ParkingSpotRealTime.objects.bulk_create(batch, ignore_conflicts=True)
            written += len(batch)
            batch = []

        step += 1
        if step % 48 == 0:  # progress every 4 hours
            print(f'  ... {ts:%H:%M} ({step}/{total_steps} steps done)')

        ts += interval

    if batch:
        ParkingSpotRealTime.objects.bulk_create(batch, ignore_conflicts=True)
        written += len(batch)

    total_in_db = ParkingSpotRealTime.objects.count()
    print(f'\n  Done! Written this run: {written}')
    print(f'  Total ParkingSpotRealTime records in DB: {total_in_db}')
    print('=' * 60)


if __name__ == '__main__':
    run()
