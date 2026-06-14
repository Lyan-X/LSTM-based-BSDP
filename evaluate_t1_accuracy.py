from __future__ import annotations

import argparse
import json

from bike_dispatch_platform.demand_prediction.services.state_classifier_support import (
    classifier_artifact_paths,
    normalize_scheme_key,
    resolve_model_selection,
)
from bike_dispatch_platform.demand_prediction.services.state_classifier_training_support import (
    evaluate_production_state_baseline,
    evaluate_state_classifier_for_scheme,
    load_dataset,
    split_samples,
    station_frames,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Evaluate T+1 state-classification performance for a prediction alias.")
    parser.add_argument(
        "--alias",
        default="production",
        choices=["production", "t1_state_classifier"],
        help="Prediction alias to evaluate under the T+1 state-classification standard.",
    )
    parser.add_argument(
        "--scheme",
        default=None,
        help="State scheme key to evaluate, such as state_5 / state_7 / state_9 / state_11. Defaults to active_state_scheme_key.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    selection = resolve_model_selection()
    scheme_key = normalize_scheme_key(args.scheme or selection["active_state_scheme_key"])
    if args.alias == "t1_state_classifier":
        model_path, bundle_path, _, _ = classifier_artifact_paths(scheme_key)
        if not model_path.exists() or not bundle_path.exists():
            raise FileNotFoundError(f"Missing classifier assets for scheme {scheme_key}: {model_path.name} / {bundle_path.name}")
        result = evaluate_state_classifier_for_scheme(scheme_key)
    else:
        dataset = load_dataset()
        frames = station_frames(dataset)
        samples = split_samples(frames).test
        result = evaluate_production_state_baseline(frames, samples, scheme_key)
        result.update(
            {
                "alias": "production",
                "scheme_key": scheme_key,
                "class_count": selection["active_state_scheme"]["class_count"]
                if selection["active_state_scheme_key"] == scheme_key
                else int(scheme_key.split("_")[-1]),
            }
        )
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
