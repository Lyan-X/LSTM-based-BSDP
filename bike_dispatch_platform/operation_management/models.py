from django.db import models

from bike_dispatch_platform.system_support.models import User


class ParkingSpot(models.Model):
    """Canonical station master data."""

    SPOT_TYPE_CHOICES = [
        ("academic", "教学科研"),
        ("residential", "生活居住"),
        ("comprehensive", "综合服务"),
        ("transit", "交通枢纽"),
    ]
    CAMPUS_AREA_CHOICES = [
        ("west", "西校区"),
        ("east", "东校区"),
        ("mixed", "跨区"),
    ]

    parking_spot_id = models.AutoField(primary_key=True, verbose_name="站点主键")
    ysu_id = models.IntegerField(verbose_name="站点编号", default=1)
    spot_name = models.CharField(max_length=100, unique=True, verbose_name="站点名称")
    longitude = models.FloatField(verbose_name="经度")
    latitude = models.FloatField(verbose_name="纬度")
    max_capacity = models.PositiveIntegerField(default=40, verbose_name="最大承载容量")
    washington_station_id = models.CharField(max_length=32, blank=True, verbose_name="华盛顿映射站点ID")
    washington_station_name = models.CharField(max_length=255, blank=True, verbose_name="华盛顿映射站点名称")
    initial_inventory = models.PositiveIntegerField(default=0, verbose_name="初始车辆投放数")
    low_warning_threshold = models.PositiveIntegerField(default=8, verbose_name="低存量预警阈值")
    high_warning_threshold = models.PositiveIntegerField(default=32, verbose_name="高饱和预警阈值")
    notes = models.TextField(blank=True, verbose_name="运维备注")
    is_active = models.BooleanField(default=True, verbose_name="是否启用")
    campus_area = models.CharField(
        max_length=20,
        choices=CAMPUS_AREA_CHOICES,
        default="mixed",
        verbose_name="所属校区",
    )
    spot_type = models.CharField(
        max_length=20,
        choices=SPOT_TYPE_CHOICES,
        default="academic",
        verbose_name="站点类型",
    )
    service_radius = models.IntegerField(default=100, verbose_name="服务半径(米)")
    create_time = models.DateTimeField(auto_now_add=True, verbose_name="创建时间")

    class Meta:
        verbose_name = "站点主数据"
        verbose_name_plural = "站点主数据"
        ordering = ["ysu_id"]

    def __str__(self):
        return f"{self.ysu_id}-{self.spot_name}"


class Vehicle(models.Model):
    """Vehicle registry for audit and dispatch statistics."""

    STATUS_CHOICES = [
        ("available", "可用"),
        ("ridden", "骑行中"),
        ("faulty", "故障"),
        ("locked", "锁定"),
        ("in_transit", "调度在途"),
    ]

    id = models.CharField(max_length=30, primary_key=True, verbose_name="车辆编号")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="available", verbose_name="车辆状态")
    latitude = models.FloatField(verbose_name="纬度")
    longitude = models.FloatField(verbose_name="经度")
    update_time = models.DateTimeField(auto_now=True, verbose_name="更新时间")
    parking_spot = models.ForeignKey(
        ParkingSpot,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="所属站点",
    )

    class Meta:
        verbose_name = "运维车辆"
        verbose_name_plural = "运维车辆"
        ordering = ["id"]

    def __str__(self):
        return f"{self.id}-{self.get_status_display()}"


class ScheduleTask(models.Model):
    """Dispatch task driven by station-level forecast gaps."""

    PRIORITY_CHOICES = [
        ("high", "高"),
        ("medium", "中"),
        ("low", "低"),
    ]
    STATUS_CHOICES = [
        ("pending", "待处理"),
        ("in_progress", "进行中"),
        ("completed", "已完成"),
        ("cancelled", "已取消"),
    ]

    id = models.AutoField(primary_key=True, verbose_name="任务编号")
    task_type = models.CharField(max_length=50, default="vehicle_dispatch", verbose_name="任务类型")
    from_station = models.ForeignKey(
        ParkingSpot,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="dispatch_source_tasks",
        verbose_name="调出站点",
    )
    to_station = models.ForeignKey(
        ParkingSpot,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="dispatch_target_tasks",
        verbose_name="调入站点",
    )
    related_vehicle = models.ForeignKey(
        Vehicle,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="schedule_tasks",
        verbose_name="关联车辆",
    )
    start_location = models.CharField(max_length=100, verbose_name="起始位置")
    end_location = models.CharField(max_length=100, verbose_name="目标位置")
    dispatch_count = models.IntegerField(default=0, verbose_name="调度数量")
    priority = models.CharField(max_length=20, choices=PRIORITY_CHOICES, default="medium", verbose_name="优先级")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending", verbose_name="任务状态")
    predicted_gap = models.FloatField(default=0, verbose_name="触发时预测缺口")
    distance_cost = models.FloatField(default=0, verbose_name="调度距离成本")
    prediction_batch_time = models.DateTimeField(null=True, blank=True, verbose_name="预测批次时间")
    predicted_time = models.DateTimeField(null=True, blank=True, verbose_name="预测时刻")
    reason = models.TextField(blank=True, verbose_name="调度原因")
    create_time = models.DateTimeField(auto_now_add=True, verbose_name="创建时间")

    class Meta:
        verbose_name = "调度任务"
        verbose_name_plural = "调度任务"
        ordering = ["-create_time"]

    def __str__(self):
        return f"task#{self.id} {self.start_location}->{self.end_location}"


class ScheduleEvaluation(models.Model):
    """Dispatch evaluation record."""

    task = models.OneToOneField(ScheduleTask, on_delete=models.CASCADE, verbose_name="关联任务")
    completion_rate = models.FloatField(verbose_name="完成率(%)")
    time_efficiency = models.FloatField(verbose_name="时间效率(分钟)")
    cost_efficiency = models.FloatField(null=True, blank=True, verbose_name="成本效率")
    satisfaction_score = models.FloatField(null=True, blank=True, verbose_name="满意度评分")
    evaluation_time = models.DateTimeField(auto_now_add=True, verbose_name="评估时间")
    evaluator = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, verbose_name="评估人")
    notes = models.TextField(blank=True, verbose_name="评估备注")

    class Meta:
        verbose_name = "调度效果评估"
        verbose_name_plural = "调度效果评估"

    def __str__(self):
        return f"evaluation#{self.task_id}"


class VehicleLocationHistory(models.Model):
    """Vehicle movement and status change history."""

    vehicle = models.ForeignKey(Vehicle, on_delete=models.CASCADE, related_name="location_histories", verbose_name="车辆")
    previous_status = models.CharField(max_length=20, blank=True, verbose_name="变更前状态")
    current_status = models.CharField(max_length=20, blank=True, verbose_name="变更后状态")
    change_reason = models.CharField(max_length=200, blank=True, verbose_name="变更原因")
    changed_at = models.DateTimeField(auto_now_add=True, verbose_name="变更时间")
    current_station = models.ForeignKey(
        ParkingSpot,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="vehicle_history_to",
        verbose_name="当前站点",
    )
    previous_station = models.ForeignKey(
        ParkingSpot,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="vehicle_history_from",
        verbose_name="前一站点",
    )

    class Meta:
        verbose_name = "车辆位置轨迹"
        verbose_name_plural = "车辆位置轨迹"
        ordering = ["-changed_at"]

    def __str__(self):
        return f"{self.vehicle_id}-{self.changed_at:%Y-%m-%d %H:%M}"


class OperatorTrack(models.Model):
    """Operator position trace."""

    operator = models.ForeignKey(User, on_delete=models.CASCADE, related_name="tracks", verbose_name="运维人员")
    latitude = models.FloatField(verbose_name="纬度")
    longitude = models.FloatField(verbose_name="经度")
    task = models.ForeignKey(
        ScheduleTask,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="tracks",
        verbose_name="关联任务",
    )
    track_time = models.DateTimeField(auto_now_add=True, verbose_name="记录时间")
    description = models.CharField(max_length=200, blank=True, verbose_name="位置描述")

    class Meta:
        verbose_name = "运维轨迹"
        verbose_name_plural = "运维轨迹"
        ordering = ["-track_time"]

    def __str__(self):
        return f"{self.operator.username}-{self.track_time:%Y-%m-%d %H:%M}"
