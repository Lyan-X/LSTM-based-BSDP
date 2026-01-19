import os
from pathlib import Path
from datetime import timedelta

# 项目根目录（自动识别，避免硬编码）
BASE_DIR = Path(__file__).resolve().parent.parent

# 安全配置（开发阶段默认，生产环境需替换密钥）
SECRET_KEY = 'django-insecure-xxx-替换为随机字符串'
DEBUG = True
ALLOWED_HOSTS = ['*']  # 开发阶段允许所有访问

# 注册4大核心应用（任务书模块全覆盖）
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    # 必须包含以下4个任务书要求的模块，重点检查system_support
    'system_support',  # 系统支撑模块（核心，无拼写错误）
    'data_process',  # 数据处理模块
    'demand_prediction',  # 需求预测模块
    'operation_management',  # 运维管理模块
]

# 中间件（新增操作日志中间件，满足任务书"系统日志记录"要求）
MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'system_support.middleware.OperationLogMiddleware',  # 自定义日志中间件
]

# 根路由配置
ROOT_URLCONF = 'bike_dispatch_platform.urls'

# 模板配置（支持模块分目录模板，符合软件工程规范）
TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [os.path.join(BASE_DIR, 'templates')],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'bike_dispatch_platform.wsgi.application'

# 数据仓库配置（任务书"结构化数据仓库"要求，开发用SQLite，生产可迁MySQL）
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'bike_dispatch_db.db',  # 共享单车调度专用数据库
    }
}

# 密码验证与多角色权限配置
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
]

# 自定义用户模型（支持任务书"多角色权限管理"）
AUTH_USER_MODEL = 'system_support.User'

# 国际化配置（符合国内使用场景）
LANGUAGE_CODE = 'zh-hans'
TIME_ZONE = 'Asia/Shanghai'
USE_I18N = True
USE_TZ = True

# 静态资源配置（关联模型可视化结果，无需重复拷贝）
STATIC_URL = 'static/'
STATIC_ROOT = os.path.join(BASE_DIR, 'static_collect')
STATICFILES_DIRS = [
    os.path.join(BASE_DIR, 'static'),
    os.path.join(BASE_DIR, '../results'),  # 关联模型训练可视化图表
]

# 媒体文件配置（任务书"公开数据集导入+本地数据录入"存储需求）
MEDIA_URL = 'media/'
MEDIA_ROOT = os.path.join(BASE_DIR, 'media')  # 存储上传的Excel/CSV数据集

# 会话配置（支持多用户并发访问，任务书技术要求）
SESSION_COOKIE_AGE = timedelta(hours=8)
SESSION_SAVE_EVERY_REQUEST = True

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'