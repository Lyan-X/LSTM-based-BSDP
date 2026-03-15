from django.db import models

from bike_dispatch_platform.operation_management.models import ParkingSpot
from bike_dispatch_platform.system_support.models import User

REGION_CHOICES = [
    ("west_campus", "西校区（教学区）"),
    ("east_campus", "东校区（教学区）"),
    ("dorm_area", "学生宿舍区"),
    ("library_area", "图书馆周边"),
    ("canteen_area", "食堂周边"),
    ("gate_area", "校门出入口"),
]


class PredictionResult(models.Model):
    """Legacy regional prediction result kept for compatibility pages."""

    TIME_PERIOD_CHOICES = [
        ("morning", "早高峰（7-9点）"),
        ("noon", "午间（11-13点）"),
        ("evening", "晚高峰（17-19点）"),
        ("night", "夜间（21-23点）"),
    ]
    MODEL_CHOICES = [("LSTM", "LSTM模型"), ("BP", "BP神经网络")]

    region = models.CharField(max_length=20, choices=REGION_CHOICES, verbose_name="预测区域")
    time_period = models.CharField(max_length=20, choices=TIME_PERIOD_CHOICES, verbose_name="预测时段")
    predict_date = models.DateField(verbose_name="预测日期")
    predict_hour = models.IntegerField(verbose_name="预测小时", choices=[(i, f"{i}:00") for i in range(24)], default=0)
    demand_count = models.IntegerField(verbose_name="调度需求车辆数")
    supply_count = models.IntegerField(default=0, verbose_name="当前供给车辆数")
    model_used = models.CharField(max_length=20, choices=MODEL_CHOICES, verbose_name="使用模型")
    accuracy = models.FloatField(verbose_name="预测准确率(%)")
    create_time = models.DateTimeField(auto_now_add=True, verbose_name="生成时间")
    user = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name="操作用户")

    class Meta:
        verbose_name = "区域级预测结果"
        verbose_name_plural = "区域级预测结果"
        unique_together = ["region", "predict_date", "predict_hour"]

    def __str__(self):
        return f"{self.predict_date} {self.predict_hour}:00 {self.region}"


class ModelTrainLog(models.Model):
    """Training log for the station-level 48h LSTM model."""

    train_date = models.DateField(verbose_name="训练日期")
    start_time = models.DateTimeField(verbose_name="开始时间")
    end_time = models.DateTimeField(verbose_name="结束时间")
    duration = models.IntegerField(verbose_name="训练时长(秒)")
    mae = models.FloatField(verbose_name="平均绝对误差")
    rmse = models.FloatField(verbose_name="均方根误差")
    r2 = models.FloatField(verbose_name="R2")
    model_filename = models.CharField(max_length=255, verbose_name="模型文件名")
    model_type = models.CharField(max_length=32, default="lstm_48h_station", verbose_name="模型类型")
    device = models.CharField(max_length=32, default="cpu", verbose_name="训练设备")
    model_path = models.CharField(max_length=255, blank=True, verbose_name="模型文件路径")
    metrics_path = models.CharField(max_length=255, blank=True, verbose_name="指标文件路径")
    status = models.CharField(
        max_length=20,
        choices=[("success", "成功"), ("failed", "失败")],
        default="success",
        verbose_name="训练状态",
    )
    error_message = models.TextField(null=True, blank=True, verbose_name="错误信息")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="创建时间")

    class Meta:
        verbose_name = "模型训练日志"
        verbose_name_plural = "模型训练日志"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.train_date}-{self.model_filename}-{self.status}"


class StationPrediction(models.Model):
    """Station-level 48h prediction output."""

    station = models.ForeignKey(ParkingSpot, on_delete=models.CASCADE, verbose_name="站点")
    batch_time = models.DateTimeField(verbose_name="预测批次时间")
    prediction_hour = models.DateTimeField(verbose_name="预测目标小时")
    net_flow_prediction = models.FloatField(verbose_name="预测净流量")
    inventory_prediction = models.FloatField(verbose_name="预测库存")
    model_version = models.CharField(max_length=64, verbose_name="模型版本")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="创建时间")

    class Meta:
        verbose_name = "站点级预测结果"
        verbose_name_plural = "站点级预测结果"
        unique_together = ("station", "batch_time", "prediction_hour")
        ordering = ["station_id", "prediction_hour"]

    def __str__(self):
        return f"{self.station.spot_name}@{self.prediction_hour:%Y-%m-%d %H:%M}"
