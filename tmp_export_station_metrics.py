from pathlib import Path

import pandas as pd

from bike_dispatch_platform.demand_prediction.services.station_prediction_service import station_prediction_service
from bike_dispatch_platform.demand_prediction.views import _regression_metrics_for_station
from bike_dispatch_platform.operation_management.models import ParkingSpot


output_path = Path("station_metrics_62.xlsx")
batch = station_prediction_service.get_batch_response(force=False)
by_id = {s["station_id"]: s for s in batch["stations"]}
rows = []
for station in ParkingSpot.objects.filter(is_active=True).order_by("ysu_id"):
    s = by_id[station.ysu_id]
    m = _regression_metrics_for_station(station.ysu_id, 48)
    rows.append(
        {
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
            "MAE": m["mae"],
            "RMSE": m["rmse"],
            "R2": m["r2"],
            "误差评分准确度": m["error_score_accuracy"],
            "SMAPE": m["smape"],
            "回测样本数": m["sample_count"],
            "决策基准时刻": s["decision_basis_hour"],
            "模型别名": batch["model_alias"],
            "模型版本": batch["model_version"],
            "状态方案": s["t_plus_1_state_scheme_key"],
            "未来48小时净流量序列": ", ".join(str(x) for x in s["predictions"]),
            "未来48小时库存序列": ", ".join(str(x) for x in s["inventories"]),
        }
    )

df = pd.DataFrame(rows)
df.to_excel(output_path, index=False)
print(output_path.resolve())
print(df.head(3).to_string(index=False))
