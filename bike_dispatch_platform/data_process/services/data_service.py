"""
数据处理服务
负责数据的导入、清洗、转换和管理
"""

import os
import pandas as pd
import numpy as np
import requests
import json
import schedule
import time
from threading import Thread
from django.conf import settings
from django.utils import timezone
from data_process.models import BikeRideData, WeatherData
from system_support.models import SystemLog
from django.db.models import Avg
import logging

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class DataService:
    """数据处理服务"""
    
    def __init__(self):
        self.base_dir = settings.BASE_DIR
        # 项目根目录（向上一级）
        project_root = os.path.abspath(os.path.join(self.base_dir, '..'))
        self.data_dir = os.path.join(project_root, 'data')
        self.test_data_dir = os.path.join(project_root, 'test_data')
        
        # 创建必要的目录
        self._ensure_directories()
    
    def _ensure_directories(self):
        """确保必要的目录存在"""
        for directory in [self.data_dir, self.test_data_dir]:
            if not os.path.exists(directory):
                os.makedirs(directory)
                logger.info(f"创建目录: {directory}")
    
    def validate_file(self, file):
        """验证上传文件"""
        if not file:
            return False, "请选择文件"
        
        if file.size == 0:
            return False, "文件为空"
        
        allowed_extensions = ('.xlsx', '.csv')
        if not file.name.lower().endswith(allowed_extensions):
            return False, f"仅支持文件格式: {', '.join(allowed_extensions)}"
        
        return True, "文件验证通过"
    
    def read_file(self, file):
        """读取文件内容"""
        try:
            if file.name.lower().endswith('.csv'):
                # 尝试不同编码
                try:
                    df = pd.read_csv(file, encoding='utf-8')
                except UnicodeDecodeError:
                    df = pd.read_csv(file, encoding='gbk')
            else:
                df = pd.read_excel(file)
            
            logger.info(f"成功读取文件: {file.name}，行数: {len(df)}")
            return df, None
            
        except Exception as e:
            error_msg = f"文件读取失败: {str(e)}"
            logger.error(error_msg)
            return None, error_msg
    
    def clean_data(self, df):
        """数据清洗"""
        try:
            # 创建副本避免修改原始数据
            cleaned_df = df.copy()
            
            # 处理列名
            cleaned_df.columns = [col.strip() for col in cleaned_df.columns]
            
            # 处理缺失值
            # 数值型列填充0
            numeric_cols = cleaned_df.select_dtypes(include=[np.number]).columns
            cleaned_df[numeric_cols] = cleaned_df[numeric_cols].fillna(0)
            
            # 字符串列填充空字符串
            object_cols = cleaned_df.select_dtypes(include=['object']).columns
            cleaned_df[object_cols] = cleaned_df[object_cols].fillna('')
            
            # 灵活处理时间列
            time_columns = ['ride_datetime', 'start_time', 'datetime', 'time', 'start_date', 'date']
            time_col_found = False
            
            for col in time_columns:
                if col in cleaned_df.columns:
                    cleaned_df['ride_datetime'] = pd.to_datetime(cleaned_df[col], errors='coerce')
                    time_col_found = True
                    break
            
            # 只有在找到时间列时才过滤无效行
            if time_col_found:
                cleaned_df = cleaned_df.dropna(subset=['ride_datetime'])
            else:
                # 没有时间列时，使用当前时间作为默认值
                cleaned_df['ride_datetime'] = timezone.now()
            
            # 移除重复行
            cleaned_df = cleaned_df.drop_duplicates()
            
            logger.info(f"数据清洗完成，行数: {len(cleaned_df)}")
            return cleaned_df, None
            
        except Exception as e:
            error_msg = f"数据清洗失败: {str(e)}"
            logger.error(error_msg)
            return None, error_msg
    
    def process_ride_data(self, df, user):
        """处理骑行数据"""
        try:
            # 数据清洗
            cleaned_df, error = self.clean_data(df)
            if error:
                return 0, error
            
            # 批量创建数据
            data_list = []
            for _, row in cleaned_df.iterrows():
                # 构建数据项
                data_item = BikeRideData(
                    data_source=row.get('data_source', 'upload'),
                    start_point=str(row.get('start_point', row.get('start_station', ''))).strip(),
                    end_point=str(row.get('end_point', row.get('end_station', ''))).strip(),
                    ride_datetime=row.get('ride_datetime'),
                    duration=float(row.get('duration', 0)) if pd.notna(row.get('duration')) else 0,
                    distance=float(row.get('distance', 0)) if pd.notna(row.get('distance')) else 0,
                    temperature=float(row.get('temperature', 25)) if pd.notna(row.get('temperature')) else 25,
                    wind_speed=float(row.get('wind_speed', 0)) if pd.notna(row.get('wind_speed', 0)) else 0,
                    status='cleaned',
                    upload_user=user
                )
                data_list.append(data_item)
            
            # 批量入库
            if data_list:
                BikeRideData.objects.bulk_create(data_list, batch_size=1000)
                logger.info(f"成功入库骑行数据: {len(data_list)}条")
            
            # 数据导入后后台自动触发需求预测处理
            self.trigger_demand_prediction()
            
            return len(data_list), None
            
        except Exception as e:
            error_msg = f"处理骑行数据失败: {str(e)}"
            logger.error(error_msg)
            return 0, error_msg
    
    def trigger_demand_prediction(self):
        """触发需求预测处理"""
        try:
            logger.info("开始自动触发需求预测处理")
            
            # 导入需求预测相关模块
            from demand_prediction.models import PredictionResult
            from system_support.services.model_service import model_service
            from django.utils import timezone
            import numpy as np
            
            # 预测下一小时
            next_hour = timezone.now().hour + 1
            if next_hour >= 24:
                next_hour = 0
            
            # 定义主要区域列表
            regions = [
                {'name': '燕山大学西校区', 'code': 'region1'},
                {'name': '燕山大学东校区', 'code': 'region2'},
                {'name': '燕山大学科技园区', 'code': 'region3'},
                {'name': '燕山大学商业区', 'code': 'region4'}
            ]
            
            # 对每个区域进行预测
            for region in regions:
                try:
                    # 获取该区域的历史骑行数据
                    historical_data = BikeRideData.objects.filter(
                        start_point__icontains=region['name'],
                        ride_datetime__hour=next_hour
                    ).order_by('-ride_datetime')[:24]
                    
                    # 计算历史统计特征
                    if historical_data.exists():
                        avg_duration = historical_data.aggregate(Avg('duration'))['duration__avg'] or 15.0
                        avg_distance = historical_data.aggregate(Avg('distance'))['distance__avg'] or 3.5
                        recent_count = historical_data.count()
                    else:
                        avg_duration = 15.0
                        avg_distance = 3.5
                        recent_count = 0
                    
                    # 获取天气数据
                    weather_data = WeatherData.objects.filter(
                        date=timezone.now().date()
                    ).first()
                    
                    # 天气特征
                    if weather_data:
                        temperature = weather_data.temperature
                        humidity = weather_data.humidity
                        wind_speed = weather_data.wind_speed
                        rainfall = weather_data.rainfall
                        weather_type = weather_data.weather_type
                    else:
                        temperature = 25
                        humidity = 60
                        wind_speed = 2
                        rainfall = 0
                        weather_type = 'sunny'
                    
                    # 构建特征向量
                    feature_vector = np.array([[
                        avg_duration,
                        avg_distance,
                        temperature,
                        humidity,
                        wind_speed,
                        rainfall,
                        0,  # 时段编码
                        0,  # 区域编码
                        0,  # 天气编码
                        1000.0,  # 人口密度
                        0.7  # 商圈类型
                    ]])
                    
                    # 使用模型预测
                    lstm_demand, _ = model_service.predict('lstm', feature_vector)
                    bp_demand, _ = model_service.predict('bp', feature_vector)
                    
                    # 选择最佳预测结果
                    final_demand = lstm_demand if lstm_demand is not None else bp_demand
                    if final_demand is None:
                        continue
                    
                    # 检查是否已存在同一小时的预测数据
                    existing_prediction = PredictionResult.objects.filter(
                        region=region['code'],
                        predict_date=timezone.now().date(),
                        predict_hour=next_hour
                    ).first()
                    
                    if existing_prediction:
                        # 更新现有预测数据
                        existing_prediction.demand_count = final_demand
                        existing_prediction.save()
                    else:
                        # 创建新预测数据
                        PredictionResult.objects.create(
                            region=region['code'],
                            time_period='morning',
                            predict_date=timezone.now().date(),
                            predict_hour=next_hour,
                            demand_count=final_demand,
                            supply_count=0,
                            model_used='LSTM',
                            accuracy=82.0
                        )
                    
                except Exception as e:
                    logger.error(f"预测{region['name']}需求失败: {str(e)}")
                    continue
            
            logger.info("需求预测处理完成")
            
        except Exception as e:
            error_msg = f"触发需求预测失败: {str(e)}"
            logger.error(error_msg)
    
    def process_weather_data(self, df):
        """处理天气数据"""
        try:
            # 数据清洗
            cleaned_df, error = self.clean_data(df)
            if error:
                return 0, error
            
            # 批量创建数据
            data_list = []
            for _, row in cleaned_df.iterrows():
                # 构建数据项
                data_item = WeatherData(
                    area=str(row.get('area', row.get('region', ''))).strip(),
                    date=row.get('date'),
                    temperature=float(row.get('temperature', 25)) if pd.notna(row.get('temperature')) else 25,
                    humidity=float(row.get('humidity', 60)) if pd.notna(row.get('humidity')) else 60,
                    wind_speed=float(row.get('wind_speed', 0)) if pd.notna(row.get('wind_speed')) else 0,
                    rainfall=float(row.get('rainfall', 0)) if pd.notna(row.get('rainfall')) else 0,
                    weather_type=str(row.get('weather_type', row.get('weather', 'sunny'))).strip()
                )
                data_list.append(data_item)
            
            # 批量入库
            if data_list:
                WeatherData.objects.bulk_create(data_list, batch_size=1000)
                logger.info(f"成功入库天气数据: {len(data_list)}条")
            
            return len(data_list), None
            
        except Exception as e:
            error_msg = f"处理天气数据失败: {str(e)}"
            logger.error(error_msg)
            return 0, error_msg
    
    def get_data_stats(self, user=None):
        """获取数据统计信息"""
        try:
            stats = {
                'total_ride_data': 0,
                'total_weather_data': 0,
                'recent_ride_data': 0,
                'recent_weather_data': 0
            }
            
            # 骑行数据统计
            if user and not user.is_admin:
                stats['total_ride_data'] = BikeRideData.objects.filter(upload_user=user).count()
                stats['recent_ride_data'] = BikeRideData.objects.filter(
                    upload_user=user,
                    ride_datetime__date__gte=timezone.now().date() - timezone.timedelta(days=7)
                ).count()
            else:
                stats['total_ride_data'] = BikeRideData.objects.count()
                stats['recent_ride_data'] = BikeRideData.objects.filter(
                    ride_datetime__date__gte=timezone.now().date() - timezone.timedelta(days=7)
                ).count()
            
            # 天气数据统计
            stats['total_weather_data'] = WeatherData.objects.count()
            stats['recent_weather_data'] = WeatherData.objects.filter(
                date__gte=timezone.now().date() - timezone.timedelta(days=7)
            ).count()
            
            return stats
            
        except Exception as e:
            logger.error(f"获取数据统计失败: {str(e)}")
            return {
                'total_ride_data': 0,
                'total_weather_data': 0,
                'recent_ride_data': 0,
                'recent_weather_data': 0
            }
    
    def export_data(self, data_type, user=None):
        """导出数据"""
        try:
            if data_type == 'ride':
                if user and not user.is_admin:
                    data = BikeRideData.objects.filter(upload_user=user)
                else:
                    data = BikeRideData.objects.all()
                
                # 转换为DataFrame
                df = pd.DataFrame([
                    {
                        'id': item.id,
                        'data_source': item.data_source,
                        'start_point': item.start_point,
                        'end_point': item.end_point,
                        'ride_datetime': item.ride_datetime,
                        'duration': item.duration,
                        'distance': item.distance,
                        'temperature': item.temperature,
                        'wind_speed': item.wind_speed,
                        'status': item.status,
                        'upload_user': item.upload_user.username if item.upload_user else '',
                        'upload_time': item.upload_time
                    }
                    for item in data
                ])
                
            elif data_type == 'weather':
                data = WeatherData.objects.all()
                
                df = pd.DataFrame([
                    {
                        'id': item.id,
                        'area': item.area,
                        'date': item.date,
                        'temperature': item.temperature,
                        'humidity': item.humidity,
                        'wind_speed': item.wind_speed,
                        'rainfall': item.rainfall,
                        'weather_type': item.weather_type
                    }
                    for item in data
                ])
            else:
                return None, "不支持的数据类型"
            
            return df, None
            
        except Exception as e:
            error_msg = f"导出数据失败: {str(e)}"
            logger.error(error_msg)
            return None, error_msg
    
    def get_data_by_date_range(self, start_date, end_date, region=None):
        """按日期范围获取数据"""
        try:
            # 查询骑行数据
            rides = BikeRideData.objects.filter(
                ride_datetime__date__range=[start_date, end_date]
            )
            
            if region:
                rides = rides.filter(start_point__icontains=region)
            
            # 关联天气数据
            result = []
            for ride in rides:  # 移除数量限制，确保所有数据都能被读取
                weather = None
                try:
                    weather = WeatherData.objects.filter(
                        area__icontains=ride.start_point,
                        date=ride.ride_datetime.date()
                    ).first()
                except:
                    pass
                
                result.append({
                    'ride': ride,
                    'weather': weather
                })
            
            return result, None
            
        except Exception as e:
            error_msg = f"获取数据失败: {str(e)}"
            logger.error(error_msg)
            return None, error_msg
    
    def generate_test_data(self, days=7, rides_per_day=100):
        """生成测试数据"""
        try:
            import random
            # 生成骑行数据
            ride_data = []
            start_date = timezone.now().date() - timezone.timedelta(days=days)
            
            for day in range(days):
                current_date = start_date + timezone.timedelta(days=day)
                
                for _ in range(rides_per_day):
                    # 随机时间
                    hour = random.randint(0, 23)
                    minute = random.randint(0, 59)
                    second = random.randint(0, 59)
                    ride_datetime = current_date.replace(hour=hour, minute=minute, second=second)
                    
                    # 随机站点
                    stations = [
                        '城市中心商业区', '科技园区', '居民区A', '居民区B',
                        '交通枢纽', '教育区', '医疗区', '文化区'
                    ]
                    start_point = random.choice(stations)
                    end_point = random.choice([s for s in stations if s != start_point])
                    
                    # 随机数据
                    duration = random.uniform(5, 60)
                    distance = random.uniform(1, 10)
                    temperature = random.uniform(15, 30)
                    wind_speed = random.uniform(0, 5)
                    
                    ride_data.append({
                        'data_source': 'test',
                        'start_point': start_point,
                        'end_point': end_point,
                        'ride_datetime': ride_datetime,
                        'duration': duration,
                        'distance': distance,
                        'temperature': temperature,
                        'wind_speed': wind_speed,
                        'status': 'cleaned'
                    })
            
            # 生成天气数据
            weather_data = []
            weather_types = ['sunny', 'cloudy', 'rainy', 'windy']
            
            for day in range(days):
                current_date = start_date + timezone.timedelta(days=day)
                
                for area in ['城市中心', '科技园区', '居民区', '交通枢纽']:
                    temperature = random.uniform(15, 30)
                    humidity = random.uniform(40, 80)
                    wind_speed = random.uniform(0, 5)
                    rainfall = random.uniform(0, 20) if random.random() < 0.3 else 0
                    weather_type = random.choice(weather_types)
                    
                    weather_data.append({
                        'area': area,
                        'date': current_date,
                        'temperature': temperature,
                        'humidity': humidity,
                        'wind_speed': wind_speed,
                        'rainfall': rainfall,
                        'weather_type': weather_type
                    })
            
            return ride_data, weather_data
            
        except Exception as e:
            error_msg = f"生成测试数据失败: {str(e)}"
            logger.error(error_msg)
            return None, error_msg
    
    def sync_campus_vehicle_data(self):
        """同步校园车辆定位系统数据"""
        try:
            # 模拟调用校园车辆定位系统接口
            # 实际项目中，这里应该调用真实的API接口
            logger.info("开始同步校园车辆定位系统数据")
            
            # 模拟API响应
            mock_response = {
                'vehicles': [
                    {
                        'vehicle_id': f'Bike_{i}',
                        'latitude': 39.915 + (i % 10) * 0.001,
                        'longitude': 119.528 + (i % 10) * 0.001,
                        'status': 'available' if i % 2 == 0 else 'riding',
                        'last_updated': timezone.now().isoformat()
                    }
                    for i in range(50)
                ]
            }
            
            # 处理车辆数据
            vehicle_data = []
            for vehicle in mock_response['vehicles']:
                if vehicle['status'] == 'available':
                    # 构建车辆数据
                    vehicle_data.append({
                        'vehicle_id': vehicle['vehicle_id'],
                        'latitude': vehicle['latitude'],
                        'longitude': vehicle['longitude'],
                        'status': vehicle['status']
                    })
            
            logger.info(f"成功同步{len(vehicle_data)}辆可用车辆数据")
            return vehicle_data, None
            
        except Exception as e:
            error_msg = f"同步校园车辆数据失败: {str(e)}"
            logger.error(error_msg)
            return None, error_msg
    
    def start_scheduled_sync(self):
        """启动定时同步任务"""
        try:
            # 每5分钟同步一次校园车辆数据
            schedule.every(5).minutes.do(self.sync_campus_vehicle_data)
            
            # 每小时清理一次孤立数据
            schedule.every().hour.do(self.clean_isolated_data)
            
            # 在后台线程中运行
            def run_schedule():
                while True:
                    schedule.run_pending()
                    time.sleep(60)
            
            sync_thread = Thread(target=run_schedule)
            sync_thread.daemon = True
            sync_thread.start()
            
            logger.info("定时同步任务已启动")
            return True
            
        except Exception as e:
            error_msg = f"启动定时同步任务失败: {str(e)}"
            logger.error(error_msg)
            return False
    
    def clean_isolated_data(self):
        """清理孤立数据集"""
        try:
            # 清理测试数据
            test_data_count = BikeRideData.objects.filter(data_source='test').delete()[0]
            if test_data_count > 0:
                logger.info(f"清理了{test_data_count}条测试数据")
            
            # 清理状态为invalid的数据
            invalid_data_count = BikeRideData.objects.filter(status='invalid').delete()[0]
            if invalid_data_count > 0:
                logger.info(f"清理了{invalid_data_count}条无效数据")
            
            # 清理没有坐标的车辆数据
            from operation_management.models import Vehicle
            vehicle_count = Vehicle.objects.filter(Q(latitude__isnull=True) | Q(longitude__isnull=True)).delete()[0]
            if vehicle_count > 0:
                logger.info(f"清理了{vehicle_count}条无坐标车辆数据")
            
            # 清理超出燕大边界的车辆数据
            from operation_management.models import Vehicle
            yanshan_bounds = {
                'north': 39.9550,
                'south': 39.9450,
                'east': 119.5400,
                'west': 119.5250
            }
            out_of_bounds_count = Vehicle.objects.filter(
                Q(latitude__gt=yanshan_bounds['north']) |
                Q(latitude__lt=yanshan_bounds['south']) |
                Q(longitude__gt=yanshan_bounds['east']) |
                Q(longitude__lt=yanshan_bounds['west'])
            ).delete()[0]
            if out_of_bounds_count > 0:
                logger.info(f"清理了{out_of_bounds_count}条超出燕大边界的车辆数据")
            
            return test_data_count + invalid_data_count + vehicle_count + out_of_bounds_count
            
        except Exception as e:
            error_msg = f"清理孤立数据失败: {str(e)}"
            logger.error(error_msg)
            return 0
    
    def batch_upload_excel(self, files, user=None):
        """批量上传Excel文件"""
        try:
            total_count = 0
            
            for file in files:
                # 验证文件
                valid, message = self.validate_file(file)
                if not valid:
                    logger.warning(f"文件验证失败: {message}")
                    continue
                
                # 读取文件
                df, error = self.read_file(file)
                if error:
                    logger.warning(f"文件读取失败: {error}")
                    continue
                
                # 处理数据
                count, error = self.process_ride_data(df, user)  # 传入真实用户
                if error:
                    logger.warning(f"处理数据失败: {error}")
                    continue
                
                total_count += count
            
            logger.info(f"批量上传完成，成功处理{total_count}条数据")
            return total_count, None
            
        except Exception as e:
            error_msg = f"批量上传失败: {str(e)}"
            logger.error(error_msg)
            return 0, error_msg

# 全局数据服务实例
data_service = DataService()
