"""Inspect peak hour data in the core dataset."""
import pandas as pd

df = pd.read_csv('ysu_62_stations_hourly_core_dataset.csv')

# Find hours with actual flow
df['hour'] = pd.to_datetime(df['hour'])
df['date'] = df['hour'].dt.date
df['hour_of_day'] = df['hour'].dt.hour

# Find a date with high variation
daily_inventory_range = df.groupby('date')['inventory'].agg(['min','max'])
daily_inventory_range['range'] = daily_inventory_range['max'] - daily_inventory_range['min']
high_variation_days = daily_inventory_range.nlargest(5, 'range').index.tolist()
print("高波动日期:", high_variation_days)

# Check peak hours (7-9 AM, 5-7 PM) on a high variation day
target_date = high_variation_days[0]
day_data = df[df['date'] == target_date]

print(f"\n日期 {target_date} 各小时的总流量统计:")
hourly_total_flow = day_data.groupby('hour_of_day').agg({
    'inflow': 'sum',
    'outflow': 'sum',
    'net_flow': 'sum',
    'inventory': ['min', 'max', 'mean']
}).round(1)
print(hourly_total_flow.to_string())

# Check a specific high-flow station at peak hour
print(f"\n日期 {target_date} 8:00-9:00 各站点数据:")
peak_hour = day_data[(day_data['hour_of_day'] == 8)]
print(peak_hour[['ysu_id', 'ysu_name', 'inflow', 'outflow', 'net_flow', 'inventory']].sort_values('inflow', ascending=False).head(15).to_string())
