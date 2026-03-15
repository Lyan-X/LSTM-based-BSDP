from django.contrib.auth.models import AbstractUser
from django.core.validators import RegexValidator
from django.db import models


class User(AbstractUser):
    """Custom user with role-based access control."""

    ROLE_CHOICES = [
        ("admin", "系统管理员"),
        ("operator", "运维调度员"),
        ("predictor", "数据分析员"),
    ]

    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default="predictor", verbose_name="用户角色")
    phone = models.CharField(
        max_length=11,
        blank=True,
        null=True,
        validators=[RegexValidator(regex=r"^1[3-9]\d{9}$", message="请输入正确的手机号")],
        verbose_name="手机号",
    )

    class Meta:
        verbose_name = "系统用户"
        verbose_name_plural = "系统用户"

    def is_admin(self):
        return self.role == "admin"

    def is_operator(self):
        return self.role == "operator"

    def is_predictor(self):
        return self.role == "predictor"

    def has_role(self, *roles: str) -> bool:
        return self.is_superuser or self.role in roles


class SystemLog(models.Model):
    """System audit log."""

    ACTION_CHOICES = [
        ("login", "登录"),
        ("logout", "登出"),
        ("upload", "数据上传"),
        ("predict", "需求预测"),
        ("schedule", "调度任务"),
        ("backup", "数据备份"),
        ("export", "报表导出"),
        ("error", "错误操作"),
        ("setting", "系统设置"),
    ]

    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, verbose_name="操作用户")
    action = models.CharField(max_length=20, choices=ACTION_CHOICES, verbose_name="操作类型")
    description = models.TextField(verbose_name="操作描述")
    ip_address = models.GenericIPAddressField(null=True, blank=True, verbose_name="IP地址")
    create_time = models.DateTimeField(auto_now_add=True, verbose_name="操作时间")

    class Meta:
        verbose_name = "系统日志"
        verbose_name_plural = "系统日志"
        ordering = ["-create_time"]

    def __str__(self):
        username = self.user.username if self.user else "匿名"
        return f"{self.get_action_display()}-{username}"


class DataBackup(models.Model):
    """Backup metadata."""

    backup_file = models.CharField(max_length=255, verbose_name="备份文件路径")
    backup_size = models.FloatField(verbose_name="备份大小(MB)")
    backup_user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, verbose_name="备份用户")
    create_time = models.DateTimeField(auto_now_add=True, verbose_name="备份时间")
    is_encrypted = models.BooleanField(default=True, verbose_name="是否加密")

    class Meta:
        verbose_name = "数据备份"
        verbose_name_plural = "数据备份"
        ordering = ["-create_time"]

    def __str__(self):
        return f"{self.backup_file}-{self.create_time:%Y-%m-%d %H:%M}"


class RegionFeature(models.Model):
    """Legacy region feature metadata."""

    BUSINESS_TYPE_CHOICES = [
        ("commercial", "商业区"),
        ("residential", "住宅区"),
        ("industrial", "工业区"),
        ("mixed", "混合区"),
    ]

    region = models.CharField(max_length=50, unique=True, verbose_name="区域名称")
    population_density = models.FloatField(verbose_name="人口密度", null=True, blank=True)
    business_type = models.CharField(
        max_length=50,
        choices=BUSINESS_TYPE_CHOICES,
        verbose_name="商圈类型",
        null=True,
        blank=True,
    )
    subway_stations = models.IntegerField(default=0, verbose_name="地铁站数量")
    bus_stations = models.IntegerField(default=0, verbose_name="公交站数量")
    create_time = models.DateTimeField(auto_now_add=True, verbose_name="创建时间")
    update_time = models.DateTimeField(auto_now=True, verbose_name="更新时间")

    class Meta:
        verbose_name = "区域特征"
        verbose_name_plural = "区域特征"

    def __str__(self):
        return self.region


class SystemSetting(models.Model):
    """Singleton runtime settings for 基于深度学习的城市共享单车调度需求预测与运维管理平台."""

    dashboard_refresh_seconds = models.PositiveIntegerField(default=10, verbose_name="仪表盘刷新秒数")
    demand_warning_threshold = models.PositiveIntegerField(default=15, verbose_name="供需预警阈值")
    prediction_horizon_hours = models.PositiveIntegerField(default=48, verbose_name="预测时长")
    dispatch_trigger_threshold = models.PositiveIntegerField(default=15, verbose_name="调度触发阈值")
    model_version = models.CharField(max_length=64, default="untrained", verbose_name="当前模型版本")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="更新时间")

    class Meta:
        verbose_name = "系统设置"
        verbose_name_plural = "系统设置"

    def __str__(self):
        return f"settings#{self.pk or 'singleton'}"
