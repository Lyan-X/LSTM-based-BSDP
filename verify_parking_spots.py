#!/usr/bin/env python3
"""
验证停车点数据是否正确导入
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

# 导入ParkingSpot模型
from operation_management.models import ParkingSpot

def verify_parking_spots():
    """验证停车点数据"""
    # 获取所有停车点
    parking_spots = ParkingSpot.objects.all()
    
    print(f"总停车点数量: {parking_spots.count()}")
    print("\n前5个停车点:")
    for spot in parking_spots[:5]:
        print(f"ID: {spot.parking_spot_id}, 名称: {spot.spot_name}, 经度: {spot.longitude}, 纬度: {spot.latitude}, 校区: {spot.campus_area}, 类型: {spot.spot_type}")
    
    print("\n后5个停车点:")
    total = parking_spots.count()
    for spot in parking_spots[total-5:total]:
        print(f"ID: {spot.parking_spot_id}, 名称: {spot.spot_name}, 经度: {spot.longitude}, 纬度: {spot.latitude}, 校区: {spot.campus_area}, 类型: {spot.spot_type}")
    
    # 验证停车点类型分布
    print("\n停车点类型分布:")
    from collections import Counter
    spot_types = Counter([spot.spot_type for spot in parking_spots])
    for spot_type, count in spot_types.items():
        print(f"{spot_type}: {count}")
    
    # 验证校区分布
    print("\n校区分布:")
    campus_areas = Counter([spot.campus_area for spot in parking_spots])
    for campus, count in campus_areas.items():
        print(f"{campus}: {count}")

if __name__ == '__main__':
    print("开始验证停车点数据...")
    verify_parking_spots()
