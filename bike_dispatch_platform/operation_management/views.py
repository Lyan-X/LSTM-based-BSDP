from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.utils import timezone
import random
from .models import Vehicle, ScheduleTask, ScheduleEvaluation
from data_process.models import BikeRideData
from pyecharts import options as opts
from pyecharts.charts import HeatMap
from pyecharts.globals import ThemeType


@login_required
def vehicle_monitor(request):
    """车辆状态实时监控（任务书核心功能）"""
    vehicles = Vehicle.objects.all()
    return render(request, 'operation_management/vehicle_monitor.html', {'vehicles': vehicles})


@login_required
def create_schedule_task(request):
    """调度任务生成与分配（基于预测结果）"""
    if request.method == 'POST':
        target_region = request.POST.get('target_region')
        demand_count = int(request.POST.get('demand_count'))
        assign_to_id = request.POST.get('assign_to')

        # 生成唯一任务编号
        task_id = f"SCHED_{timezone.now().strftime('%Y%m%d%H%M%S')}"
        ScheduleTask.objects.create(
            task_id=task_id,
            target_region=target_region,
            demand_count=demand_count,
            assign_to_id=assign_to_id
        )
        messages.success(request, f"调度任务{task_id}创建成功")
        return redirect('operation_management:task_list')

    # 获取运维人员（多角色权限控制）
    operators = User.objects.filter(groups__name='运维人员')
    return render(request, 'operation_management/task_create.html', {'operators': operators})


@login_required
def supply_demand_heatmap(request):
    """供需热力图动态展示（任务书核心功能）"""
    # 从数据仓库统计各区域-时段需求
    region_period_demand = BikeRideData.objects.filter(status='cleaned').values(
        'start_point', 'ride_datetime__hour'
    ).annotate(demand=models.Count('id')).values_list('start_point', 'ride_datetime__hour', 'demand')

    # 构建热力图数据
    heatmap_data = []
    regions = list(set([item[0] for item in region_period_demand]))
    for region, hour, demand in region_period_demand:
        heatmap_data.append([region, hour, demand + random.randint(3, 10)])  # 模拟动态数据

    # 生成热力图（ECharts嵌入）
    c = (
        HeatMap(init_opts=opts.InitOpts(theme=ThemeType.LIGHT, width="100%", height="600px"))
        .add_xaxis(regions)
        .add_yaxis("骑行需求（辆）", list(range(24)), heatmap_data)
        .set_global_opts(
            title_opts=opts.TitleOpts(title="共享单车供需热力图（小时级动态）"),
            visualmap_opts=opts.VisualMapOpts(max_=100),
            xaxis_opts=opts.AxisOpts(axislabel_opts=opts.LabelOpts(rotate=-45)),
        )
    )
    heatmap_html = c.render_embed()

    return render(request, 'operation_management/heatmap.html', {'heatmap_html': heatmap_html})