from django.core.management.base import BaseCommand
import csv
import json
import random
import os
from datetime import datetime, timedelta
from django.conf import settings

class Command(BaseCommand):
    help = '在燕山大学校园边界内生成结构化测试数据'

    def handle(self, *args, **options):
        self.stdout.write('开始生成标准化测试数据...')
        
        # 燕大校园边界
        yanshan_bounds = {
            'north': 39.9550,
            'south': 39.9450,
            'east': 119.5400,
            'west': 119.5250
        }
        
        # 创建测试数据目录
        test_data_dir = os.path.join(settings.BASE_DIR, '..', 'test_data')
        os.makedirs(test_data_dir, exist_ok=True)
        
        # 1. 生成停车点数据
        self.stdout.write('生成停车点数据...')
        parking_spots = self.generate_parking_spots(yanshan_bounds)
        self.save_parking_spots(parking_spots, test_data_dir)
        
        # 2. 生成车辆数据
        self.stdout.write('生成车辆数据...')
        vehicles = self.generate_vehicles(1400, yanshan_bounds, parking_spots)
        self.save_vehicles(vehicles, test_data_dir)
        
        # 3. 生成预测结果数据
        self.stdout.write('生成预测结果数据...')
        predictions = self.generate_predictions(parking_spots)
        self.save_predictions(predictions, test_data_dir)
        
        # 4. 生成数据流说明文档
        self.stdout.write('生成数据流说明文档...')
        self.generate_dataflow_doc(test_data_dir)
        
        self.stdout.write('标准化测试数据生成完成！')
        self.stdout.write(f'数据文件已保存至: {test_data_dir}')
    
    def generate_parking_spots(self, bounds):
        """生成停车点数据"""
        parking_spots = []
        
        # 燕大校园内的主要区域
        areas = [
            {'name': '燕山大学南门', 'lat': 39.9450, 'lon': 119.5300},
            {'name': '燕山大学北门', 'lat': 39.9550, 'lon': 119.5300},
            {'name': '燕山大学东门', 'lat': 39.9500, 'lon': 119.5400},
            {'name': '燕山大学西门', 'lat': 39.9500, 'lon': 119.5250},
            {'name': '燕山大学图书馆', 'lat': 39.9490, 'lon': 119.5320},
            {'name': '燕山大学教学楼', 'lat': 39.9480, 'lon': 119.5330},
            {'name': '燕山大学食堂', 'lat': 39.9470, 'lon': 119.5310},
            {'name': '燕山大学宿舍区', 'lat': 39.9460, 'lon': 119.5320},
            {'name': '燕山大学体育馆', 'lat': 39.9510, 'lon': 119.5330},
            {'name': '燕山大学行政楼', 'lat': 39.9500, 'lon': 119.5310},
        ]
        
        for i, area in enumerate(areas, 1):
            # 在每个区域周围生成多个停车点
            for j in range(1, 4):
                spot_id = f'P{i:03d}{j:02d}'
                # 在区域周围随机偏移
                lat_offset = random.uniform(-0.001, 0.001)
                lon_offset = random.uniform(-0.001, 0.001)
                lat = max(bounds['south'], min(bounds['north'], area['lat'] + lat_offset))
                lon = max(bounds['west'], min(bounds['east'], area['lon'] + lon_offset))
                
                parking_spots.append({
                    'id': spot_id,
                    'name': f'{area["name"]}停车点{j}',
                    'latitude': round(lat, 6),
                    'longitude': round(lon, 6),
                    'service_radius': random.randint(50, 150)
                })
        
        return parking_spots
    
    def generate_vehicles(self, count, bounds, parking_spots):
        """生成车辆数据"""
        vehicles = []
        status_options = ['available', 'ridden', 'faulty', 'locked']
        
        for i in range(1, count + 1):
            # 随机选择一个停车点，在其附近生成车辆位置
            spot = random.choice(parking_spots)
            lat_offset = random.uniform(-0.0005, 0.0005)
            lon_offset = random.uniform(-0.0005, 0.0005)
            lat = max(bounds['south'], min(bounds['north'], spot['latitude'] + lat_offset))
            lon = max(bounds['west'], min(bounds['east'], spot['longitude'] + lon_offset))
            
            # 随机生成更新时间（过去24小时内）
            update_time = datetime.now() - timedelta(hours=random.randint(0, 24), minutes=random.randint(0, 59))
            
            vehicles.append({
                'id': f'B{i:04d}',
                'status': random.choice(status_options),
                'latitude': round(lat, 6),
                'longitude': round(lon, 6),
                'update_time': update_time.strftime('%Y-%m-%d %H:%M:%S'),
                'parking_spot_id': spot['id']
            })
        
        return vehicles
    
    def generate_predictions(self, parking_spots):
        """生成预测结果数据"""
        predictions = []
        current_time = datetime.now()
        
        # 生成未来24小时的预测数据
        for hour in range(24):
            predict_time = current_time + timedelta(hours=hour)
            
            for spot in parking_spots:
                # 基于时间和位置生成合理的需求预测
                base_demand = random.randint(5, 20)
                
                # 考虑时间因素：上课时间需求高
                hour_of_day = predict_time.hour
                if 8 <= hour_of_day <= 12 or 14 <= hour_of_day <= 18:
                    demand_multiplier = random.uniform(1.5, 2.5)
                else:
                    demand_multiplier = random.uniform(0.5, 1.0)
                
                demand = int(base_demand * demand_multiplier)
                supply = random.randint(demand - 5, demand + 5)
                supply = max(0, supply)  # 确保供给不为负数
                
                predictions.append({
                    'parking_spot_id': spot['id'],
                    'parking_spot_name': spot['name'],
                    'predict_time': predict_time.strftime('%Y-%m-%d %H:00:00'),
                    'demand': demand,
                    'supply': supply,
                    'difference': supply - demand
                })
        
        return predictions
    
    def save_parking_spots(self, parking_spots, output_dir):
        """保存停车点数据"""
        # 保存为CSV
        csv_path = os.path.join(output_dir, 'parking_spots.csv')
        with open(csv_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=['id', 'name', 'latitude', 'longitude', 'service_radius'])
            writer.writeheader()
            writer.writerows(parking_spots)
        
        # 保存为JSON
        json_path = os.path.join(output_dir, 'parking_spots.json')
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(parking_spots, f, ensure_ascii=False, indent=2)
        
        self.stdout.write(f'生成了 {len(parking_spots)} 个停车点数据')
    
    def save_vehicles(self, vehicles, output_dir):
        """保存车辆数据"""
        # 保存为CSV
        csv_path = os.path.join(output_dir, 'vehicles.csv')
        with open(csv_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=['id', 'status', 'latitude', 'longitude', 'update_time', 'parking_spot_id'])
            writer.writeheader()
            writer.writerows(vehicles)
        
        # 保存为JSON
        json_path = os.path.join(output_dir, 'vehicles.json')
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(vehicles, f, ensure_ascii=False, indent=2)
        
        self.stdout.write(f'生成了 {len(vehicles)} 条车辆数据')
    
    def save_predictions(self, predictions, output_dir):
        """保存预测结果数据"""
        # 保存为CSV
        csv_path = os.path.join(output_dir, 'predictions.csv')
        with open(csv_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=['parking_spot_id', 'parking_spot_name', 'predict_time', 'demand', 'supply', 'difference'])
            writer.writeheader()
            writer.writerows(predictions)
        
        # 保存为JSON
        json_path = os.path.join(output_dir, 'predictions.json')
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(predictions, f, ensure_ascii=False, indent=2)
        
        self.stdout.write(f'生成了 {len(predictions)} 条预测结果数据')
    
    def generate_dataflow_doc(self, output_dir):
        """生成数据流说明文档"""
        doc_path = os.path.join(output_dir, 'dataflow_documentation.md')
        
        doc_content = """
# 数据流说明文档

## 数据格式

### 1. 停车点数据 (parking_spots.csv/json)
- id: 停车点唯一标识符
- name: 停车点名称
- latitude: 纬度（WGS84坐标系）
- longitude: 经度（WGS84坐标系）
- service_radius: 服务半径（米）

### 2. 车辆数据 (vehicles.csv/json)
- id: 车辆唯一标识符
- status: 车辆状态（available/ridden/faulty/locked）
- latitude: 纬度（WGS84坐标系）
- longitude: 经度（WGS84坐标系）
- update_time: 更新时间（YYYY-MM-DD HH:MM:SS）
- parking_spot_id: 所属停车点ID

### 3. 预测结果数据 (predictions.csv/json)
- parking_spot_id: 停车点ID
- parking_spot_name: 停车点名称
- predict_time: 预测时间（YYYY-MM-DD HH:00:00）
- demand: 预测需求量
- supply: 预测供给量
- difference: 供给-需求差值

## 接入方式

1. **数据导入**：通过Django管理界面或API接口导入CSV/JSON文件
2. **实时数据流**：通过WebSocket或REST API接收实时车辆状态更新
3. **定时同步**：通过后台定时任务同步最新数据

## 更新逻辑

1. **车辆状态更新**：每30秒自动刷新车辆位置和状态
2. **预测数据更新**：每小时生成一次新的预测数据
3. **停车点统计**：实时更新每个停车点的车辆数量

## 数据约束

1. **地理范围**：所有坐标数据必须在燕山大学校园边界内
2. **时间精度**：预测数据精确到小时级别
3. **数据完整性**：所有必填字段不能为空
4. **数据一致性**：车辆状态和位置必须保持一致
"""
        
        with open(doc_path, 'w', encoding='utf-8') as f:
            f.write(doc_content)
        
        self.stdout.write('生成了数据流说明文档')