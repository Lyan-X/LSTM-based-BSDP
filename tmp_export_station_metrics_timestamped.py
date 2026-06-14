from pathlib import Path

import pandas as pd
from django.utils import timezone

from bike_dispatch_platform.demand_prediction.models import StationPrediction
from bike_dispatch_platform.demand_prediction.services.station_prediction_service import station_prediction_service
from bike_dispatch_platform.operation_management.models import ParkingSpot


output_path = Path("station_metrics_62_timestamped.xlsx")
batch = station_prediction_service.generate_predictions(force=False)
runtime_summary = station_prediction_service.model_runtime_summary()
by_id = batch.station_payloads

latest_created_at = (
    StationPrediction.objects.filter(batch_time=batch.batch_time.to_pydatetime())
    .order_by("-created_at")
    .values_list("created_at", flat=True)
    .first()
)

rows = []
for station in ParkingSpot.objects.filter(is_active=True).order_by("ysu_id"):
    s = by_id[station.ysu_id]
    timestamps = s.get("timestamps", [])
    rows.append(
        {
            "导出生成时间": timezone.now().strftime("%Y-%m-%d %H:%M:%S"),
            "预测批次时间batch_time": batch.batch_time.strftime("%Y-%m-%d %H:%M:%S"),
            "预测记录写入时间created_at": latest_created_at.strftime("%Y-%m-%d %H:%M:%S") if latest_created_at else "",
            "决策基准时刻decision_basis_hour": pd.Timestamp(s.get("decision_basis_hour")).strftime("%Y-%m-%d %H:%M:%S") if s.get("decision_basis_hour") else "",
            "T+1目标时刻": pd.Timestamp(timestamps[0]).strftime("%Y-%m-%d %H:%M:%S") if timestamps else "",
            "预测序列结束时刻": pd.Timestamp(timestamps[-1]).strftime("%Y-%m-%d %H:%M:%S") if timestamps else "",
            "模型别名": runtime_summary.get("active_alias", ""),
            "模型说明": runtime_summary.get("active_description", ""),
            "模型版本": batch.model_version,
            "状态划分方案": s.get("t_plus_1_state_scheme_key", ""),
            "站点编号": s["station_id"],
            "站点名称": s["station_name"],
            "T+1净流量预测": s["t_plus_1_prediction"],
            "T+1库存预测": s["t_plus_1_inventory"],
            "T+1供需缺口": s["t_plus_1_gap"],
            "T+1状态标签": s["t_plus_1_state_label"],
            "T+1状态区间": s["t_plus_1_state_range"],
            "T+1状态代表值": s["t_plus_1_state_midpoint"],
            "未来48小时总绝对需求": s["summary"]["total_abs_demand"],
            "未来48小时峰值需求": s["summary"]["peak_abs_demand"],
            "未来48小时净流量序列": ", ".join(str(x) for x in s["predictions"]),
            "未来48小时库存序列": ", ".join(str(x) for x in s["inventories"]),
        }
    )

df = pd.DataFrame(rows)
with pd.ExcelWriter(output_path, engine="openpyxl") as writer:
    df.to_excel(writer, sheet_name="62站点逐站指标", index=False)
    desc = pd.DataFrame(
        [
            {"字段": "导出生成时间", "说明": "本次导出文件生成的实际时间"},
            {"字段": "预测批次时间batch_time", "说明": "系统本轮预测所属批次时间，通常按整点生成"},
            {"字段": "预测记录写入时间created_at", "说明": "预测结果写入数据库的时间"},
            {"字段": "决策基准时刻decision_basis_hour", "说明": "当前调度建议和T+1状态判断使用的基准时刻"},
            {"字段": "T+1目标时刻", "说明": "未来第1个预测点对应的具体时刻"},
            {"字段": "预测序列结束时刻", "说明": "未来48小时预测序列的最后一个时刻"},
            {"字段": "T+1净流量预测", "说明": "未来第1小时的净流量预测值"},
            {"字段": "T+1库存预测", "说明": "未来第1小时的库存预测值"},
            {"字段": "T+1供需缺口", "说明": "未来第1小时的供需缺口"},
        ]
    )
    desc.to_excel(writer, sheet_name="时间字段说明", index=False)

print(output_path.resolve())
print(df[['站点编号','站点名称','预测批次时间batch_time','T+1目标时刻','预测序列结束时刻']].head(5).to_string(index=False))
