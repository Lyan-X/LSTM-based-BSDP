
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
