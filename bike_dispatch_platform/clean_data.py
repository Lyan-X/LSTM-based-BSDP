#!/usr/bin/env python3
"""
数据清理脚本
删除冗余数据，只保留停车点和测试位置数据
"""

import os
import django

# 设置Django环境
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'bike_dispatch_platform.settings')
django.setup()

from data_process.models import BikeRideData, DataProcessLog
from demand_prediction.models import ModelTrainLog, PredictionResult
from operation_management.models import Vehicle, ScheduleTask, ParkingSpot
from system_support.models import RegionFeature, SystemLog, DataBackup


def clean_data():
    """清理冗余数据"""
    print("开始清理冗余数据...")
    
    # 清理骑行数据
    print("清理骑行数据...")
    BikeRideData.objects.all().delete()
    print("骑行数据清理完成")
    
    # 清理数据处理日志
    print("清理数据处理日志...")
    DataProcessLog.objects.all().delete()
    print("数据处理日志清理完成")
    
    # 清理模型训练日志
    print("清理模型训练日志...")
    ModelTrainLog.objects.all().delete()
    print("模型训练日志清理完成")
    
    # 清理预测结果
    print("清理预测结果...")
    PredictionResult.objects.all().delete()
    print("预测结果清理完成")
    
    # 清理车辆信息
    print("清理车辆信息...")
    Vehicle.objects.all().delete()
    print("车辆信息清理完成")
    
    # 清理调度任务
    print("清理调度任务...")
    ScheduleTask.objects.all().delete()
    print("调度任务清理完成")
    
    # 清理区域特征
    print("清理区域特征...")
    RegionFeature.objects.all().delete()
    print("区域特征清理完成")
    
    # 清理系统日志
    print("清理系统日志...")
    SystemLog.objects.all().delete()
    print("系统日志清理完成")
    
    # 清理数据备份
    print("清理数据备份...")
    DataBackup.objects.all().delete()
    print("数据备份清理完成")
    
    # 验证停车点数据是否保留
    parking_count = ParkingSpot.objects.count()
    print(f"\n停车点数据保留数量：{parking_count}")
    
    print("\n数据清理完成！")
    print("仅保留了停车点和测试位置数据")


if __name__ == "__main__":
    clean_data()
