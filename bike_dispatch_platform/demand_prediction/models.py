from django.db import models
from system_support.models import User

# ========== 全局常量（核心修改：移到类外，可被其他模块导入） ==========
REGION_CHOICES = [
    ('region1', '区域1'),
    ('region2', '区域2'),
    ('region3', '区域3'),
    ('region4', '区域4')
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
    demand_count = models.IntegerField(verbose_name="调度需求车辆数")
    
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
        
    def __str__(self):
        """自定义对象展示名称，便于后台管理查看"""
        return f"{self.predict_date} {self.get_region_display()} {self.get_time_period_display()} 需求数：{self.demand_count}"