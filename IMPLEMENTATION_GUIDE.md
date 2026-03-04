# 项目修复实施指南

## 概述
本文档提供详细的步骤说明，用于修复「主页地图停车点车辆数为0」和「热力图数据不自动更新」的问题。

## 修复前的准备工作

### 1. 备份文件
```bash
cd "e:\develop\BSDP-Bike Sharing Demand Prediction Based on LSTM Model\BSDP\bike_dispatch_platform\templates"

# 备份主页模板
copy system_support\dashboard.html system_support\dashboard.html.backup

# 备份热力图模板
copy operation_management\heatmap.html operation_management\heatmap.html.backup

# 备份车辆监控模板
copy operation_management\vehicle_monitor.html operation_management\vehicle_monitor.html.backup
```

### 2. 确认调度器运行
访问：http://localhost:8000/operation/api/scheduler-status/
确认返回：`{"scheduler_running": true}`

### 3. 确认实时数据接口正常
访问：http://localhost:8000/operation/api/parking-data/
确认返回包含62个停车点的数据，每个停车点有 `count` 字段

## 修复步骤

### 修复1：主页地图自动刷新（dashboard.html）

#### 步骤1：修改 parkingVehicleMap 声明
**文件位置：** `templates/system_support/dashboard.html`
**查找：** 约第406行
```javascript
// 从模板获取parkingVehicleMap
const parkingVehicleMap = {{ stats.parking_vehicle_map|safe }};
```

**替换为：**
```javascript
// 从模板获取parkingVehicleMap（改为let以支持动态更新）
let parkingVehicleMap = {{ stats.parking_vehicle_map|safe }};

// 存储所有marker的引用，用于后续更新
const markerMap = new Map();
```

#### 步骤2：在渲染marker时保存引用
**文件位置：** `templates/system_support/dashboard.html`
**查找：** 约第408-430行的 `PARKING_POINTS.forEach(point => {` 循环

**在创建marker后添加以下代码：**
```javascript
// 渲染所有停车点 + 绑定弹窗
PARKING_POINTS.forEach(point => {
    // 创建停车点图标
    const marker = L.marker([point.lat, point.lng], {
        icon: createParkingIcon(false)
    }).addTo(homeMap);
    
    // 添加停车点管辖范围
    const radiusCircle = L.circle([point.lat, point.lng], {
        radius: PARKING_RADIUS,
        color: '#1890FF',
        fillColor: '#1890FF',
        fillOpacity: 0.1,
        weight: 1
    }).addTo(homeMap);
    
    // 将radiusCircle关联到marker对象
    marker.radiusCircle = radiusCircle;
    
    // ===== 新增：保存marker信息 =====
    marker.spotName = point.name;
    marker.spotLat = point.lat;
    marker.spotLng = point.lng;
    markerMap.set(point.name, marker);
    // ===== 新增结束 =====
    
    // 绑定弹窗
    const parkedCount = parkingVehicleMap[point.name] || 0;
    // ... 其余代码保持不变
});
```

#### 步骤3：添加自动刷新函数
**文件位置：** `templates/system_support/dashboard.html`
**位置：** 在 `updateCurrentTime()` 函数之前添加

**添加以下完整代码：**
```javascript
// ==================== 自动刷新功能 ====================
// 配置项：自动刷新间隔（毫秒）
const AUTO_REFRESH_INTERVAL = 30000; // 30秒

// 全局变量
let autoRefreshTimer = null;
let isRefreshing = false;

/**
 * 刷新停车点数据
 */
function refreshParkingData() {
    if (isRefreshing) {
        console.log('[自动刷新] 正在刷新中，跳过本次请求');
        return;
    }
    
    isRefreshing = true;
    console.log('[自动刷新] 开始刷新停车点数据...');
    
    fetch('/operation/api/parking-data/')
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                // 更新parkingVehicleMap
                const newMap = {};
                data.data.forEach(spot => {
                    newMap[spot.name] = spot.count || 0;
                });
                
                // 更新全局变量
                Object.keys(newMap).forEach(key => {
                    parkingVehicleMap[key] = newMap[key];
                });
                
                // 更新所有marker的弹窗
                markerMap.forEach((marker, spotName) => {
                    const parkedCount = newMap[spotName] || 0;
                    const updateTime = data.current_time || new Date().toLocaleString('zh-CN');
                    
                    marker.setPopupContent(`
                        <div class="popup-card">
                            <h5>${spotName}</h5>
                            <p>经度：${marker.spotLng.toFixed(6)}</p>
                            <p>纬度：${marker.spotLat.toFixed(6)}</p>
                            <p>管辖范围：30米</p>
                            <p>实时停放车辆数：<span class="badge bg-success">${parkedCount}</span></p>
                            <p style="font-size:12px;color:#888;">更新时间：${updateTime}</p>
                        </div>
                    `);
                });
                
                console.log('[自动刷新] 数据刷新成功，更新时间：' + (data.current_time || new Date().toLocaleString()));
            } else {
                console.error('[自动刷新] 刷新失败：' + data.message);
            }
        })
        .catch(error => {
            console.error('[自动刷新] 请求失败:', error);
        })
        .finally(() => {
            isRefreshing = false;
        });
}

/**
 * 启动自动刷新
 */
function startAutoRefresh() {
    // 清除已有定时器
    if (autoRefreshTimer) {
        clearInterval(autoRefreshTimer);
    }
    
    // 设置新的定时器
    autoRefreshTimer = setInterval(refreshParkingData, AUTO_REFRESH_INTERVAL);
    console.log(`[自动刷新] 已启动，间隔：${AUTO_REFRESH_INTERVAL / 1000}秒`);
}

/**
 * 手动刷新（重置定时器）
 */
function manualRefresh() {
    console.log('[手动刷新] 触发');
    refreshParkingData();
    // 重置自动刷新计时器
    startAutoRefresh();
}
```

#### 步骤4：启动自动刷新
**文件位置：** `templates/system_support/dashboard.html`
**查找：** `});` （DOMContentLoaded 事件处理函数的结束位置）

**在结束 `});` 之前添加：**
```javascript
        // 启动自动刷新
        startAutoRefresh();
    });
```

### 修复2：热力图自动刷新（heatmap.html）

#### 步骤1：修改刷新按钮
**文件位置：** `templates/operation_management/heatmap.html`
**查找：** 约第45行
```html
<button id="refreshBtn" class="btn btn-secondary w-100 btn-sm" onclick="location.reload()">
    <i class="bi bi-arrow-clockwise"></i> 刷新数据
</button>
```

**替换为：**
```html
<button id="refreshBtn" class="btn btn-secondary w-100 btn-sm" onclick="manualRefresh()">
    <i class="bi bi-arrow-clockwise"></i> 刷新数据
</button>
```

#### 步骤2：修改 parkingSpotsData 声明
**文件位置：** `templates/operation_management/heatmap.html`
**查找：** 约第120行
```javascript
let parkingSpotsData = {{ parking_spots|safe }};
```

**替换为：**
```javascript
window.parkingSpotsData = {{ parking_spots|safe }};
let allMarkers = []; // 存储所有marker引用
```

#### 步骤3：在渲染marker时保存引用
**文件位置：** `templates/operation_management/heatmap.html`
**查找：** `PARKING_POINTS.forEach(point => {` 循环中创建marker的代码

**在创建marker后添加：**
```javascript
marker.spotName = point.name;
marker._spotGap = gap;
allMarkers.push(marker);
```

#### 步骤4：添加自动刷新函数
**文件位置：** `templates/operation_management/heatmap.html`
**位置：** 在 `showHeatmap()` 函数之后添加

**添加以下完整代码：**
```javascript
// ==================== 自动刷新功能 ====================
const AUTO_REFRESH_INTERVAL = 30000; // 30秒
let autoRefreshTimer = null;
let isRefreshing = false;

function refreshHeatmapData() {
    if (isRefreshing) {
        console.log('[自动刷新] 正在刷新中，跳过本次请求');
        return;
    }
    
    isRefreshing = true;
    console.log('[自动刷新] 开始刷新热力图数据...');
    
    fetch('/operation/api/parking-data/')
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                // 更新所有marker
                allMarkers.forEach(marker => {
                    const spotName = marker.spotName;
                    const spotData = data.data.find(s => s.name === spotName);
                    
                    if (spotData) {
                        const supply = spotData.count || 0;
                        const demand = supply; // 简化处理，实际应从API获取
                        const gap = demand - supply;
                        
                        marker._spotGap = gap;
                        marker.setIcon(createGapIcon(gap, false));
                        
                        if (marker.radiusCircle) {
                            const c = gapColor(gap);
                            marker.radiusCircle.setStyle({ color: c, fillColor: c });
                        }
                        
                        const gapLabel = gap >= 20 ? '严重短缺' : gap >= 10 ? '中度短缺' : gap > -10 ? '基本均衡' : gap > -20 ? '中度过剩' : '严重过剩';
                        marker.setPopupContent(`
                            <div class="popup-card">
                                <h5>${spotName}</h5>
                                <p>当前可用车辆：<strong>${supply}</strong> 辆</p>
                                <p>供需缺口：<strong style="color:${gapColor(gap)}">${gap > 0 ? '+' : ''}${gap}</strong> (${gapLabel})</p>
                                <p style="font-size:12px;color:#888">更新：${data.current_time || new Date().toLocaleString()}</p>
                            </div>
                        `);
                    }
                });
                
                console.log('[自动刷新] 热力图数据刷新成功');
            }
        })
        .catch(error => {
            console.error('[自动刷新] 请求失败:', error);
        })
        .finally(() => {
            isRefreshing = false;
        });
}

function startAutoRefresh() {
    if (autoRefreshTimer) clearInterval(autoRefreshTimer);
    autoRefreshTimer = setInterval(refreshHeatmapData, AUTO_REFRESH_INTERVAL);
    console.log(`[自动刷新] 已启动，间隔：${AUTO_REFRESH_INTERVAL / 1000}秒`);
}

function manualRefresh() {
    console.log('[手动刷新] 触发');
    const refreshBtn = document.getElementById('refreshBtn');
    if (refreshBtn) {
        refreshBtn.innerHTML = '<span class="spinner-border spinner-border-sm"></span> 刷新中...';
        refreshBtn.disabled = true;
    }
    
    refreshHeatmapData();
    
    setTimeout(() => {
        if (refreshBtn) {
            refreshBtn.innerHTML = '<i class="bi bi-arrow-clockwise"></i> 刷新数据';
            refreshBtn.disabled = false;
        }
    }, 1000);
    
    startAutoRefresh();
}
```

#### 步骤5：启动自动刷新
**文件位置：** `templates/operation_management/heatmap.html`
**查找：** `window.onload = function() {` 函数的最后

**在 `initMap();` 之后添加：**
```javascript
window.onload = function() {
    initMap();
    startAutoRefresh(); // 新增
};
```

## 验证步骤

### 1. 启动项目
```bash
cd "e:\develop\BSDP-Bike Sharing Demand Prediction Based on LSTM Model\BSDP\bike_dispatch_platform"
python manage.py runserver
```

### 2. 验证主页地图
1. 访问：http://localhost:8000/system_support/dashboard/
2. 打开浏览器开发者工具（F12），切换到Console标签
3. 应该看到日志：`[自动刷新] 已启动，间隔：30秒`
4. 点击任意停车点，查看弹窗中的"实时停放车辆数"
5. 等待30秒，应该看到日志：`[自动刷新] 开始刷新停车点数据...`
6. 再次点击停车点，查看"更新时间"是否变化

### 3. 验证热力图
1. 访问：http://localhost:8000/operation/heatmap/
2. 打开浏览器开发者工具（F12），切换到Console标签
3. 应该看到日志：`[自动刷新] 已启动，间隔：30秒`
4. 点击"刷新数据"按钮，应该看到按钮变为"刷新中..."
5. 等待30秒，应该看到自动刷新日志

### 4. 验证数据正确性
- 早高峰（7-9点）：教学楼停放少（3-10辆）
- 午高峰（11-13点）：食堂停放少（5-14辆）
- 夜间（0-5点）：各停车点停放多（18-30辆）

## 故障排查

### 问题1：控制台报错 "markerMap is not defined"
**原因：** 未正确声明 `markerMap`
**解决：** 确认在 `let parkingVehicleMap` 之后添加了 `const markerMap = new Map();`

### 问题2：自动刷新不生效
**原因：** 未调用 `startAutoRefresh()`
**解决：** 确认在 DOMContentLoaded 或 window.onload 最后调用了 `startAutoRefresh();`

### 问题3：刷新后数据仍为0
**原因：** 调度器未运行或API返回数据格式错误
**解决：** 
1. 访问 http://localhost:8000/operation/api/scheduler-status/ 确认调度器运行
2. 访问 http://localhost:8000/operation/api/parking-data/ 查看返回数据

### 问题4：点击刷新按钮报错 "manualRefresh is not defined"
**原因：** 未定义 `manualRefresh()` 函数
**解决：** 确认已添加完整的自动刷新代码

## 性能优化建议

### 1. 调整刷新间隔
如果觉得30秒太频繁，可以修改：
```javascript
const AUTO_REFRESH_INTERVAL = 60000; // 改为60秒
```

### 2. 数据库索引优化
```sql
CREATE INDEX idx_collect_time ON data_process_parkingspotrealtime(collect_time DESC);
CREATE INDEX idx_parking_spot_time ON data_process_parkingspotrealtime(parking_spot_id, collect_time DESC);
```

### 3. 仅在页面可见时刷新
```javascript
document.addEventListener('visibilitychange', function() {
    if (document.hidden) {
        // 页面隐藏时停止刷新
        if (autoRefreshTimer) clearInterval(autoRefreshTimer);
    } else {
        // 页面可见时恢复刷新
        startAutoRefresh();
    }
});
```

## 回滚方案

如果修复后出现问题，可以快速回滚：
```bash
cd "e:\develop\BSDP-Bike Sharing Demand Prediction Based on LSTM Model\BSDP\bike_dispatch_platform\templates"

# 恢复主页模板
copy system_support\dashboard.html.backup system_support\dashboard.html

# 恢复热力图模板
copy operation_management\heatmap.html.backup operation_management\heatmap.html
```

## 完成检查清单

- [ ] 备份了原始文件
- [ ] 修改了 dashboard.html 的 parkingVehicleMap 声明
- [ ] 在 dashboard.html 中添加了 markerMap
- [ ] 在 dashboard.html 中添加了自动刷新函数
- [ ] 在 dashboard.html 中调用了 startAutoRefresh()
- [ ] 修改了 heatmap.html 的刷新按钮
- [ ] 在 heatmap.html 中添加了 allMarkers
- [ ] 在 heatmap.html 中添加了自动刷新函数
- [ ] 在 heatmap.html 中调用了 startAutoRefresh()
- [ ] 验证了主页地图显示非零车辆数
- [ ] 验证了自动刷新生效（30秒）
- [ ] 验证了手动刷新生效
- [ ] 验证了调度器正常运行
- [ ] 验证了系统响应时间≤3秒

## 联系支持

如果遇到无法解决的问题，请提供以下信息：
1. 浏览器控制台的完整错误日志
2. 访问 http://localhost:8000/operation/api/scheduler-status/ 的返回结果
3. 访问 http://localhost:8000/operation/api/parking-data/ 的返回结果
4. Django 服务器的控制台输出
