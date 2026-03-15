from django.db import models

from bike_dispatch_platform.operation_management.models import ParkingSpot
from bike_dispatch_platform.system_support.models import User


class BikeRideData(models.Model):
    """Raw ride data imported for analysis and audit."""

    data_source = models.CharField(max_length=50, verbose_name="数据来源")
    start_point = models.CharField(max_length=100, verbose_name="骑行起点")
    end_point = models.CharField(max_length=100, verbose_name="骑行终点")
    ride_datetime = models.DateTimeField(verbose_name="骑行时间")
    duration = models.FloatField(default=0.0, verbose_name="骑行时长")
    distance = models.FloatField(default=0.0, verbose_name="骑行距离")
    temperature = models.FloatField(default=25.0, verbose_name="温度")
    wind_speed = models.FloatField(default=0.0, verbose_name="风速")
    status = models.CharField(max_length=20, default="cleaned", verbose_name="数据状态")
    upload_user = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name="上传用户")
    create_time = models.DateTimeField(auto_now_add=True, verbose_name="创建时间")

    class Meta:
        verbose_name = "骑行数据"
        verbose_name_plural = "骑行数据"

    def __str__(self):
        return f"{self.ride_datetime} {self.start_point}->{self.end_point}"


class WeatherData(models.Model):
    """Weather data used by the runtime services."""

    area = models.CharField(max_length=100, verbose_name="区域")
    date = models.DateField(verbose_name="日期")
    temperature = models.FloatField(verbose_name="温度(℃)")
    humidity = models.FloatField(verbose_name="湿度(%)")
    wind_speed = models.FloatField(verbose_name="风速(m/s)")
    rainfall = models.FloatField(default=0, verbose_name="降雨量(mm)")
    weather_type = models.CharField(
        max_length=20,
        choices=[("sunny", "晴"), ("cloudy", "阴"), ("rain", "雨")],
        verbose_name="天气类型",
    )

    class Meta:
        verbose_name = "天气数据"
        verbose_name_plural = "天气数据"
        unique_together = ("area", "date")

    def __str__(self):
        return f"{self.area}-{self.date}-{self.weather_type}"


class ParkingSpotSnapshot(models.Model):
    """Hourly station snapshot used for training and history inspection."""

    parking_spot = models.ForeignKey(ParkingSpot, on_delete=models.CASCADE, verbose_name="站点")
    timestamp = models.DateTimeField(verbose_name="记录时间")
    parked_count = models.IntegerField(default=0, verbose_name="停放车辆数")
    riding_count = models.IntegerField(default=0, verbose_name="骑行中车辆数")
    fault_count = models.IntegerField(default=0, verbose_name="故障车辆数")

    class Meta:
        verbose_name = "站点小时快照"
        verbose_name_plural = "站点小时快照"
        unique_together = ("parking_spot", "timestamp")
        ordering = ["-timestamp"]

    def __str__(self):
        return f"{self.parking_spot.spot_name}-{self.timestamp:%Y-%m-%d %H:%M}"


class DataProcessLog(models.Model):
    """Processing log for import and validation jobs."""

    parking_spot = models.ForeignKey(
        ParkingSpot,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="站点",
    )
    actual_count = models.IntegerField(default=0, verbose_name="真实停放量")
    status = models.CharField(
        max_length=20,
        choices=[("normal", "正常"), ("error", "异常")],
        default="normal",
        verbose_name="处理状态",
    )
    error_message = models.TextField(null=True, blank=True, verbose_name="错误信息")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="创建时间")

    class Meta:
        verbose_name = "数据处理日志"
        verbose_name_plural = "数据处理日志"

    def __str__(self):
        return f"{self.created_at:%Y-%m-%d %H:%M:%S}-{self.status}"


class ParkingSpotRealTime(models.Model):
    """10-second station runtime state."""

    parking_spot = models.ForeignKey(ParkingSpot, on_delete=models.CASCADE, verbose_name="站点")
    collect_time = models.DateTimeField(verbose_name="采集时间")
    parked_count = models.IntegerField(default=0, verbose_name="当前停放车辆数")
    riding_count = models.IntegerField(default=0, verbose_name="当前骑行中车辆数")
    in_transit_count = models.IntegerField(default=0, verbose_name="当前在途车辆数")
    fault_count = models.IntegerField(default=0, verbose_name="当前故障车辆数")
    demand_count = models.IntegerField(default=0, verbose_name="当前需求量")

    class Meta:
        verbose_name = "实时站点状态"
        verbose_name_plural = "实时站点状态"
        ordering = ["-collect_time", "parking_spot_id"]

    def __str__(self):
        return f"{self.parking_spot.spot_name}-{self.collect_time:%Y-%m-%d %H:%M:%S}"
