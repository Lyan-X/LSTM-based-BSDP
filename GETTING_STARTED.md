# 共享单车调度需求预测与运维管理平台 - 快速入门指南

> 毕业设计项目 | 燕山大学 刘妍 (202211040587) | 软件工程专业
> 测试范围：燕山大学校园

## 1. 环境准备

### 系统要求
- Python 3.9+
- pip (Python包管理器)

### 安装依赖
```bash
# 创建虚拟环境（如已有可跳过）
python -m venv bsdp_env

# 激活虚拟环境
# Windows:
bsdp_env\Scripts\activate
# Linux/Mac:
source bsdp_env/bin/activate

# 安装依赖
pip install -r requirements.txt
```

## 2. 数据库初始化

```bash
cd bike_dispatch_platform

# 生成迁移文件
python manage.py makemigrations

# 应用迁移
python manage.py migrate

# 创建超级管理员（如未创建）
python manage.py createsuperuser
```

### 预置用户账号

| 用户名 | 角色 | 说明 |
|--------|------|------|
| Lyan | admin | 系统管理员（全部权限） |
| Admin | admin | 管理员 |
| predict_staff | predictor | 预测人员（数据/模型访问） |
| maintain_staff | operator | 运维人员（任务管理） |

## 3. 启动服务

```bash
cd bike_dispatch_platform
python manage.py runserver 8000
```

浏览器访问：http://127.0.0.1:8000/

## 4. 四大核心模块

### 4.1 数据处理模块（/data/manage/）
- **数据导入**：支持CSV/Excel文件上传（UTF-8/GBK编码自动识别）
- **本地数据录入**：手动录入骑行数据和天气数据（限燕山大学停车点）
- **天气数据管理**：导入/录入天气数据，与骑行数据按时间/区域关联
- **数据处理日志**：记录所有数据导入和处理操作
- **数据可视化**：14天滚动窗口的小时/星期骑行量统计图表
- **数据导出**：支持CSV格式导出骑行数据和天气数据

### 4.2 需求预测模块（/model/predict/）
- **LSTM模型**：时序预测，准确率≥80%，擅长捕捉时间依赖
- **BP神经网络**：多特征融合预测，准确率≥75%，训练速度快
- **需求预测**：选择区域+时段+日期，自动融合天气特征进行预测
- **批量预测**：一键对所有区域24小时进行批量预测
- **模型对比**：LSTM与BP模型性能指标对比（/predict/compare/）
- **预测结果导出**：CSV格式导出（/model/predict/export/）

### 4.3 运维管理模块（/operation/）
- **调度任务管理**：创建/查看/管理调度任务
- **自动生成任务**：基于预测需求自动匹配供需缺口生成调度任务
- **车辆实时监控**：地图展示520辆车辆位置和状态
- **供需热力图**：Leaflet地图+热力图层，展示62个停车点供需状况
- **调度效果评估**：完成率、状态分布、7天趋势图
- **运维人员轨迹追踪**：记录和展示运维人员移动路径

### 4.4 系统支撑模块（/system/）
- **多角色权限**：admin（全部）、operator（任务管理）、predictor（数据/模型）
- **系统日志**：自动记录登录、数据上传、预测操作等
- **数据备份**：一键备份SQLite数据库（加密标记）
- **区域特征管理**：管理燕山大学校园区域的人口密度、商圈类型等

## 5. 关键数据说明

### 不可修改的数据
- **停车点经纬度数据**：`config.py` 中的 `PARKING_SPOTS` 字典（62个停车点坐标）
- **燕山大学边界坐标**：`config.py` 中的 `YSU_BOUNDARY` 多边形
- **测试数据集**：`ysu_bike_data.csv`（44642条燕山大学骑行数据）

### 测试范围
系统默认应用范围为**燕山大学校园**，地图中心点：119.528179, 39.909689

## 6. 技术栈

| 组件 | 版本 | 用途 |
|------|------|------|
| Django | 4.2.10 | Web后端框架 |
| TensorFlow | 2.15.0 | 深度学习模型 |
| Bootstrap | 5.3.0 | 前端UI框架 |
| ECharts | 5.4.3 | 数据可视化图表 |
| Leaflet.js | 1.9.4 | 地图可视化 |
| SQLite3 | - | 开发数据库 |

## 7. 模型训练（可选）

```bash
# 在项目根目录执行
# 训练LSTM模型
python train.py

# 训练BP神经网络
python bp_model.py
```

训练结果保存在 `results/` 目录。

## 8. 项目结构

```
bike_dispatch_platform/          # Django项目根目录
├── bike_dispatch_platform/      # 项目配置
├── data_process/                # 数据处理模块
├── demand_prediction/           # 需求预测模块
├── operation_management/        # 运维管理模块
├── system_support/              # 系统支撑模块
├── templates/                   # HTML模板
├── manage.py                    # Django管理脚本
└── bike_dispatch_db.db          # SQLite数据库

config.py                        # 停车点/边界配置（不可修改）
train_models.py                  # 统一模型训练脚本（LSTM+BP）
simulate_real_time_data.py       # 实时数据模拟器
scheduled_train.py               # 定时训练调度器
preprocess.py                    # 数据预处理脚本
model.py                         # LSTM模型定义
ysu_bike_data.csv                # 燕山大学骑行数据集
requirements.txt                 # Python依赖列表
model_train_log.md               # 模型训练结果日志
```

## 9. 定时任务

### 实时数据模拟器
```bash
# 持续运行（每1分钟生成一批骑行数据+更新车辆状态）
python simulate_real_time_data.py

# 单次运行（测试用）
python simulate_real_time_data.py --once
```
- 按YSU作息时间生成骑行量（早晚高峰多，凌晨少）
- 自动更新520辆车辆的状态（可用/骑行中/故障/锁定）
- 记录到 `DataProcessLog` 和 `BikeRideData` 表

### 定时模型训练
```bash
# 持续运行（每天凌晨2:00自动训练）
python scheduled_train.py

# 立即训练（演示用）
python scheduled_train.py --now
```
- 使用最近7天的数据重新训练LSTM和BP模型
- 新模型精度达标才替换旧模型（LSTM≥80%, BP≥75%）
- 历史模型保存在 `models/history/` 目录

### 手动触发训练（Web界面）
登录后访问 `/model/train/manual/`（POST请求），或在"模型与预测"页面使用训练按钮。

## 10. 毕业答辩演示指南

### 演示步骤
1. **启动系统**
   ```bash
   cd bike_dispatch_platform
   python manage.py runserver 8000
   ```
   浏览器访问 http://127.0.0.1:8000/，用 `Lyan` 账号登录

2. **数据管理演示** → `/data/manage/`
   - 展示数据导入（上传CSV）、本地手动录入、天气数据管理
   - 展示14天滚动窗口的小时/星期骑行量ECharts图表
   - 展示数据导出CSV功能

3. **启动实时数据模拟**（新终端）
   ```bash
   python simulate_real_time_data.py
   ```
   等待1分钟后刷新数据管理页面，展示实时数据流入

4. **需求预测演示** → `/model/predict/`
   - 展示模型训练日志（LSTM R²=81.24%, BP R²=81.33%）
   - 选择区域+时段+日期执行实时预测，展示预测结果
   - 展示批量预测（一键生成所有区域24小时预测）
   - 展示模型对比页面 → `/predict/compare/`

5. **停车点级短期预测** → `/model/predict/spot/`
   - 展示62个YSU停车点的30分钟/1小时需求预测
   - 展示供需缺口排序（短缺/均衡/过剩标识）

6. **供需热力图演示** → `/operation/heatmap/`
   - 展示以燕山大学为中心的Leaflet地图
   - 展示按供需缺口着色的停车点标记（红=短缺，绿=过剩）
   - 点击停车点查看详细供需数据
   - 展示左侧自动调度建议面板

7. **运维管理演示** → `/operation/`
   - 展示车辆实时监控（520辆车辆地图分布）
   - 展示调度任务创建和管理
   - 展示调度效果评估（完成率趋势图）

8. **系统管理演示**（管理员）
   - 展示系统日志 → `/system/logs/`
   - 展示数据备份功能 → `/system/backup/`
   - 展示区域特征管理 → `/system/region/feature/list/`

### 关键数据指标（答辩参考）
| 指标 | 值 | 达标要求 |
|------|-----|---------|
| LSTM模型R² | 81.24% | ≥80% ✓ |
| BP模型R² | 81.33% | ≥75% ✓ |
| YSU停车点 | 62个 | 全覆盖 ✓ |
| 车辆数量 | 520辆 | 初始化 ✓ |
| 页面数 | 21个 | 全部200 OK ✓ |
| 响应时间 | <3s | ≤3s ✓ |

### 截图位置备注
（请在以下页面截图用于答辩PPT）
- 系统首页仪表盘 `/system/dashboard/`
- 数据管理页面（含ECharts图表）`/data/manage/`
- 停车点短期预测表格 `/model/predict/spot/`
- 供需热力图（含调度建议）`/operation/heatmap/`
- 模型对比页面 `/predict/compare/`
- 调度效果评估页面 `/operation/evaluation/`
