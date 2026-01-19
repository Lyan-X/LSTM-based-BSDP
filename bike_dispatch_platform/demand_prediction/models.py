from django.db import models
from system_support.models import User


class PredictionResult(models.Model):
    """预测结果模型（任务书"输出日/时段/区域调度需求"）"""
    REGION_CHOICES = [('region1', '区域1'), ('region2', '区域2'), ('region3', '区域3'), ('region4', '区域4')]
    region = models.CharField(max_length=20, choices=REGION_CHOICES, verbose_name="预测区域")

    TIME_PERIOD_CHOICES = [('morning', '早高峰（7-9点）'), ('noon', '午间（11-13点）'), ('evening', '晚高峰（17-19点）'),
                           ('night', '夜间（21-23点）')]
    time_period = models.CharField(max_length=20, choices=TIME_PERIOD_CHOICES, verbose_name="预测时段")

    predict_date = models.DateField(verbose_name="预测日期")
    demand_count = models.IntegerField(verbose_name="调度需求车辆数")
    model_used = models.CharField(max_length=20, choices=[('LSTM', 'LSTM模型'), ('BP', 'BP神经网络')],
                                  verbose_name="使用模型")
    accuracy = models.FloatField(verbose_name="预测准确率（%）")
    create_time = models.DateTimeField(auto_now_add=True, verbose_name="生成时间")
    user = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name="操作用户")

    class Meta:
        verbose_name = "预测结果"
        verbose_name_plural = "预测结果"