#!/usr/bin/env python3
"""
创建管理员用户的脚本
"""
import os
import sys

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), 'bike_dispatch_platform'))

# 设置Django环境变量
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'bike_dispatch_platform.settings')

# 导入Django
import django
django.setup()

# 导入用户模型
from system_support.models import User

def create_admin_user():
    """创建管理员用户"""
    try:
        # 检查是否已存在admin用户
        if User.objects.filter(username='admin').exists():
            print('管理员用户已存在！')
            return
        
        # 创建管理员用户
        user = User.objects.create_superuser(
            username='admin',
            password='admin',
            email='admin@example.com',
            role='admin'
        )
        print('管理员用户创建成功！')
        print(f'用户名: {user.username}')
        print(f'角色: {user.get_role_display()}')
    except Exception as e:
        print(f'创建管理员用户失败: {str(e)}')

if __name__ == '__main__':
    create_admin_user()
