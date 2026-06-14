from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from bike_dispatch_platform.demand_prediction.services.state_classifier_support import (
    STATE_SCHEME_EXPLORATION_PATH,
    STATE_SCHEME_ORDER,
    normalize_scheme_key,
    save_model_selection,
)
from bike_dispatch_platform.demand_prediction.services.state_classifier_training_support import (
    choose_recommended_scheme,
    render_exploration_markdown,
    train_state_classifier_for_scheme,
)


ROOT_DIR = Path(__file__).resolve().parent
REPORT_PATH = ROOT_DIR / "状态划分探索报告.md"


def main() -> None:
    results = []
    for scheme_key in STATE_SCHEME_ORDER:
        results.append(train_state_classifier_for_scheme(normalize_scheme_key(scheme_key)))

    recommended = choose_recommended_scheme(results)
    payload = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "results": results,
        "recommended_scheme_key": recommended["scheme_key"],
        "recommended_summary": {
            "class_count": recommended["class_count"],
            "classification_accuracy": recommended["test_metrics"]["classification_accuracy"],
            "macro_f1": recommended["test_metrics"]["macro_f1"],
            "weighted_f1": recommended["test_metrics"]["weighted_f1"],
        },
    }
    STATE_SCHEME_EXPLORATION_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    REPORT_PATH.write_text(render_exploration_markdown(results, recommended), encoding="utf-8")
    save_model_selection(
        {
            "active_model_alias": "production",
            "active_state_scheme_key": recommended["scheme_key"],
            "recommended_state_scheme_key": recommended["scheme_key"],
        }
    )
    print(json.dumps(payload, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
