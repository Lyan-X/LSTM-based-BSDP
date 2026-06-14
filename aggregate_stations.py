"""
华盛顿 Capital Bikeshare 停车点信息汇总脚本
将所有停车点信息汇总到一个 CSV 文件中，便于后续建立映射关系
"""
import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime

# 项目根目录
BASE_DIR = Path(__file__).parent
DATASET_DIR = BASE_DIR / 'bike_demand_research' / 'dataset'

class StationInfoAggregator:
    """停车点信息汇总器"""
    
    def __init__(self):
        self.dataset_path = DATASET_DIR / 'daily_rent_detail.csv'
        self.stations = {}
    
    def load_data(self):
        """加载数据集"""
        print("加载 Capital Bikeshare 数据集...")
        
        if not self.dataset_path.exists():
            raise FileNotFoundError(f"数据集文件不存在：{self.dataset_path}")
        
        # 加载数据
        df = pd.read_csv(self.dataset_path)
        
        # 数据类型转换
        df['started_at'] = pd.to_datetime(df['started_at'], format='mixed', errors='coerce')
        df['ended_at'] = pd.to_datetime(df['ended_at'], format='mixed', errors='coerce')
        
        # 过滤无效数据
        df = df.dropna(subset=['started_at', 'end_station_id', 'start_station_id'])
        
        print(f"成功加载并过滤后的数据量：{len(df)} 条")
        return df
    
    def aggregate_station_info(self, df):
        """汇总停车点信息"""
        print("汇总停车点信息...")
        
        # 提取起点站信息
        start_stations = df.groupby('start_station_id').agg({
            'start_station_name': 'first',
            'start_lat': 'mean',
            'start_lng': 'mean',
            'ride_id': 'count'
        }).reset_index()
        
        start_stations.columns = ['station_id', 'station_name', 'latitude', 'longitude', 'total_start_rides']
        
        # 提取终点站信息
        end_stations = df.groupby('end_station_id').agg({
            'ride_id': 'count'
        }).reset_index()
        end_stations.columns = ['station_id', 'total_end_rides']
        
        # 合并起点和终点数据
        stations_df = pd.merge(start_stations, end_stations, on='station_id', how='outer')
        stations_df['total_end_rides'] = stations_df['total_end_rides'].fillna(0)
        
        # 计算总骑行量
        stations_df['total_ride_count'] = stations_df['total_start_rides'] + stations_df['total_end_rides']
        
        # 计算小时级平均可用车辆数（基于骑行量估算）
        # 假设每个站点平均每天运营 12 小时
        days = len(df['started_at'].dt.date.unique())
        stations_df['avg_hourly_bikes'] = stations_df['total_ride_count'] / (days * 12)
        
        # 计算车辆周转率（假设每个站点容量为 20 辆）
        stations_df['turnover_rate'] = stations_df['total_ride_count'] / (20 * days)
        
        # 计算潮汐特征
        df['start_hour'] = df['started_at'].dt.hour
        
        # 计算每个站点每小时的出发量
        start_hourly = df.groupby(['start_station_id', 'start_hour']).size().unstack(fill_value=0)
        
        # 计算每个站点每小时的到达量
        end_hourly = df.groupby(['end_station_id', 'start_hour']).size().unstack(fill_value=0)
        
        # 计算每个站点的潮汐特征
        tidal_features = []
        for station_id in stations_df['station_id']:
            # 计算潮汐特征（使用7-9点和17-19点的平均）
            morning_in = 0
            morning_out = 0
            evening_in = 0
            evening_out = 0
            noon_in = 0
            noon_out = 0
            
            # 计算出发量
            if station_id in start_hourly.index:
                for h in [7, 8, 9]:
                    if h in start_hourly.columns:
                        morning_out += start_hourly.loc[station_id, h]
                for h in [17, 18, 19]:
                    if h in start_hourly.columns:
                        evening_out += start_hourly.loc[station_id, h]
                for h in [11, 12, 13]:
                    if h in start_hourly.columns:
                        noon_out += start_hourly.loc[station_id, h]
            
            # 计算到达量
            if station_id in end_hourly.index:
                for h in [7, 8, 9]:
                    if h in end_hourly.columns:
                        morning_in += end_hourly.loc[station_id, h]
                for h in [17, 18, 19]:
                    if h in end_hourly.columns:
                        evening_in += end_hourly.loc[station_id, h]
                for h in [11, 12, 13]:
                    if h in end_hourly.columns:
                        noon_in += end_hourly.loc[station_id, h]
            
            # 计算平均值
            morning_in /= 3
            morning_out /= 3
            evening_in /= 3
            evening_out /= 3
            noon_in /= 3
            noon_out /= 3
            
            # 总流量
            total_morning = morning_in + morning_out
            total_evening = evening_in + evening_out
            total_noon = noon_in + noon_out
            total_all = total_morning + total_evening + total_noon
            
            # 一级分类
            if total_all > 0:
                # 学术办公型：早进晚出
                if morning_in > morning_out * 1.05 and evening_out > evening_in * 1.05:
                    category = 'academic'
                    tidal_feature = '早高峰 7-9 点车辆净流入、晚高峰 17-19 点车辆净流出'
                # 居住型：早出晚进
                elif morning_out > morning_in * 1.05 and evening_in > evening_out * 1.05:
                    category = 'residential'
                    tidal_feature = '早高峰 7-9 点车辆净流出、晚高峰 17-19 点车辆净流入'
                # 综合商业型：午间流量大
                elif total_noon > total_all * 0.3 and abs(morning_in - morning_out) < total_morning * 0.5:
                    category = 'comprehensive'
                    tidal_feature = '午间 11-13 点、晚间 18-21 点流量高峰，潮汐特征平缓'
                # 交通枢纽型：双向流量大
                else:
                    category = 'transit'
                    tidal_feature = '早晚高峰双向集中流量波动，短时流入流出量极大'
            else:
                category = 'transit'
                tidal_feature = '早晚高峰双向集中流量波动，短时流入流出量极大'
            
            tidal_features.append({
                'station_id': station_id,
                'category': category,
                'tidal_feature': tidal_feature,
                'morning_in': morning_in,
                'morning_out': morning_out,
                'evening_in': evening_in,
                'evening_out': evening_out,
                'noon_in': noon_in,
                'noon_out': noon_out
            })
        
        # 合并潮汐特征
        tidal_df = pd.DataFrame(tidal_features)
        stations_df = pd.merge(stations_df, tidal_df, on='station_id', how='left')
        
        # 计算活跃度等级
        stations_df['activity_score'] = stations_df['avg_hourly_bikes'] * 0.7 + stations_df['turnover_rate'] * 0.3
        stations_df['activity_level'] = pd.qcut(
            stations_df['activity_score'], 
            q=[0, 0.2, 0.7, 1.0], 
            labels=['低活跃度', '中活跃度', '高活跃度']
        )
        
        # 清理数据
        stations_df = stations_df.dropna(subset=['station_name', 'latitude', 'longitude'])
        stations_df = stations_df[stations_df['total_ride_count'] > 0]
        
        self.stations = stations_df
        print(f"汇总完成，共 {len(stations_df)} 个停车点")
    
    def export_to_csv(self):
        """导出到 CSV 文件"""
        print("导出停车点信息到 CSV 文件...")
        
        # 选择需要的列
        export_columns = [
            'station_id', 'station_name', 'latitude', 'longitude',
            'total_ride_count', 'avg_hourly_bikes', 'turnover_rate',
            'category', 'tidal_feature', 'activity_level',
            'morning_in', 'morning_out', 'evening_in', 'evening_out', 'noon_in', 'noon_out'
        ]
        
        export_df = self.stations[export_columns].copy()
        
        # 格式化数值
        export_df['avg_hourly_bikes'] = export_df['avg_hourly_bikes'].round(2)
        export_df['turnover_rate'] = export_df['turnover_rate'].round(3)
        export_df['morning_in'] = export_df['morning_in'].round(2)
        export_df['morning_out'] = export_df['morning_out'].round(2)
        export_df['evening_in'] = export_df['evening_in'].round(2)
        export_df['evening_out'] = export_df['evening_out'].round(2)
        export_df['noon_in'] = export_df['noon_in'].round(2)
        export_df['noon_out'] = export_df['noon_out'].round(2)
        
        # 导出文件
        output_path = BASE_DIR / 'washington_stations_complete.csv'
        export_df.to_csv(output_path, index=False, encoding='utf-8-sig')
        
        print(f"\n停车点信息已导出至：{output_path}")
        print(f"\n导出信息：")
        print(f"- 总停车点数量：{len(export_df)}")
        print(f"- 分类统计：")
        print(export_df['category'].value_counts())
        print(f"- 活跃度统计：")
        print(export_df['activity_level'].value_counts())
        
        return output_path
    
    def process(self):
        """执行完整处理流程"""
        try:
            # 加载数据
            df = self.load_data()
            
            # 汇总停车点信息
            self.aggregate_station_info(df)
            
            # 导出到 CSV
            output_path = self.export_to_csv()
            
            print("\n✅ 处理完成！")
            print(f"✅ 停车点信息已汇总至：{output_path}")
            
            return True
            
        except Exception as e:
            print(f"❌ 处理失败：{str(e)}")
            import traceback
            traceback.print_exc()
            return False


if __name__ == '__main__':
    aggregator = StationInfoAggregator()
    success = aggregator.process()
    exit(0 if success else 1)
