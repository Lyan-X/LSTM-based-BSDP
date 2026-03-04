"""
APScheduler integration for real-time parking spot data generation.
Runs every 1 minute (configurable) to simulate live YSU bike sharing operations.
"""
import logging
import random
from django.utils import timezone

logger = logging.getLogger('scheduler')

# ─── YSU spot type classification ────────────────────────────────────────────
_TEACHING = ['教学楼', '学院', '建筑系', '文法', '里仁', '电气', '材料', '信息']
_CANTEEN  = ['食堂', '餐厅']
_DORM     = ['组图', '至明楼', '至博楼', '至雅楼', '公寓', '宿舍']
_LIBRARY  = ['图书馆']
_GATE     = ['门', '体育场', '体育学院']


def _spot_type(name: str) -> str:
    for k in _TEACHING:
        if k in name:
            return 'teaching'
    for k in _CANTEEN:
        if k in name:
            return 'canteen'
    for k in _DORM:
        if k in name:
            return 'dorm'
    for k in _LIBRARY:
        if k in name:
            return 'library'
    for k in _GATE:
        if k in name:
            return 'gate'
    return 'other'


def _gen_counts(spot_type: str, hour: int, is_weekend: bool):
    """Return (parked, riding, fault, demand) for a spot at a given hour."""
    # Peak-hour flags
    peak_morning = 7 <= hour <= 9
    peak_noon    = 11 <= hour <= 13
    peak_evening = 17 <= hour <= 19
    is_peak = peak_morning or peak_noon or peak_evening
    is_night = 0 <= hour <= 5

    if is_night:
        parked = random.randint(18, 30)
        demand = random.randint(0, 4)
    elif is_peak:
        if spot_type == 'teaching':
            parked = random.randint(3, 10)
            demand = parked + random.randint(5, 15)  # high shortage
        elif spot_type == 'canteen' and peak_noon:
            parked = random.randint(5, 14)
            demand = parked + random.randint(8, 18)  # lunch rush
        elif spot_type == 'dorm':
            parked = random.randint(8, 18)
            demand = parked + random.randint(3, 10)
        elif spot_type == 'library':
            parked = random.randint(6, 14)
            demand = parked + random.randint(2, 8)
        elif spot_type == 'gate':
            parked = random.randint(4, 12)
            demand = parked + random.randint(3, 9)
        else:
            parked = random.randint(8, 18)
            demand = parked + random.randint(1, 6)
    else:
        # Off-peak: roughly balanced
        parked = random.randint(12, 25)
        demand = parked + random.randint(-5, 5)

    # Weekend: more bikes parked (less commuting)
    if is_weekend:
        parked = min(40, int(parked * 1.2))

    riding = random.randint(3, 15)
    fault  = random.randint(1, 3)
    parked = max(0, parked)
    demand = max(0, demand)
    return parked, riding, fault, demand


# ─── Main job function ────────────────────────────────────────────────────────
def generate_real_time_data():
    """
    Generate one batch of real-time data for all parking spots.
    Called by APScheduler every SCHEDULER_INTERVAL_MINUTES (default 1).
    Also auto-creates dispatch tasks when gap >= 10.
    """
    try:
        from data_process.models import ParkingSpotRealTime
        from operation_management.models import ParkingSpot, ScheduleTask

        now      = timezone.now()
        hour     = now.hour
        weekday  = now.weekday()
        is_wknd  = weekday >= 5

        spots = list(ParkingSpot.objects.all())
        if not spots:
            logger.warning('[Scheduler] No parking spots found — skipping.')
            return

        records    = []
        deficit_list = []  # (spot, gap) pairs needing dispatch

        for spot in spots:
            stype = _spot_type(spot.spot_name)
            parked, riding, fault, demand = _gen_counts(stype, hour, is_wknd)

            records.append(ParkingSpotRealTime(
                parking_spot=spot,
                collect_time=now,
                parked_count=parked,
                riding_count=riding,
                fault_count=fault,
                demand_count=demand,
            ))

            gap = demand - parked
            if gap >= 10:
                deficit_list.append((spot, gap, parked))

        # Bulk-insert all records at once
        ParkingSpotRealTime.objects.bulk_create(records, batch_size=100)

        # ── Auto-dispatch: pair surplus spots → deficit spots ──────────────
        if deficit_list:
            surplus_map = {
                r.parking_spot_id: (r.parked_count - r.demand_count)
                for r in records
                if (r.parked_count - r.demand_count) >= 5
            }
            surplus_ids = sorted(surplus_map, key=lambda k: surplus_map[k], reverse=True)

            for spot, gap, _ in deficit_list:
                if not surplus_ids:
                    break
                src_id = surplus_ids[0]
                src_spot = ParkingSpot.objects.filter(pk=src_id).first()
                if not src_spot:
                    surplus_ids.pop(0)
                    continue
                transfer = min(gap, surplus_map[src_id])
                ScheduleTask.objects.create(
                    task_type='auto_dispatch',
                    start_location=src_spot.spot_name,
                    end_location=spot.spot_name,
                    dispatch_count=transfer,
                    priority='high' if gap >= 15 else 'medium',
                    status='pending',
                    predicted_time=now,
                )
                surplus_map[src_id] -= transfer
                if surplus_map[src_id] < 5:
                    surplus_ids.pop(0)

        # ── Prune old records (keep latest 48 h to save DB space) ──────────
        cutoff = now - timezone.timedelta(hours=48)
        deleted, _ = ParkingSpotRealTime.objects.filter(collect_time__lt=cutoff).delete()

        logger.info(
            '[Scheduler] %d records written at %s | dispatch tasks: %d | pruned: %d',
            len(records), now.strftime('%H:%M:%S'), len(deficit_list), deleted
        )

    except Exception as exc:
        logger.error('[Scheduler] generate_real_time_data failed: %s', exc, exc_info=True)


# ─── Scheduler lifecycle ──────────────────────────────────────────────────────
_scheduler = None

SCHEDULER_INTERVAL_MINUTES = 1   # change to 5 for slower cadence


def start_scheduler():
    """Start the APScheduler BackgroundScheduler (idempotent)."""
    global _scheduler
    from apscheduler.schedulers.background import BackgroundScheduler
    from apscheduler.triggers.interval import IntervalTrigger

    if _scheduler is not None and _scheduler.running:
        logger.warning('[Scheduler] Already running — skipping duplicate start.')
        return

    _scheduler = BackgroundScheduler(
        timezone='Asia/Shanghai',
        job_defaults={'misfire_grace_time': 60, 'coalesce': True},
    )
    _scheduler.add_job(
        generate_real_time_data,
        trigger=IntervalTrigger(minutes=SCHEDULER_INTERVAL_MINUTES),
        id='realtime_data_job',
        name='YSU Realtime Parking Data',
        replace_existing=True,
    )
    _scheduler.start()
    logger.info(
        '[Scheduler] Started. Interval: %d min. First run at next tick.',
        SCHEDULER_INTERVAL_MINUTES
    )


def stop_scheduler():
    """Gracefully stop the scheduler (called on server shutdown)."""
    global _scheduler
    if _scheduler and _scheduler.running:
        _scheduler.shutdown(wait=False)
        logger.info('[Scheduler] Stopped.')
