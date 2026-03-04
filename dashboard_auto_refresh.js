// ==================== 主页地图自动刷新功能 ====================
// 将此代码添加到 dashboard.html 的 <script> 标签中

// 配置项：自动刷新间隔（毫秒）
const AUTO_REFRESH_INTERVAL = 30000; // 30秒

// 全局变量
let autoRefreshTimer = null;
let isRefreshing = false;
let markerMap = new Map(); // 存储所有marker引用

// 修改原有代码：将 const parkingVehicleMap 改为 let
// 原代码：const parkingVehicleMap = {{ stats.parking_vehicle_map|safe }};
// 新代码：let parkingVehicleMap = {{ stats.parking_vehicle_map|safe }};

// 在渲染停车点时，保存marker引用到markerMap
// 在 PARKING_POINTS.forEach(point => { ... }) 循环中添加：
// marker.spotName = point.name;
// marker.spotLat = point.lat;
// marker.spotLng = point.lng;
// markerMap.set(point.name, marker);

// ==================== 核心刷新函数 ====================

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

// ==================== 初始化 ====================
// 在页面加载完成后启动自动刷新
// 在 DOMContentLoaded 事件处理函数的最后添加：
// startAutoRefresh();

// ==================== 使用说明 ====================
// 1. 将上述代码添加到 dashboard.html 的 <script> 标签中
// 2. 修改 const parkingVehicleMap 为 let parkingVehicleMap
// 3. 在渲染marker时添加：
//    marker.spotName = point.name;
//    marker.spotLat = point.lat;
//    marker.spotLng = point.lng;
//    markerMap.set(point.name, marker);
// 4. 在 DOMContentLoaded 最后调用 startAutoRefresh();
