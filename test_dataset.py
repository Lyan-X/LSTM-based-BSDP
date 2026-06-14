"""Inspect the core dataset for inflow/outflow data."""
import pandas as pd

df = pd.read_csv('ysu_62_stations_hourly_core_dataset.csv')
print("数据集基本信息:")
print(f"  总行数: {len(df)}")
print(f"  列名: {list(df.columns)}")
print(f"  时间范围: {df['hour'].min()} -> {df['hour'].max()}")
print(f"\n数据统计:")
print(df[['inflow', 'outflow', 'net_flow', 'inventory']].describe())

print(f"\n净流量非零行数: {(df['net_flow'] != 0).sum()}")
print(f"流入量非零行数: {(df['inflow'] != 0).sum()}")
print(f"流出量非零行数: {(df['outflow'] != 0).sum()}")

# Check a specific station's data
station_1 = df[df['ysu_id'] == 1].sort_values('hour')
print(f"\n站点1的完整数据(前20行):")
print(station_1[['hour', 'inflow', 'outflow', 'net_flow', 'inventory']].head(20).to_string())
