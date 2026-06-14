"""
实时运行系统设计
基于 LSTM 预测结果实现 10 秒刷新
"""
import numpy as np
import pandas as pd
import tensorflow as tf
import pickle
from pathlib import Path
import time
import threading
from datetime import datetime, timedelta

# 项目根目录
BASE_DIR = Path(__file__).parent

class RealTimeSystem:
    """实时运行系统"""
    
    def __init__(self):
        self.model_path = BASE_DIR / 'lstm_model'
        self.scaler_path = BASE_DIR / 'scaler.pkl'
        self.dataset_path = BASE_DIR / 'ysu_62_stations_hourly_core_dataset.csv'
        self.stations = 62
        self.total_vehicles = 1200
        self.update_interval = 10  # 10秒刷新
        self.hourly_update_interval = 3600  # 1小时更新预测
        
        # 加载模型和标度器
        self.model = None
        self.scaler = None
        self.load_model()
        
        # 初始化站点状态
        self.station_status = {}
        self.initialize_station_status()
        
        # 预测结果
        self.predictions = {}
        self.last_prediction_time = None
        
        # 启动线程
        self.running = True
        self.refresh_thread = threading.Thread(target=self.refresh_loop)
        self.prediction_thread = threading.Thread(target=self.prediction_loop)
        
    def load_model(self):
        """加载模型和标度器"""
        try:
            self.model = tf.keras.models.load_model(self.model_path)
            with open(self.scaler_path, 'rb') as f:
                self.scaler = pickle.load(f)
            print("模型加载成功")
        except Exception as e:
            print(f"模型加载失败: {e}")
    
    def initialize_station_status(self):
        """初始化站点状态"""
        # 从数据集中获取初始车辆数
        df = pd.read_csv(self.dataset_path)
        df['hour'] = pd.to_datetime(df['hour'])
        
        for station_id in range(1, 63):
            station_data = df[df['ysu_id'] == station_id].sort_values('hour')
            if not station_data.empty:
                # 使用最新的车辆存量
                latest_inventory = station_data.tail(1)['inventory'].values[0]
                self.station_status[station_id] = {
                    'current_vehicles': latest_inventory,
                    'last_update': datetime.now()
                }
            else:
                # 默认为 20 辆
                self.station_status[station_id] = {
                    'current_vehicles': 20,
                    'last_update': datetime.now()
                }
        
        # 确保总量为 1200
        self.balance_vehicles()
    
    def balance_vehicles(self):
        """平衡车辆数量，确保总量为 1200"""
        current_total = sum([status['current_vehicles'] for status in self.station_status.values()])
        difference = self.total_vehicles - current_total
        
        if difference != 0:
            # 平均分配差异
            per_station = difference / len(self.station_status)
            remainder = difference % len(self.station_status)
            
            for station_id, status in self.station_status.items():
                adjustment = int(per_station)
                if remainder > 0:
                    adjustment += 1
                    remainder -= 1
                status['current_vehicles'] = max(0, status['current_vehicles'] + adjustment)
    
    def get_station_data(self, station_id, hours=48):
        """获取站点历史数据"""
        df = pd.read_csv(self.dataset_path)
        df['hour'] = pd.to_datetime(df['hour'])
        
        # 获取指定站点的最新数据
        station_data = df[df['ysu_id'] == station_id].sort_values('hour')
        if len(station_data) < hours:
            return None
        
        # 取最近的 hours 小时数据
        recent_data = station_data.tail(hours)
        features = recent_data[['inflow', 'outflow', 'net_flow']].values
        
        return features
    
    def update_predictions(self):
        """更新预测结果"""
        if self.model is None or self.scaler is None:
            print("模型未加载，无法更新预测")
            return
        
        print("更新预测结果...")
        
        for station_id in range(1, 63):
            # 获取站点历史数据
            historical_data = self.get_station_data(station_id)
            if historical_data is None:
                self.predictions[station_id] = {'error': 'Insufficient data'}
                continue
            
            # 标准化数据
            scaled_data = self.scaler.transform(historical_data)
            
            # 准备输入
            X_input = np.array([scaled_data])
            
            # 预测
            try:
                pred = self.model.predict(X_input)[0]
                
                # 反标准化
                temp = np.zeros((1, len(pred), 3))
                temp[0, :, 2] = pred
                pred_denorm = self.scaler.inverse_transform(temp[0, :, :])[:, 2]
                
                self.predictions[station_id] = {
                    'station_id': station_id,
                    'predictions': pred_denorm.tolist(),
                    'timestamps': pd.date_range(start=datetime.now(), periods=48, freq='H').astype(str).tolist()
                }
            except Exception as e:
                self.predictions[station_id] = {'error': str(e)}
        
        self.last_prediction_time = datetime.now()
        print("预测结果更新完成")
    
    def calculate_interpolation(self, station_id, current_time):
        """计算 10 秒级插值"""
        if station_id not in self.predictions:
            return 0
        
        prediction = self.predictions[station_id]
        if 'error' in prediction:
            return 0
        
        # 找到当前小时的预测
        current_hour = current_time.replace(minute=0, second=0, microsecond=0)
        next_hour = current_hour + timedelta(hours=1)
        
        # 计算当前小时在预测中的索引
        for i, timestamp_str in enumerate(prediction['timestamps']):
            timestamp = pd.to_datetime(timestamp_str)
            if timestamp == current_hour:
                # 计算当前小时的净流量
                net_flow = prediction['predictions'][i]
                
                # 计算 10 秒的增量
                seconds_in_hour = 3600
                increment_per_second = net_flow / seconds_in_hour
                increment_per_10s = increment_per_second * 10
                
                return increment_per_10s
        
        return 0
    
    def update_station_status(self):
        """更新站点状态"""
        current_time = datetime.now()
        total_increment = 0
        increments = {}
        
        # 计算每个站点的增量
        for station_id, status in self.station_status.items():
            increment = self.calculate_interpolation(station_id, current_time)
            increments[station_id] = increment
            total_increment += increment
        
        # 调整增量，确保总量守恒
        if total_increment != 0:
            adjustment = -total_increment / len(self.station_status)
            for station_id in increments:
                increments[station_id] += adjustment
        
        # 更新站点状态
        for station_id, increment in increments.items():
            status = self.station_status[station_id]
            new_vehicles = status['current_vehicles'] + increment
            
            # 边界检查
            new_vehicles = max(0, new_vehicles)
            # 假设最大容量为 30
            new_vehicles = min(30, new_vehicles)
            
            status['current_vehicles'] = new_vehicles
            status['last_update'] = current_time
        
        # 再次平衡，确保总量为 1200
        self.balance_vehicles()
    
    def refresh_loop(self):
        """10 秒刷新循环"""
        while self.running:
            try:
                self.update_station_status()
                print(f"[{datetime.now()}] 站点状态已更新")
                print(f"当前总车辆数: {sum([s['current_vehicles'] for s in self.station_status.values()])}")
            except Exception as e:
                print(f"刷新循环错误: {e}")
            
            time.sleep(self.update_interval)
    
    def prediction_loop(self):
        """每小时更新预测循环"""
        while self.running:
            try:
                self.update_predictions()
            except Exception as e:
                print(f"预测循环错误: {e}")
            
            time.sleep(self.hourly_update_interval)
    
    def start(self):
        """启动系统"""
        print("启动实时运行系统...")
        
        # 初次更新预测
        self.update_predictions()
        
        # 启动线程
        self.refresh_thread.daemon = True
        self.prediction_thread.daemon = True
        
        self.refresh_thread.start()
        self.prediction_thread.start()
        
        print("实时运行系统已启动")
    
    def stop(self):
        """停止系统"""
        print("停止实时运行系统...")
        self.running = False
        
        if self.refresh_thread.is_alive():
            self.refresh_thread.join()
        if self.prediction_thread.is_alive():
            self.prediction_thread.join()
        
        print("实时运行系统已停止")
    
    def get_current_status(self):
        """获取当前状态"""
        return self.station_status


if __name__ == '__main__':
    system = RealTimeSystem()
    system.start()
    
    # 运行 5 分钟后停止
    try:
        time.sleep(300)
    finally:
        system.stop()
