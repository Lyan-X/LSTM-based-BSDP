// ==================== 热力图自动刷新功能 ====================
// 将此代码添加到 heatmap.html 的 <script> 标签中

// 配置项：自动刷新间隔（毫秒）
const AUTO_REFRESH_INTERVAL = 30000; // 30秒

// 全局变量
let autoRefreshTimer = null;
let isRefreshing = false;
let allMarkers = []; // 存储所有marker引用

// 修改原有代码：将 parkingSpotsData 改为全局变量
// 原代码：let parkingSpotsData = {{ parking_spots|safe }};
// 新代码：window.parkingSpotsData = {{ parking_spots|safe }};

// ==================== 核心刷新函数 ====================

/**
 * 刷新热力图数据
 */
function refreshHeatmapData() {
    if (isRefreshing) {
        console.log('[自动刷新] 正在刷新中，跳过本次请求');
        return;
    }
    
    isRefreshing = true;
    console.log('[自动刷新] 开始刷新热力图数据...');
    
    // 方法1：重新加载页面数据（简单但会闪烁）
    // location.reload();
    
    // 方法2：AJAX更新（推荐，无闪烁）
    fetch('/operation/api/parking-data/')
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                // 构建新的停车点数据映射
                const newDataMap = {};
                data.data.forEach(spot => {
                    newDataMap[spot.name] = {
                        name: spot.name,
                        lat: spot.lat,
                        lng: spot.lng,
                        supply: spot.count || 0,
                        demand: spot.count || 0, // 如果API返回demand字段，使用spot.demand
                        gap: 0 // 需要重新计算或从API获取
                    };
                });
                
                // 更新全局数据
                window.parkingSpotsData = Object.values(newDataMap);
                
                // 更新所有marker的弹窗和图标
                allMarkers.forEach(marker => {
                    const spotName = marker.spotName;
                    const newData = newDataMap[spotName];
                    
                    if (newData) {
                        const supply = newData.supply;
                        const demand = newData.demand;
                        const gap = demand - supply;
                        
                        // 更新marker图标颜色
                        const markerColor = gapColor(gap);
                        marker.setIcon(createGapIcon(gap, false));
                        
                        // 更新管辖范围颜色
                        if (marker.radiusCircle) {
                            marker.radiusCircle.setStyle({
                                color: markerColor,
                                fillColor: markerColor,
                                fillOpacity: 0.15,
                                weight: 1
                            });
                        }
                        
                        // 更新弹窗内容
                        const gapLabel = gap >= 20 ? '严重短缺' : gap >= 10 ? '中度短缺' : gap > -10 ? '基本均衡' : gap > -20 ? '中度过剩' : '严重过剩';
                        const updateTime = data.current_time || new Date().toLocaleString('zh-CN');
                        
                        marker.setPopupContent(`
                            <div class="popup-card">
                                <h5>${spotName}</h5>
                                <p>当前可用车辆：<strong>${supply}</strong> 辆</p>
                                <p>30分钟预测需求：<strong>${demand}</strong> 辆</p>
                                <p>供需缺口：<strong style="color:${markerColor}">${gap > 0 ? '+' : ''}${gap}</strong> (${gapLabel})</p>
                                <p style="font-size:12px;color:#888">更新时间：${updateTime}</p>
                            </div>
                        `);
                    }
                });
                
                // 更新统计数据
                updateStatistics();
                
                console.log('[自动刷新] 热力图数据刷新成功，更新时间：' + (data.current_time || new Date().toLocaleString()));
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
 * 更新统计数据
 */
function updateStatistics() {
    let shortageCount = 0;
    let surplusCount = 0;
    
    window.parkingSpotsData.forEach(spot => {
        const gap = spot.gap || 0;
        if (gap >= 10) shortageCount++;
        if (gap <= -10) surplusCount++;
    });
    
    // 更新页面显示
    const shortageEl = document.querySelector('.text-danger');
    const surplusEl = document.querySelector('.text-success');
    
    if (shortageEl) shortageEl.textContent = shortageCount;
    if (surplusEl) surplusEl.textContent = surplusCount;
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
    autoRefreshTimer = setInterval(refreshHeatmapData, AUTO_REFRESH_INTERVAL);
    console.log(`[自动刷新] 已启动，间隔：${AUTO_REFRESH_INTERVAL / 1000}秒`);
}

/**
 * 手动刷新（重置定时器）
 */
function manualRefresh() {
    console.log('[手动刷新] 触发');
    
    // 显示加载状态
    const refreshBtn = document.getElementById('refreshBtn');
    if (refreshBtn) {
        refreshBtn.innerHTML = '<span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span> 刷新中...';
        refreshBtn.disabled = true;
    }
    
    refreshHeatmapData();
    
    // 恢复按钮状态
    setTimeout(() => {
        if (refreshBtn) {
            refreshBtn.innerHTML = '<i class="bi bi-arrow-clockwise"></i> 刷新数据';
            refreshBtn.disabled = false;
        }
    }, 1000);
    
    // 重置自动刷新计时器
    startAutoRefresh();
}

// ==================== 辅助函数 ====================

/**
 * 根据供需缺口返回颜色
 */
function gapColor(gap) {
    if (gap >= 20) return '#dc2626';      // 严重短缺
    if (gap >= 10) return '#f97316';      // 中度短缺
    if (gap > -10) return '#eab308';      // 基本均衡
    if (gap > -20) return '#22c55e';      // 中度过剩
    return '#15803d';                      // 严重过剩
}

/**
 * 创建缺口图标
 */
function createGapIcon(gap, isSelected) {
    const bg = isSelected ? '#FF5722' : gapColor(gap);
    return L.divIcon({
        className: 'parking-icon',
        html: '<div style="width:28px;height:28px;border-radius:50%;background:' + bg + ';color:#fff;display:flex;align-items:center;justify-content:center;border:2px solid #fff;font-size:11px;font-weight:bold;box-shadow:0 2px 6px rgba(0,0,0,0.3)">' + (gap > 0 ? '+' + gap : gap) + '</div>',
        iconSize: [28, 28],
        iconAnchor: [14, 14]
    });
}

// ==================== 初始化 ====================
// 在渲染marker时保存引用：
// marker.spotName = point.name;
// allMarkers.push(marker);

// 修改刷新按钮的onclick事件：
// 原代码：<button id="refreshBtn" class="btn btn-secondary w-100 btn-sm" onclick="location.reload()">
// 新代码：<button id="refreshBtn" class="btn btn-secondary w-100 btn-sm" onclick="manualRefresh()">

// 在 window.onload 或 initMap() 最后调用：
// startAutoRefresh();

// ==================== 使用说明 ====================
// 1. 将上述代码添加到 heatmap.html 的 <script> 标签中
// 2. 修改刷新按钮的 onclick 从 location.reload() 改为 manualRefresh()
// 3. 在渲染marker时添加：
//    marker.spotName = point.name;
//    allMarkers.push(marker);
// 4. 在 initMap() 或 window.onload 最后调用 startAutoRefresh();
