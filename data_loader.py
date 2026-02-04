import pandas as pd
from shapely.geometry import Point, Polygon

# 燕山大学边界坐标（从generate_ysu_bike_data.py中获取）
YSU_BOUNDARY = [
    (119.516, 39.914),
    (119.520, 39.914),
    (119.520, 39.912),
    (119.516, 39.912)
]

# 还车点字典
PARKING_SPOTS = {
    "第四体育场": (119.517816, 39.913239),
    "图书馆": (119.5185, 39.9135),
    "教学楼A区": (119.519, 39.913),
    "食堂": (119.517, 39.913),
    "宿舍区": (119.5165, 39.9132)
}

def validate_coordinate(longitude, latitude):
    """
    校验坐标是否在燕山大学边界内
    """
    point = Point(longitude, latitude)
    # 转换边界格式为Polygon所需的格式
    boundary = [(p[0], p[1]) for p in YSU_BOUNDARY]
    polygon = Polygon(boundary)
    return polygon.contains(point)

def load_ysu_bike_data(file_path):
    """
    读取ysu_bike_data.csv文件
    集成坐标边界校验逻辑
    适配新数据字段
    """
    # 加载数据
    df = pd.read_csv(file_path)
    
    # 验证坐标边界
    df['is_in_boundary'] = df.apply(
        lambda row: validate_coordinate(row['longitude'], row['latitude']),
        axis=1
    )
    
    # 确保字段类型正确
    df['id'] = df['id'].astype(int)
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    df['longitude'] = df['longitude'].astype(float)
    df['latitude'] = df['latitude'].astype(float)
    df['bike_count'] = df['bike_count'].astype(int)
    df['is_in_boundary'] = df['is_in_boundary'].astype(int)
    df['weekday'] = df['weekday'].astype(int)
    df['hour'] = df['hour'].astype(int)
    df['is_peak'] = df['is_peak'].astype(int)
    
    # 按时间排序
    df = df.sort_values(by=['timestamp']).reset_index(drop=True)
    
    print(f"成功加载数据：{len(df)} 条记录")
    print(f"边界内数据：{df['is_in_boundary'].sum()} 条")
    print(f"边界外数据：{len(df) - df['is_in_boundary'].sum()} 条")
    
    return df

def load_original_data(file_path):
    """
    加载原始训练数据（兼容原有功能）
    """
    df = pd.read_csv(file_path)
    return df

if __name__ == "__main__":
    # 测试加载燕山大学数据
    ysu_data = load_ysu_bike_data('ysu_bike_data.csv')
    print(ysu_data.head())
    print(ysu_data.info())
