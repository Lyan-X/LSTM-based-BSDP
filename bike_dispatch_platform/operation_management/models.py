from django.db import models
# 核心修正：现在能导入全局的REGION_CHOICES（因为已移到类外）
from demand_prediction.models import PredictionResult, REGION_CHOICES

class Vehicle(models.Model):
    """运维车辆/单车模型（任务书"运维管理模块"核心）"""
    bike_id = models.CharField(max_length=30, unique=True, verbose_name="单车编号")
    status = models.CharField(
        max_length=20, 
        choices=[('normal', '正常'), ('fault', '故障'), ('maintain', '维护中')], 
        verbose_name="车辆状态"
    )
    # 引用全局导入的REGION_CHOICES（现在无报错）
    current_region = models.CharField(
        max_length=20, 
        choices=REGION_CHOICES, 
        verbose_name="当前区域"
    )
    update_time = models.DateTimeField(auto_now=True, verbose_name="更新时间")

    class Meta:
        verbose_name = "运维车辆"
        verbose_name_plural = "运维车辆"
        
    def __str__(self):
        return f"单车{self.bike_id} - {self.get_status_display()} - {self.get_current_region_display()}"