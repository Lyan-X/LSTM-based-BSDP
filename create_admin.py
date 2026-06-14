"""Create default admin user."""
import os, sys, django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'django_project.settings')
sys.path.insert(0, 'e:/develop/BSDP-Bike Sharing Demand Prediction Based on LSTM Model/BSDP')
django.setup()

from bike_dispatch_platform.system_support.models import User

username = 'admin'
password = 'admin123'

if not User.objects.filter(username=username).exists():
    User.objects.create_superuser(username=username, email='admin@example.com', password=password, role='admin')
    print(f'用户 {username} 已创建，密码: {password}')
else:
    print(f'用户 {username} 已存在')
