#!/usr/bin/env python3
"""Run the knowledge-base ingest pipeline."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from caseware_kb.config import DATA_DIR  # noqa: E402
from caseware_kb.pipeline import run_ingest  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description="Build the Caseware knowledge base index")
    parser.add_argument(
        "--data",
        type=Path,
        default=DATA_DIR,
        help="Path to the data directory",
    )
    args = parser.parse_args()

    summary = run_ingest(args.data)
    print(json.dumps(summary, indent=2))

    if summary["warnings"]:
        print("\nWarnings:", file=sys.stderr)
        for warning in summary["warnings"]:
            print(f"  - {warning}", file=sys.stderr)


if __name__ == "__main__":
    main()
