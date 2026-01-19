from django.db import models
from system_support.models import User

class Vehicle(models.Model):
    """车辆状态模型（任务书"车辆状态实时监控"）"""
    vehicle_id = models.CharField(max_length=50, unique=True, verbose_name="车辆编号")
    STATUS_CHOICES = [('available', '可用'), ('maintenance', '维修中'), ('in_use', '使用中')]
    status = models.CharField(max_length=20, default='available', choices=STATUS_CHOICES, verbose_name="状态")
    current_region = models.CharField(max_length=20, choices=PredictionResult.REGION_CHOICES, verbose_name="当前区域")
    update_time = models.DateTimeField(auto_now=True, verbose_name="更新时间")

class ScheduleTask(models.Model):
    """调度任务模型（任务书"调度任务生成与分配"）"""
    task_id = models.CharField(max_length=50, unique=True, verbose_name="任务编号")
    target_region = models.CharField(max_length=20, choices=PredictionResult.REGION_CHOICES, verbose_name="目标区域")
    demand_count = models.IntegerField(verbose_name="需求车辆数")
    assign_to = models.ForeignKey(User, on_delete=models.CASCADE, related_name="assigned_tasks", verbose_name="分配给")
    STATUS_CHOICES = [('pending', '待执行'), ('executing', '执行中'), ('completed', '已完成')]
    status = models.CharField(max_length=20, default='pending', choices=STATUS_CHOICES, verbose_name="任务状态")
    create_time = models.DateTimeField(auto_now_add=True, verbose_name="创建时间")
    complete_time = models.DateTimeField(null=True, blank=True, verbose_name="完成时间")

class ScheduleEvaluation(models.Model):
    """调度效果评估（任务书要求）"""
    task = models.OneToOneField(ScheduleTask, on_delete=models.CASCADE, verbose_name="关联任务")
    actual_demand = models.IntegerField(verbose_name="实际需求数")
    satisfaction_rate = models.FloatField(verbose_name="需求满足率（%）")
    evaluation_time = models.DateTimeField(auto_now_add=True, verbose_name="评估时间")