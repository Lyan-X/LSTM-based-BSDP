from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description="Run repeated SRS compliance probes for long-duration stability testing.")
    parser.add_argument("--duration-hours", type=float, default=72.0, help="Total soak duration in hours.")
    parser.add_argument("--interval-seconds", type=int, default=300, help="Probe interval in seconds.")
    parser.add_argument(
        "--output",
        type=str,
        default="srs_soak_test_log.jsonl",
        help="JSONL output file in the project root.",
    )
    args = parser.parse_args()

    output_path = Path(args.output).resolve()
    deadline = datetime.now() + timedelta(hours=args.duration_hours)

    while datetime.now() < deadline:
        started_at = datetime.now()
        probe = subprocess.run(
            [sys.executable, "verify_srs_compliance.py"],
            capture_output=True,
            text=True,
            check=False,
        )
        record = {
            "started_at": started_at.isoformat(),
            "return_code": probe.returncode,
            "stdout": probe.stdout,
            "stderr": probe.stderr,
        }
        with output_path.open("a", encoding="utf-8") as fp:
            fp.write(json.dumps(record, ensure_ascii=False) + "\n")

        if probe.returncode != 0:
            break
        time.sleep(args.interval_seconds)


if __name__ == "__main__":
    main()
