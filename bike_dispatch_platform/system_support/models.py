from django.db import models
from django.contrib.auth.models import AbstractUser, Group, Permission


class User(AbstractUser):
    """自定义用户模型（多角色：管理员、运维人员、普通用户）"""
    phone = models.CharField(max_length=11, blank=True, verbose_name="手机号")
    create_time = models.DateTimeField(auto_now_add=True, verbose_name="创建时间")

    class Meta:
        verbose_name = "用户"
        verbose_name_plural = "用户"


class OperationLog(models.Model):
    """系统操作日志（任务书要求）"""
    user = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name="操作人")
    operation = models.CharField(max_length=100, verbose_name="操作内容")
    ip_address = models.GenericIPAddressField(verbose_name="操作IP")
    operation_time = models.DateTimeField(auto_now_add=True, verbose_name="操作时间")

    class Meta:
        verbose_name = "操作日志"
        verbose_name_plural = "操作日志"


class DataBackup(models.Model):
    """数据加密备份（任务书要求）"""
    backup_file = models.FileField(upload_to='backups/%Y%m%d/', verbose_name="备份文件")
    backup_size = models.FloatField(verbose_name="备份大小（MB）")
    backup_time = models.DateTimeField(auto_now_add=True, verbose_name="备份时间")
    backup_user = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name="备份人")

    class Meta:
        verbose_name = "数据备份"
        verbose_name_plural = "数据备份"