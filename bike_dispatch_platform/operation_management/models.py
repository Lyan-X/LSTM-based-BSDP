from django.db import models
from django.utils import timezone
from demand_prediction.models import PredictionResult, REGION_CHOICES
from system_support.models import User


class Vehicle(models.Model):
    """运维车辆/单车模型（任务书"运维管理模块"核心）"""
    bike_id = models.CharField(max_length=30, unique=True, verbose_name="单车编号")
    status = models.CharField(
        max_length=20, 
        choices=[('normal', '正常'), ('fault', '故障'), ('maintain', '维护中'), ('offline', '离线')], 
        default='normal',
        verbose_name="车辆状态"
    )
    current_region = models.CharField(
        max_length=20, 
        choices=REGION_CHOICES, 
        verbose_name="当前区域"
    )
    latitude = models.FloatField(null=True, blank=True, verbose_name="纬度")
    longitude = models.FloatField(null=True, blank=True, verbose_name="经度")
    update_time = models.DateTimeField(auto_now=True, verbose_name="更新时间")

    class Meta:
        verbose_name = "运维车辆"
        verbose_name_plural = "运维车辆"
        ordering = ['-update_time']
        
    def __str__(self):
        return f"单车{self.bike_id} - {self.get_status_display()} - {self.get_current_region_display()}"


class ScheduleTask(models.Model):
    """调度任务模型（任务书"调度任务生成与分配"要求）"""
    task_id = models.CharField(max_length=50, unique=True, verbose_name="任务编号")
    target_region = models.CharField(max_length=20, choices=REGION_CHOICES, verbose_name="目标区域")
    source_region = models.CharField(max_length=20, choices=REGION_CHOICES, null=True, blank=True, verbose_name="源区域")
    demand_count = models.IntegerField(verbose_name="需求车辆数")
    actual_count = models.IntegerField(default=0, verbose_name="实际调度数")
    
    STATUS_CHOICES = [
        ('pending', '待分配'),
        ('assigned', '已分配'),
        ('in_progress', '进行中'),
        ('completed', '已完成'),
        ('cancelled', '已取消'),
    ]
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending', verbose_name="任务状态")
    
    assign_to = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='assigned_tasks',
        verbose_name="分配给"
    )
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='created_tasks',
        verbose_name="创建人"
    )
    prediction_result = models.ForeignKey(
        PredictionResult,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="关联预测结果"
    )
    create_time = models.DateTimeField(auto_now_add=True, verbose_name="创建时间")
    complete_time = models.DateTimeField(null=True, blank=True, verbose_name="完成时间")
    description = models.TextField(blank=True, verbose_name="任务描述")

    class Meta:
        verbose_name = "调度任务"
        verbose_name_plural = "调度任务"
        ordering = ['-create_time']
    
    def __str__(self):
        return f"{self.task_id} - {self.get_target_region_display()} - {self.get_status_display()}"


class ScheduleEvaluation(models.Model):
    """调度效果评估模型（任务书"调度效果评估"要求）"""
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
        return f"{self.task.task_id} - 完成率：{self.completion_rate}%"


class OperatorTrack(models.Model):
    """运维人员轨迹追踪模型（任务书"运维人员轨迹追踪"要求）"""
    operator = models.ForeignKey(User, on_delete=models.CASCADE, related_name='tracks', verbose_name="运维人员")
    latitude = models.FloatField(verbose_name="纬度")
    longitude = models.FloatField(verbose_name="经度")
    task = models.ForeignKey(
        ScheduleTask,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='tracks',
        verbose_name="关联任务"
    )
    track_time = models.DateTimeField(auto_now_add=True, verbose_name="记录时间")
    description = models.CharField(max_length=200, blank=True, verbose_name="位置描述")

    class Meta:
        verbose_name = "运维轨迹"
        verbose_name_plural = "运维轨迹"
        ordering = ['-track_time']
    
    def __str__(self):
        return f"{self.operator.username} - {self.track_time.strftime('%Y-%m-%d %H:%M')}"