from __future__ import annotations

import argparse
import json

from bike_dispatch_platform.demand_prediction.services.state_classifier_support import normalize_scheme_key, resolve_model_selection
from bike_dispatch_platform.demand_prediction.services.state_classifier_training_support import train_state_classifier_for_scheme


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Train a parallel T+1 state-classifier model for a selected scheme.")
    parser.add_argument(
        "--scheme",
        default=None,
        help="State scheme key to train, such as state_5 / state_7 / state_9 / state_11. Defaults to active_state_scheme_key.",
    )
    parser.add_argument("--epochs", type=int, default=20, help="Maximum training epochs.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    selection = resolve_model_selection()
    scheme_key = normalize_scheme_key(args.scheme or selection["active_state_scheme_key"])
    metrics_payload = train_state_classifier_for_scheme(scheme_key=scheme_key, epochs=args.epochs)
    print(json.dumps(metrics_payload, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
