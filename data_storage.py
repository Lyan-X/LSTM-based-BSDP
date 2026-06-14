"""
数据存储方案
实现核心时序数据库表、实时状态表、预测结果表和可选历史演示表
"""
import sqlite3
import numpy as np
from pathlib import Path
import pandas as pd
from datetime import datetime, timedelta

# 项目根目录
BASE_DIR = Path(__file__).parent

class DataStorage:
    """数据存储管理"""
    
    def __init__(self, db_path='bike_sharing.db'):
        self.db_path = BASE_DIR / db_path
        self.conn = None
        self.cursor = None
        self.initialize_database()
    
    def initialize_database(self):
        """初始化数据库"""
        # 连接数据库
        self.conn = sqlite3.connect(self.db_path)
        self.cursor = self.conn.cursor()
        
        # 创建核心时序数据库表
        self.create_core_timeseries_table()
        
        # 创建实时状态表
        self.create_realtime_status_table()
        
        # 创建预测结果表
        self.create_prediction_results_table()
        
        # 创建可选历史演示表
        self.create_history_demo_table()
        
        # 提交更改
        self.conn.commit()
        print("数据库初始化完成")
    
    def create_core_timeseries_table(self):
        """创建核心时序数据库表"""
        query = '''
        CREATE TABLE IF NOT EXISTS core_timeseries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            station_id INTEGER NOT NULL,
            hour TEXT NOT NULL,
            inflow REAL NOT NULL,
            outflow REAL NOT NULL,
            net_flow REAL NOT NULL,
            inventory INTEGER NOT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(station_id, hour)
        )
        '''
        self.cursor.execute(query)
        
        # 创建索引
        self.cursor.execute('CREATE INDEX IF NOT EXISTS idx_core_timeseries_station_hour ON core_timeseries(station_id, hour)')
    
    def create_realtime_status_table(self):
        """创建实时状态表"""
        query = '''
        CREATE TABLE IF NOT EXISTS realtime_status (
            station_id INTEGER PRIMARY KEY,
            current_vehicles REAL NOT NULL,
            last_update TEXT NOT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
        '''
        self.cursor.execute(query)
    
    def create_prediction_results_table(self):
        """创建预测结果表"""
        query = '''
        CREATE TABLE IF NOT EXISTS prediction_results (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            station_id INTEGER NOT NULL,
            prediction_hour TEXT NOT NULL,
            net_flow_prediction REAL NOT NULL,
            prediction_time TEXT NOT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(station_id, prediction_hour)
        )
        '''
        self.cursor.execute(query)
        
        # 创建索引
        self.cursor.execute('CREATE INDEX IF NOT EXISTS idx_prediction_results_station_hour ON prediction_results(station_id, prediction_hour)')
    
    def create_history_demo_table(self):
        """创建可选历史演示表"""
        query = '''
        CREATE TABLE IF NOT EXISTS history_demo (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            station_id INTEGER NOT NULL,
            hour TEXT NOT NULL,
            inflow REAL NOT NULL,
            outflow REAL NOT NULL,
            net_flow REAL NOT NULL,
            inventory INTEGER NOT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(station_id, hour)
        )
        '''
        self.cursor.execute(query)
        
        # 创建索引
        self.cursor.execute('CREATE INDEX IF NOT EXISTS idx_history_demo_station_hour ON history_demo(station_id, hour)')
    
    def insert_core_timeseries_data(self, station_id, hour, inflow, outflow, net_flow, inventory):
        """插入核心时序数据"""
        query = '''
        INSERT OR REPLACE INTO core_timeseries (station_id, hour, inflow, outflow, net_flow, inventory)
        VALUES (?, ?, ?, ?, ?, ?)
        '''
        self.cursor.execute(query, (station_id, hour, inflow, outflow, net_flow, inventory))
        self.conn.commit()
    
    def update_realtime_status(self, station_id, current_vehicles):
        """更新实时状态"""
        last_update = datetime.now().isoformat()
        query = '''
        INSERT OR REPLACE INTO realtime_status (station_id, current_vehicles, last_update)
        VALUES (?, ?, ?)
        '''
        self.cursor.execute(query, (station_id, current_vehicles, last_update))
        self.conn.commit()
    
    def insert_prediction_result(self, station_id, prediction_hour, net_flow_prediction):
        """插入预测结果"""
        prediction_time = datetime.now().isoformat()
        query = '''
        INSERT OR REPLACE INTO prediction_results (station_id, prediction_hour, net_flow_prediction, prediction_time)
        VALUES (?, ?, ?, ?)
        '''
        self.cursor.execute(query, (station_id, prediction_hour, net_flow_prediction, prediction_time))
        self.conn.commit()
    
    def insert_history_demo_data(self, station_id, hour, inflow, outflow, net_flow, inventory):
        """插入历史演示数据"""
        query = '''
        INSERT OR REPLACE INTO history_demo (station_id, hour, inflow, outflow, net_flow, inventory)
        VALUES (?, ?, ?, ?, ?, ?)
        '''
        self.cursor.execute(query, (station_id, hour, inflow, outflow, net_flow, inventory))
        self.conn.commit()
    
    def clean_history_demo_data(self):
        """清理超过 7 天的历史演示数据"""
        seven_days_ago = (datetime.now() - timedelta(days=7)).isoformat()
        query = '''
        DELETE FROM history_demo WHERE hour < ?
        '''
        self.cursor.execute(query, (seven_days_ago,))
        self.conn.commit()
        print("历史演示数据已清理")
    
    def load_core_dataset(self, dataset_path):
        """从核心数据集中加载数据到数据库"""
        print("加载核心数据集到数据库...")
        
        df = pd.read_csv(dataset_path)
        
        for _, row in df.iterrows():
            self.insert_core_timeseries_data(
                station_id=row['ysu_id'],
                hour=row['hour'],
                inflow=row['inflow'],
                outflow=row['outflow'],
                net_flow=row['net_flow'],
                inventory=row['inventory']
            )
        
        print(f"已加载 {len(df)} 条核心时序数据")
    
    def get_station_data(self, station_id, hours=48):
        """获取站点历史数据"""
        query = '''
        SELECT inflow, outflow, net_flow 
        FROM core_timeseries 
        WHERE station_id = ? 
        ORDER BY hour DESC 
        LIMIT ?
        '''
        self.cursor.execute(query, (station_id, hours))
        results = self.cursor.fetchall()
        
        if len(results) < hours:
            return None
        
        # 反转顺序，使最早的数据在前
        results.reverse()
        return np.array(results)
    
    def get_realtime_status(self):
        """获取所有站点的实时状态"""
        query = 'SELECT station_id, current_vehicles, last_update FROM realtime_status'
        self.cursor.execute(query)
        results = self.cursor.fetchall()
        
        status = {}
        for row in results:
            status[row[0]] = {
                'current_vehicles': row[1],
                'last_update': row[2]
            }
        
        return status
    
    def close(self):
        """关闭数据库连接"""
        if self.conn:
            self.conn.close()
            print("数据库连接已关闭")


if __name__ == '__main__':
    storage = DataStorage()
    
    # 加载核心数据集
    dataset_path = BASE_DIR / 'ysu_62_stations_hourly_core_dataset.csv'
    if dataset_path.exists():
        storage.load_core_dataset(dataset_path)
    
    # 清理历史演示数据
    storage.clean_history_demo_data()
    
    storage.close()
