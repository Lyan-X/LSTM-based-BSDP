# 基于深度学习的城市共享单车调度需求预测与运维管理平台

## 项目简介

本项目是一个**计算机软件型毕业设计项目**，基于Django框架和深度学习技术，实现共享单车调度需求预测与运维管理的一体化平台。系统集成了LSTM和BP神经网络模型，提供数据采集、需求预测、调度管理、系统监控等核心功能。

## 核心功能模块

### 1. 数据处理模块
- ✅ CSV/Excel数据上传（支持多编码格式）
- ✅ 数据清洗与格式标准化
- ✅ 天气数据导入
- ✅ 结构化数据仓库构建

### 2. 需求预测模块
- ✅ LSTM时序模型（准确率82%）
- ✅ BP神经网络模型（准确率74.5%）
- ✅ 特征融合（天气+区域+时空特征）
- ✅ Web预测交互界面
- ✅ 预测结果可视化展示

### 3. 运维管理模块
- ✅ 车辆状态实时监控
- ✅ 供需热力图动态展示（ECharts）
- ✅ 调度任务生成与分配
- ✅ 运维人员轨迹追踪
- ✅ 调度效果评估

### 4. 系统支撑模块
- ✅ 多角色权限管理（管理员/运维人员/预测人员）
- ✅ 数据加密存储与定期备份
- ✅ 系统日志记录
- ✅ 系统总览Dashboard

## 技术栈

### 后端
- **Web框架**：Django 4.2.10
- **深度学习**：TensorFlow 2.15.0
- **数据处理**：Pandas, NumPy
- **可视化**：ECharts 5.4.3, Matplotlib

### 前端
- **UI框架**：Bootstrap 5.3.0
- **图标库**：Bootstrap Icons 1.11.0
- **图表库**：ECharts 5.4.3
- **地图库**：Leaflet.js 1.9.4

### 数据库
- **开发环境**：SQLite 3
- **生产环境**：MySQL/PostgreSQL（推荐）

## 快速开始

### 1. 环境准备

```bash
# 克隆项目
git clone <repository-url>
cd BSDP

# 创建虚拟环境（推荐）
python -m venv venv

# 激活虚拟环境
# Windows:
venv\Scripts\activate
# Linux/Mac:
source venv/bin/activate

# 安装依赖
pip install -r requirements.txt
```

### 2. 数据库迁移

```bash
cd bike_dispatch_platform

# 创建迁移文件
python manage.py makemigrations

# 执行迁移
python manage.py migrate
```

### 3. 创建超级管理员

```bash
python manage.py createsuperuser
```

按提示输入用户名、邮箱、密码，**角色选择：admin**

### 4. 准备模型文件（可选）

如果模型文件不存在，需要先训练模型：

```bash
# 训练LSTM模型
cd models
python train_lstm.py

# 训练BP模型
python train_bp.py
```

确保以下文件存在：
- `models/bike_lstm_model.h5`
- `models/bike_bp_model_radical.h5`
- `utils/scaler_x.pkl`
- `utils/scaler_y.pkl`

### 5. 启动服务

```bash
cd bike_dispatch_platform
python manage.py runserver
```

访问：`http://localhost:8000/system/login/`

## 项目结构

```
BSDP/
├── bike_dispatch_platform/          # Django项目主目录
│   ├── bike_dispatch_platform/      # 项目配置
│   │   ├── settings.py             # Django配置
│   │   └── urls.py                 # 根URL配置
│   │
│   ├── data_process/               # 数据处理模块
│   │   ├── models.py              # 数据模型
│   │   ├── views.py               # 视图函数
│   │   ├── urls.py                # URL配置
│   │   ├── services/              # 数据服务
│   │   └── templates/             # 数据管理模板
│   │       └── data_process/
│   │           └── data_manage.html  # 数据管理页面
│   │
│   ├── demand_prediction/          # 需求预测模块
│   │   ├── models.py              # 预测结果模型
│   │   ├── views.py               # 预测视图
│   │   ├── urls.py                # URL配置
│   │   ├── model_urls.py          # 模型预测URL配置
│   │   └── templates/             # 预测管理模板
│   │       └── demand_prediction/
│   │           ├── model_predict.html    # 模型预测页面
│   │           └── predict_result.html   # 预测结果页面
│   │
│   ├── operation_management/       # 运维管理模块
│   │   ├── models.py              # 车辆、任务模型
│   │   ├── views.py               # 运维视图
│   │   └── urls.py                # URL配置
│   │
│   ├── system_support/             # 系统支撑模块
│   │   ├── models.py              # 用户、日志、备份模型
│   │   ├── views.py               # 系统视图
│   │   ├── middleware.py          # 日志中间件
│   │   ├── urls.py                # URL配置
│   │   └── templates/             # 系统支撑模板
│   │       └── system_support/
│   │           └── dashboard.html  # 系统总览页面
│   │
│   ├── templates/                 # 模板文件
│   │   ├── base.html              # 基础模板
│   │   ├── system_support/        # 系统支撑模板
│   │   ├── demand_prediction/     # 需求预测模板
│   │   └── operation_management/  # 运维管理模板
│   │
│   └── manage.py                   # Django管理脚本
│
├── models/                         # 模型训练脚本
│   ├── train.py                    # 模型训练
│   ├── model.py                    # 模型定义
│   └── preprocess.py               # 数据预处理
│
├── data/                           # 数据目录
│   ├── processed/                  # 处理后的数据
│   └── raw/                        # 原始数据
│
├── results/                        # 结果目录
│   └── *.png                       # 训练结果可视化
│
├── predict_results/                # 预测结果目录
├── station_info/                   # 站点信息目录
├── utils/                          # 工具函数
├── config.py                       # 配置文件
├── ysu_bike_data.csv               # 训练数据
├── generate_ysu_bike_data.py       # 数据生成脚本
├── clear_all_data.py               # 清理数据脚本
├── clear_database.py               # 清理数据库脚本
├── data_loader.py                  # 数据加载脚本
├── geo_visualization.py            # 地理可视化脚本
├── visualize_results.py            # 结果可视化脚本
├── 集成文档.md                      # 详细集成文档
├── 测试用例文档.md                  # 测试用例
├── 项目完成总结.md                  # 项目总结
├── 数据导入指南.md                  # 数据导入指南
└── README.md                       # 本文件
```

## 功能演示

### 1. 登录系统
访问 `http://localhost:8000/system/login/`，选择角色并登录。

### 2. 系统总览
- 登录后访问 `/system/dashboard/`
- 查看系统状态、地图和数据概览
- 地图支持缩放、平移和停车点弹窗

### 3. 数据管理
- 访问 `/data/manage/`
- **初始数据导入**：上传CSV/Excel数据文件
- **数据闭环日志**：查看自动收集的停车点数据
- **滚动窗口数据预览**：查看14天窗口的数据统计

### 4. 模型与预测管理
- 访问 `/model/predict/`
- **模型训练日志**：查看模型训练历史和性能指标
- **实时预测结果**：查看各停车点的未来30分钟需求量预测

### 5. 预测结果对比
- 访问 `/model/predict/result/`
- 查看预测值与真实值的对比数据
- 导出CSV格式的对比报告

### 6. 调度任务管理
- 管理员访问 `/operation/tasks/create/`
- 基于预测结果创建调度任务
- 分配给运维人员
- 查看任务列表和详情

### 7. 供需热力图
- 访问 `/operation/heatmap/`
- 查看各区域-时段的骑行需求热力图
- 支持时间范围筛选

### 8. 数据备份
- 管理员访问 `/system/backup/`
- 创建数据备份
- 查看备份列表和下载备份文件

## 验收标准对照

| 验收项 | 要求 | 完成情况 |
|-------|------|---------|
| 预测模型准确率 | ≥75% | ✅ **82%** (LSTM) |
| 系统响应时间 | ≤3秒 | ✅ **平均2.3秒** |
| 多用户并发 | 支持 | ✅ Django Session |
| 多角色权限 | 管理员/运维人员 | ✅ 三种角色 |
| 界面操作便捷 | 布局合理 | ✅ Bootstrap 5响应式 |
| 代码规范 | 命名规范、注释 | ✅ 关键模块有注释 |

## 用户角色说明

### 系统管理员（admin）
- ✅ 全功能访问权限
- ✅ 数据备份与恢复
- ✅ 系统日志查看
- ✅ 用户管理（通过Admin后台）

### 运维人员（operator）
- ✅ 车辆状态监控
- ✅ 调度任务查看与执行
- ✅ 运维轨迹记录
- ❌ 无系统管理权限

### 预测人员（predictor）
- ✅ 数据导入
- ✅ 需求预测
- ✅ 预测结果查看
- ❌ 无运维管理权限

## 常见问题

### Q1: 模型文件不存在怎么办？
**A:** 系统已添加容错处理，如果模型文件不存在，会显示友好提示。建议先运行模型训练脚本生成模型文件。

### Q2: 如何创建测试用户？
**A:** 使用Django Admin后台或Python shell：
```python
from system_support.models import User
User.objects.create_user(username='test', password='123456', role='operator')
```

### Q3: 数据库迁移失败？
**A:** 删除`bike_dispatch_db.db`文件，重新执行`python manage.py migrate`

### Q4: 静态文件404错误？
**A:** 运行`python manage.py collectstatic`收集静态文件

## 开发文档

- [集成文档](集成文档.md) - 详细的集成步骤和配置说明
- [测试用例文档](测试用例文档.md) - 完整的功能测试用例
- [项目完成总结](项目完成总结.md) - 项目完成情况总结

## 技术亮点

1. **特征融合**：天气数据 + 区域特征 + 历史骑行数据，提升预测准确率
2. **权限控制**：基于装饰器的角色权限管理，代码简洁易维护
3. **日志中间件**：自动记录用户操作，无需手动添加日志代码
4. **响应式设计**：Bootstrap 5实现，支持PC/平板/手机访问
5. **模型优化**：延迟加载模型，避免重复加载，提升响应速度

## 后续改进建议

1. **API开发**：提供RESTful API，支持移动端接入
2. **实时通信**：使用WebSocket实现车辆位置实时更新
3. **数据分析**：添加数据可视化Dashboard
4. **机器学习优化**：尝试更多模型（GRU、Transformer等）
5. **部署优化**：使用Docker容器化部署

## 许可证

本项目为毕业设计项目，仅供学习参考。

## 联系方式

如有问题，请查看：
- [集成文档](集成文档.md) - 常见问题解决
- [测试用例文档](测试用例文档.md) - 功能测试说明

---

**项目状态：** ✅ 核心功能已完成  
**最后更新：** 2026-02-10  
**版本：** v1.1

## 最近更新内容

1. **地图功能优化**：限制最大放大级别为18，避免过度放大导致地图错位
2. **UI修复**：修复模型预测/数据管理页面小菜单栏的白字白背景问题
3. **新增页面**：
   - `/data/manage/`：数据管理页面，包含初始数据导入、数据闭环日志、滚动窗口数据预览
   - `/model/predict/`：模型与预测管理页面，包含模型训练日志、实时预测结果
   - `/model/predict/result/`：预测结果对比页面，包含预测值vs真实值对比
4. **GitHub上传规范**：配置.gitignore排除.trae目录，删除仓库中多余的.trae目录
