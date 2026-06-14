from pathlib import Path

import pandas as pd
from django.utils import timezone

from bike_dispatch_platform.demand_prediction.models import StationPrediction
from bike_dispatch_platform.demand_prediction.services.station_prediction_service import station_prediction_service
from bike_dispatch_platform.operation_management.models import ParkingSpot


output_path = Path("station_metrics_62_defense.xlsx")
batch = station_prediction_service.get_batch_response(force=False)
by_id = {s["station_id"]: s for s in batch["stations"]}
export_time = timezone.now()
rows = []
for station in ParkingSpot.objects.filter(is_active=True).order_by("ysu_id"):
    s = by_id[station.ysu_id]
    first_prediction = StationPrediction.objects.filter(
        station=station,
        batch_time=batch["batch_time"],
    ).order_by("prediction_hour").first()
    rows.append(
        {
            "站点编号": s["station_id"],
            "站点名称": s["station_name"],
            "预测批次时间": batch["batch_time"],
            "T+1目标时刻": s["timestamps"][0] if s.get("timestamps") else "",
            "T+1净流量预测": s["t_plus_1_prediction"],
            "T+1库存预测": s["t_plus_1_inventory"],
            "T+1供需缺口": s["t_plus_1_gap"],
            "T+1状态": s["t_plus_1_state_label"],
            "T+1状态区间": s["t_plus_1_state_range"],
            "未来48小时峰值需求": s["summary"]["peak_abs_demand"],
            "未来48小时总绝对需求": s["summary"]["total_abs_demand"],
            "预测记录写入时间": first_prediction.created_at.isoformat() if first_prediction else "",
            "导出生成时间": export_time.isoformat(),
        }
    )

df = pd.DataFrame(rows)
summary_df = pd.DataFrame(
    [
        {"字段": "预测批次时间", "说明": "这一整批62个站点预测结果所属的统一批次时刻。"},
        {"字段": "T+1目标时刻", "说明": "当前批次下第一个预测点对应的时刻，也是T+1展示的核心时刻。"},
        {"字段": "T+1净流量预测", "说明": "该站点在T+1时刻预测的净流入/净流出变化值。"},
        {"字段": "T+1库存预测", "说明": "该站点在T+1时刻预测的库存数量。"},
        {"字段": "T+1供需缺口", "说明": "根据T+1预测库存得到的供需缺口。"},
        {"字段": "T+1状态", "说明": "系统根据阈值划分得到的站点供需状态标签。"},
        {"字段": "T+1状态区间", "说明": "该状态对应的库存区间解释。"},
        {"字段": "未来48小时峰值需求", "说明": "未来48小时内该站点需求波动的峰值强度。"},
        {"字段": "未来48小时总绝对需求", "说明": "未来48小时内需求波动总量，用于衡量站点活跃程度。"},
        {"字段": "预测记录写入时间", "说明": "这条预测结果写入数据库的时间。"},
        {"字段": "导出生成时间", "说明": "本次答辩版Excel导出的生成时间。"},
    ]
)
with pd.ExcelWriter(output_path, engine="openpyxl") as writer:
    df.to_excel(writer, index=False, sheet_name="62站点精简答辩版")
    summary_df.to_excel(writer, index=False, sheet_name="字段说明")

print(output_path.resolve())
print(df.head(5).to_string(index=False))
