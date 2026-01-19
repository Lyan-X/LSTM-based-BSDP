from django.db import models
from django.contrib.auth.models import AbstractUser

class User(AbstractUser):
    """自定义用户模型（任务书"系统支撑模块"核心：多角色权限）"""
    # 扩展字段：角色（管理员/运维人员/预测人员）
    ROLE_CHOICES = [
        ('admin', '系统管理员'),
        ('operator', '运维人员'),
        ('predictor', '预测人员'),
    ]
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='predictor', verbose_name="用户角色")
    phone = models.CharField(max_length=11, blank=True, null=True, verbose_name="手机号")

    class Meta:
        verbose_name = "系统用户"
        verbose_name_plural = "系统用户"