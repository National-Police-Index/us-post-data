"""
Usage:
    python -m pipeline.main
    python -m pipeline.main --states ga ca
"""
from __future__ import annotations

import argparse
import os


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

    from pipeline.orchestrate import Orchestrator

    Orchestrator(
        rclone_remote=os.environ.get(
            "RCLONE_REMOTE", "dropbox:post-db-test"
        ),
    ).run(states=args.states)


if __name__ == "__main__":
    main()
