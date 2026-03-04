from django.db import models
from system_support.models import User  # 关联自定义用户模型
from operation_management.models import ParkingSpot  # 关联停车点模型

class BikeRideData(models.Model):
    """骑行数据模型（任务书"数据仓库"核心）"""
    # 数据来源（公开数据集/本地采集等）
    data_source = models.CharField(max_length=50, verbose_name="数据来源")
    # 骑行起点/终点
    start_point = models.CharField(max_length=100, verbose_name="骑行起点")
    end_point = models.CharField(max_length=100, verbose_name="骑行终点")
    # 骑行时间
    ride_datetime = models.DateTimeField(verbose_name="骑行时间")
    # 骑行时长（分钟）
    duration = models.FloatField(default=0.0, verbose_name="骑行时长")
    # 骑行距离（公里）
    distance = models.FloatField(default=0.0, verbose_name="骑行距离")
    # 温度和风速字段
    temperature = models.FloatField(default=25.0, verbose_name="温度")
    wind_speed = models.FloatField(default=0.0, verbose_name="风速")
    # 【可选优化】用外键关联WeatherData，替代冗余的天气字段
    # weather = models.ForeignKey(
    #     "WeatherData",
    #     on_delete=models.SET_NULL,
    #     null=True,
    #     blank=True,
    #     verbose_name="关联天气数据"
    # )
    # 数据状态（原始/清洗后）
    status = models.CharField(max_length=20, default="cleaned", verbose_name="数据状态")
    # 上传用户（关联系统用户）
    upload_user = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name="上传用户")
    # 自动记录创建时间
    create_time = models.DateTimeField(auto_now_add=True, verbose_name="创建时间")

    class Meta:
        verbose_name = "骑行数据"
        verbose_name_plural = "骑行数据"

    def __str__(self):
        return f"{self.ride_datetime} - {self.start_point}→{self.end_point}"

class WeatherData(models.Model):
    """天气数据模型（任务书“数据处理模块”要求的关联数据）"""
    area = models.CharField(max_length=100, verbose_name="区域")  # 与骑行数据的start_point匹配（扩长度）
    date = models.DateField(verbose_name="日期")
    temperature = models.FloatField(verbose_name="温度(℃)")
    humidity = models.FloatField(verbose_name="湿度(%)")
    wind_speed = models.FloatField(verbose_name="风速(m/s)")
    rainfall = models.FloatField(default=0, verbose_name="降雨量(mm)")
    weather_type = models.CharField(
        max_length=20,
        choices=[("sunny", "晴"), ("cloudy", "阴"), ("rain", "雨")],  # 标准化取值
        verbose_name="天气类型"
    )

    class Meta:
        verbose_name = "天气数据"
        verbose_name_plural = "天气数据"
        unique_together = ("area", "date")  # 避免同一区域同一天重复数据

    def __str__(self):
        return f"{self.area} - {self.date} - {self.weather_type}"


class ParkingSpotSnapshot(models.Model):
    """Hourly parking spot vehicle count snapshot (core data for training & display)"""
    parking_spot = models.ForeignKey(ParkingSpot, on_delete=models.CASCADE, verbose_name="停车点")
    timestamp = models.DateTimeField(verbose_name="记录时间")
    parked_count = models.IntegerField(default=0, verbose_name="停放车辆数")
    riding_count = models.IntegerField(default=0, verbose_name="骑行中车辆数")
    fault_count = models.IntegerField(default=0, verbose_name="故障车辆数")

    class Meta:
        verbose_name = "停车点快照"
        verbose_name_plural = "停车点快照"
        unique_together = ("parking_spot", "timestamp")
        ordering = ['-timestamp']

    def __str__(self):
        return f"{self.parking_spot.spot_name} {self.timestamp:%Y-%m-%d %H:00} parked={self.parked_count}"


class DataProcessLog(models.Model):
    """数据处理日志模型（用于记录数据闭环过程）"""
    # 停车点信息
    parking_spot = models.ForeignKey(ParkingSpot, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="停车点")
    # 实际停车量
    actual_count = models.IntegerField(default=0, verbose_name="真实停车量")
    # 处理状态
    status = models.CharField(
        max_length=20,
        choices=[("normal", "正常"), ("error", "异常")],
        default="normal",
        verbose_name="处理状态"
    )
    # 错误信息
    error_message = models.TextField(null=True, blank=True, verbose_name="错误信息")
    # 自动记录创建时间
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="创建时间")

    class Meta:
        verbose_name = "数据处理日志"
        verbose_name_plural = "数据处理日志"

    def __str__(self):
        parking_spot_name = self.parking_spot.spot_name if self.parking_spot else "未知"
        return f"{self.created_at} - {parking_spot_name} - {self.status}"


class ParkingSpotRealTime(models.Model):
    """实时停车点数据模型"""
    id = models.AutoField(primary_key=True, verbose_name="ID")
    parking_spot = models.ForeignKey(ParkingSpot, on_delete=models.CASCADE, verbose_name="停车点")
    collect_time = models.DateTimeField(verbose_name="数据采集时刻")
    parked_count = models.IntegerField(default=0, verbose_name="当前时刻停放车辆数")
    riding_count = models.IntegerField(default=0, verbose_name="当前时刻骑行中车辆数")
    fault_count = models.IntegerField(default=0, verbose_name="当前时刻故障车辆数")
    demand_count = models.IntegerField(default=0, verbose_name="当前时刻基于用户行为的需求量")

    class Meta:
        verbose_name = "实时停车点数据"
        verbose_name_plural = "实时停车点数据"
        ordering = ['-collect_time']

    def __str__(self):
        return f"{self.parking_spot.spot_name} - {self.collect_time} - 停放: {self.parked_count} - 骑行: {self.riding_count} - 故障: {self.fault_count} - 需求: {self.demand_count}"