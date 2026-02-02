from django.db import models
from django.utils import timezone
from system_support.models import User


class ParkingSpot(models.Model):
    """停车点模型"""
    id = models.CharField(max_length=30, primary_key=True, verbose_name="停车点编号")
    name = models.CharField(max_length=100, verbose_name="停车点名称")
    latitude = models.FloatField(verbose_name="纬度")
    longitude = models.FloatField(verbose_name="经度")
    service_radius = models.IntegerField(default=100, verbose_name="服务半径(米)")
    create_time = models.DateTimeField(auto_now_add=True, verbose_name="创建时间")

    class Meta:
        verbose_name = "停车点"
        verbose_name_plural = "停车点"

    def __str__(self):
        return self.name


class Vehicle(models.Model):
    """运维车辆/单车模型（任务书"运维管理模块"核心）"""
    id = models.CharField(max_length=30, primary_key=True, verbose_name="车辆编号")
    status = models.CharField(
        max_length=20, 
        choices=[('available', '可用'), ('ridden', '已骑行'), ('faulty', '故障'), ('locked', '锁定')], 
        default='available',
        verbose_name="车辆状态"
    )
    latitude = models.FloatField(verbose_name="纬度")
    longitude = models.FloatField(verbose_name="经度")
    update_time = models.DateTimeField(auto_now=True, verbose_name="更新时间")
    parking_spot_id = models.CharField(max_length=30, verbose_name="所属停车点ID")

    class Meta:
        verbose_name = "运维车辆"
        verbose_name_plural = "运维车辆"
        ordering = ['-update_time']
        
    def __str__(self):
        return f"车辆{self.id} - {self.get_status_display()}"


class ScheduleTask(models.Model):
    """调度任务模型（任务书"调度任务生成与分配"要求）"""
    id = models.AutoField(primary_key=True, verbose_name="任务编号")
    task_type = models.CharField(max_length=50, default='vehicle_dispatch', verbose_name="任务类型")
    start_location = models.CharField(max_length=100, verbose_name="起始位置")
    end_location = models.CharField(max_length=100, verbose_name="目标位置")
    dispatch_count = models.IntegerField(default=0, verbose_name="调度数量")
    
    PRIORITY_CHOICES = [
        ('high', '高'),
        ('medium', '中'),
        ('low', '低'),
    ]
    priority = models.CharField(max_length=20, choices=PRIORITY_CHOICES, default='medium', verbose_name="优先级")
    
    STATUS_CHOICES = [
        ('pending', '待处理'),
        ('in_progress', '进行中'),
        ('completed', '已完成'),
        ('cancelled', '已取消'),
    ]
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending', verbose_name="任务状态")
    
    create_time = models.DateTimeField(auto_now_add=True, verbose_name="创建时间")
    predicted_time = models.DateTimeField(null=True, blank=True, verbose_name="预测时间")

    class Meta:
        verbose_name = "调度任务"
        verbose_name_plural = "调度任务"
        ordering = ['-create_time']
    
    def __str__(self):
        return f"任务{self.id} - {self.start_location} → {self.end_location} - {self.get_status_display()}"


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