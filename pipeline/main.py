"""
Usage:
    python -m pipeline.main
    python -m pipeline.main --states ga ca
"""
from __future__ import annotations

import argparse
import logging
import os
from datetime import datetime


def _setup_logging(log_dir: str = "pipeline/logs") -> str:
    os.makedirs(log_dir, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    log_path = os.path.join(log_dir, f"pipeline-{ts}.log")

    fmt = logging.Formatter(
        "%(asctime)s %(levelname)-8s %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )
    root = logging.getLogger()
    root.setLevel(logging.DEBUG)

    fh = logging.FileHandler(log_path)
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(fmt)
    root.addHandler(fh)

    sh = logging.StreamHandler()
    sh.setLevel(logging.INFO)
    sh.setFormatter(fmt)
    root.addHandler(sh)

    return log_path


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Poll Dropbox for new POST data and run cleaning pipeline"
    )
    parser.add_argument(
        "--states",
        nargs="+",
        help="Lowercase state codes to poll (default: all)",
    )
    args = parser.parse_args()

    log_path = _setup_logging()
    logging.getLogger(__name__).info("Log file: %s", log_path)

    from pipeline.orchestrate import Orchestrator

    Orchestrator(
        rclone_remote=os.environ.get(
            "RCLONE_REMOTE", "dropbox:post-db-test"
        ),
    ).run(states=args.states)


if __name__ == "__main__":
    main()
