from django.db import models
from system_support.models import User

# ========== 全局常量（核心修改：移到类外，可被其他模块导入） ==========
REGION_CHOICES = [
    ('west_campus', '西校区（教学区）'),
    ('east_campus', '东校区（教学区）'),
    ('dorm_area', '学生宿舍区'),
    ('library_area', '图书馆周边'),
    ('canteen_area', '食堂周边'),
    ('gate_area', '校门出入口'),
]

class PredictionResult(models.Model):
    """预测结果模型（任务书"输出日/时段/区域调度需求"）"""
    # 引用全局的REGION_CHOICES（不再类内定义）
    region = models.CharField(max_length=20, choices=REGION_CHOICES, verbose_name="预测区域")

    # 时段选择项（类内定义，无需外部导入）
    TIME_PERIOD_CHOICES = [
        ('morning', '早高峰（7-9点）'),
        ('noon', '午间（11-13点）'),
        ('evening', '晚高峰（17-19点）'),
        ('night', '夜间（21-23点）')
    ]
    time_period = models.CharField(max_length=20, choices=TIME_PERIOD_CHOICES, verbose_name="预测时段")

    predict_date = models.DateField(verbose_name="预测日期")
    predict_hour = models.IntegerField(verbose_name="预测小时", choices=[(i, f'{i}:00') for i in range(24)], default=0)
    demand_count = models.IntegerField(verbose_name="调度需求车辆数")
    supply_count = models.IntegerField(default=0, verbose_name="当前供给车辆数")
    
    # 使用模型选择项
    MODEL_CHOICES = [
        ('LSTM', 'LSTM模型'),
        ('BP', 'BP神经网络')
    ]
    model_used = models.CharField(max_length=20, choices=MODEL_CHOICES, verbose_name="使用模型")
    
    accuracy = models.FloatField(verbose_name="预测准确率（%）")
    create_time = models.DateTimeField(auto_now_add=True, verbose_name="生成时间")
    user = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name="操作用户")

    class Meta:
        verbose_name = "预测结果"
        verbose_name_plural = "预测结果"
        unique_together = ['region', 'predict_date', 'predict_hour']  # 确保每个小时只能有一份预测数据
        
    def __str__(self):
        """自定义对象展示名称，便于后台管理查看"""
        return f"{self.predict_date} {self.predict_hour}:00 {self.get_region_display()} 需求数：{self.demand_count}"


class ModelTrainLog(models.Model):
    """模型训练日志模型"""
    # 训练日期
    train_date = models.DateField(verbose_name="训练日期")
    # 训练时间
    start_time = models.DateTimeField(verbose_name="开始时间")
    end_time = models.DateTimeField(verbose_name="结束时间")
    # 训练时长（秒）
    duration = models.IntegerField(verbose_name="训练时长（秒）")
    # 模型性能指标
    mae = models.FloatField(verbose_name="平均绝对误差")
    rmse = models.FloatField(verbose_name="均方根误差")
    r2 = models.FloatField(verbose_name="R²准确率")
    # 模型文件名
    model_filename = models.CharField(max_length=255, verbose_name="模型文件名")
    # 训练状态
    status = models.CharField(
        max_length=20,
        choices=[("success", "成功"), ("failed", "失败")],
        default="success",
        verbose_name="训练状态"
    )
    # 错误信息
    error_message = models.TextField(null=True, blank=True, verbose_name="错误信息")
    # 自动记录创建时间
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="创建时间")

    class Meta:
        verbose_name = "模型训练日志"
        verbose_name_plural = "模型训练日志"

    def __str__(self):
        return f"{self.train_date} - {self.model_filename} - {self.status}"