import pandas as pd
import numpy as np

def data_cleaning(df):
    """
    数据清洗函数（任务书"清洗、格式标准化"要求）
    功能：去重、缺失值填充、字段格式标准化
    """
    # 1. 去重（根据核心字段去重）
    df = df.drop_duplicates(subset=['start_point', 'end_point', 'ride_datetime'], keep='first')
    
    # 2. 缺失值填充
    # 数值型字段用均值填充
    numeric_cols = ['duration', 'distance', 'temperature', 'wind_speed']
    for col in numeric_cols:
        if col in df.columns:
            df[col] = df[col].fillna(df[col].mean())
    
    # 字符型字段用默认值填充
    df['start_point'] = df['start_point'].fillna('未知起点').astype(str)
    df['end_point'] = df['end_point'].fillna('未知终点').astype(str)
    df['weather'] = df['weather'].fillna('sunny').astype(str)
    
    # 3. 格式标准化（确保时间字段是datetime类型）
    if 'ride_datetime' in df.columns:
        df['ride_datetime'] = pd.to_datetime(df['ride_datetime'], errors='coerce')
        # 过滤掉时间为空的数据
        df = df.dropna(subset=['ride_datetime'])
    
    # 4. 过滤异常值（时长/距离不能为负数）
    df = df[df['duration'] >= 0]
    df = df[df['distance'] >= 0]
    
    return df