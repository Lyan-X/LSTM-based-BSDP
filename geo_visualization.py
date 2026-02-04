import folium
import pandas as pd

def plot_geo_heatmap(df, scalers=None):
    """
    地理热力图可视化（folium）
    显示燕山大学各还车点的车辆分布
    """
    # 计算燕山大学中心点
    from config import YSU_BOUNDARY
    lats = [p[1] for p in YSU_BOUNDARY]
    lons = [p[0] for p in YSU_BOUNDARY]
    center_lat = sum(lats) / len(lats)
    center_lon = sum(lons) / len(lons)
    
    # 初始化地图（燕山大学中心点）
    m = folium.Map(
        location=[center_lat, center_lon], 
        zoom_start=15,
        max_zoom=19,  # 最大放大级别锁定为19（左下角显示20m）
        control_scale=True  # 显示比例尺
    )
    
    # 添加多边形边界遮罩
    # 转换边界格式
    boundary_coords = [(p[1], p[0]) for p in YSU_BOUNDARY]  # folium使用(lat, lon)格式
    folium.Polygon(
        locations=boundary_coords,
        color='blue',
        fill=True,
        fill_color='blue',
        fill_opacity=0.1,
        popup='燕山大学边界'
    ).add_to(m)
    
    # 取最新时间的车辆数
    latest_time = df["timestamp"].max()
    latest_df = df[df["timestamp"] == latest_time]
    
    # 遍历还车点
    for idx, row in latest_df.iterrows():
        # 标记颜色（车辆数越少，颜色越红；越多越绿）
        cnt = row["bike_count"]
        color = "red" if cnt < 15 else "orange" if cnt < 30 else "green"
        
        # 添加标记
        folium.Marker(
            location=[row["latitude"], row["longitude"]],
            popup=f"{row['location_name']}<br>车辆数：{cnt}",
            icon=folium.Icon(color=color, icon="bicycle")
        ).add_to(m)
    
    # 保存地图
    m.save("results/ysu_bike_geo_distribution.html")
    return m

def load_bike_data():
    """
    加载自行车数据
    """
    return pd.read_csv("ysu_bike_data.csv")

if __name__ == "__main__":
    # 加载数据
    bike_data = load_bike_data()
    
    # 生成地理热力图
    m = plot_geo_heatmap(bike_data)
    
    print("地理热力图已生成到 results 文件夹：results/ysu_bike_geo_distribution.html")
    print(f"地图中心点：[39.909689, 119.528179]")
    print(f"显示的还车点数量：{len(bike_data['location_name'].unique())}")
