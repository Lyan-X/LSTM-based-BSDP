"""Reset admin password."""
import os, sys, django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'django_project.settings')
sys.path.insert(0, 'e:/develop/BSDP-Bike Sharing Demand Prediction Based on LSTM Model/BSDP')
django.setup()

from bike_dispatch_platform.system_support.models import User

username = 'admin'
password = 'admin123'

try:
    user = User.objects.get(username=username)
    user.set_password(password)
    user.save()
    print(f'用户 {username} 密码已重置为: {password}')
except User.DoesNotExist:
    print(f'用户 {username} 不存在')
