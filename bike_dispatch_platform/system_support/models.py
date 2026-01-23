from django.db import models
from django.contrib.auth.models import AbstractUser
from django.core.validators import RegexValidator

class User(AbstractUser):
    """自定义用户模型（任务书"系统支撑模块"核心：多角色权限）"""
    # 扩展字段：角色（管理员/运维人员/预测人员）
    ROLE_CHOICES = [
        ('admin', '系统管理员'),
        ('operator', '运维人员'),
        ('predictor', '预测人员'),
    ]
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='predictor', verbose_name="用户角色")
    phone = models.CharField(
        max_length=11, 
        blank=True, 
        null=True, 
        validators=[RegexValidator(regex=r'^1[3-9]\d{9}$', message='请输入正确的手机号')],
        verbose_name="手机号"
    )
    # 密码加密存储（Django默认使用PBKDF2，满足任务书"数据加密存储"要求）
    # 敏感数据加密：使用Django的make_password和check_password

    class Meta:
        verbose_name = "系统用户"
        verbose_name_plural = "系统用户"
    
    def is_admin(self):
        """判断是否为管理员"""
        return self.role == 'admin'
    
    def is_operator(self):
        """判断是否为运维人员"""
        return self.role == 'operator'
    
    def is_predictor(self):
        """判断是否为预测人员"""
        return self.role == 'predictor'


class SystemLog(models.Model):
    """系统日志模型（任务书"系统日志记录"要求）"""
    ACTION_CHOICES = [
        ('login', '登录'),
        ('logout', '登出'),
        ('upload', '数据上传'),
        ('predict', '需求预测'),
        ('schedule', '调度任务'),
        ('backup', '数据备份'),
        ('export', '报表导出'),
        ('error', '错误操作'),
    ]
    
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, verbose_name="操作用户")
    action = models.CharField(max_length=20, choices=ACTION_CHOICES, verbose_name="操作类型")
    description = models.TextField(verbose_name="操作描述")
    ip_address = models.GenericIPAddressField(null=True, blank=True, verbose_name="IP地址")
    create_time = models.DateTimeField(auto_now_add=True, verbose_name="操作时间")
    
    class Meta:
        verbose_name = "系统日志"
        verbose_name_plural = "系统日志"
        ordering = ['-create_time']
    
    def __str__(self):
        return f"{self.get_action_display()} - {self.user.username if self.user else '匿名'} - {self.create_time}"


class DataBackup(models.Model):
    """数据备份记录模型（任务书"定期备份"要求）"""
    backup_file = models.CharField(max_length=255, verbose_name="备份文件路径")
    backup_size = models.FloatField(verbose_name="备份大小(MB)")
    backup_user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, verbose_name="备份用户")
    create_time = models.DateTimeField(auto_now_add=True, verbose_name="备份时间")
    is_encrypted = models.BooleanField(default=True, verbose_name="是否加密")
    
    class Meta:
        verbose_name = "数据备份"
        verbose_name_plural = "数据备份"
        ordering = ['-create_time']
    
    def __str__(self):
        return f"{self.backup_file} - {self.create_time}"


class RegionFeature(models.Model):
    """区域特征数据模型（任务书"区域特征数据采集"要求）"""
    region = models.CharField(max_length=50, unique=True, verbose_name="区域名称")
    population_density = models.FloatField(verbose_name="人口密度(人/km²)", null=True, blank=True)
    business_type = models.CharField(
        max_length=50,
        choices=[
            ('commercial', '商业区'),
            ('residential', '住宅区'),
            ('industrial', '工业区'),
            ('mixed', '混合区'),
        ],
        verbose_name="商圈类型",
        null=True,
        blank=True
    )
    subway_stations = models.IntegerField(default=0, verbose_name="地铁站数量")
    bus_stations = models.IntegerField(default=0, verbose_name="公交站数量")
    create_time = models.DateTimeField(auto_now_add=True, verbose_name="创建时间")
    update_time = models.DateTimeField(auto_now=True, verbose_name="更新时间")
    
    class Meta:
        verbose_name = "区域特征"
        verbose_name_plural = "区域特征"
    
    def __str__(self):
        return f"{self.region} - {self.get_business_type_display() if self.business_type else '未分类'}"