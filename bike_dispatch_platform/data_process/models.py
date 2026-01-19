from django.db import models
from system_support.models import User


class BikeRideData(models.Model):
    """共享单车骑行数据模型（任务书"结构化数据仓库"核心）"""
    # 数据来源（任务书"公开数据集导入+本地数据录入"）
    DATA_SOURCE_CHOICES = [('public', '公开数据集'), ('local', '本地录入')]
    data_source = models.CharField(max_length=20, choices=DATA_SOURCE_CHOICES, verbose_name="数据来源")

    # 核心骑行数据（任务书要求：起止点、时间、里程）
    start_point = models.CharField(max_length=100, verbose_name="起始区域")
    end_point = models.CharField(max_length=100, verbose_name="结束区域")
    ride_datetime = models.DateTimeField(verbose_name="骑行时间")
    duration = models.FloatField(verbose_name="骑行时长（分钟）")
    distance = models.FloatField(verbose_name="骑行里程（公里）")

    # 环境关联数据（任务书要求：天气因素）
    weather = models.CharField(max_length=20, choices=[('sunny', '晴天'), ('rainy', '雨天'), ('cloudy', '阴天')],
                               verbose_name="天气")
    temperature = models.FloatField(verbose_name="温度（℃）")
    wind_speed = models.FloatField(verbose_name="风速（m/s）")

    # 数据状态（任务书"清洗、格式标准化"）
    STATUS_CHOICES = [('uncleaned', '未清洗'), ('cleaned', '已清洗')]
    status = models.CharField(max_length=20, default='uncleaned', choices=STATUS_CHOICES, verbose_name="数据状态")

    # 关联信息
    upload_user = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name="上传用户")
    create_time = models.DateTimeField(auto_now_add=True, verbose_name="创建时间")

    class Meta:
        verbose_name = "骑行数据"
        verbose_name_plural = "骑行数据"
        ordering = ['-ride_datetime']