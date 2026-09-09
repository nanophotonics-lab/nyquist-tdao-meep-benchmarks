#!/usr/bin/env python3
"""Run one isolated CPU-pinned TD forward+adjoint condition."""

from __future__ import annotations

import argparse
import contextlib
import os
import platform
import sys
from pathlib import Path

import MEEP_TD_runtime_after_source_benchmark as td


class Tee:
    def __init__(self, *streams):
        self.streams = streams

    def write(self, text):
        for stream in self.streams:
            stream.write(text)
            stream.flush()

    def flush(self):
        for stream in self.streams:
            stream.flush()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--sampling-interval", type=int, required=True)
    parser.add_argument("--termination", choices=("fixed", "moderate"), required=True)
    parser.add_argument("--repetition", type=int, required=True)
    parser.add_argument("--execution-order", type=int, required=True)
    parser.add_argument("--cpu", type=int, default=8)
    parser.add_argument("--log", type=Path, required=True)
    parser.add_argument("--gradient-output", type=Path, default=None)
    args = parser.parse_args()
    if args.sampling_interval < 1:
        parser.error("--sampling-interval must be >= 1")

    if hasattr(os, "sched_setaffinity"):
        os.sched_setaffinity(0, {args.cpu})
    affinity = sorted(os.sched_getaffinity(0)) if hasattr(os, "sched_getaffinity") else []
    args.log.parent.mkdir(parents=True, exist_ok=True)
    with args.log.open("w", encoding="utf-8") as stream:
        with contextlib.redirect_stdout(Tee(sys.stdout, stream)):
            print("TD_REPEAT_SUMMARY_BEGIN")
            row = td.run_td_once(
                after_sources_time=50.0,
                sampling_interval=args.sampling_interval,
                termination=args.termination,
                decay_by=1e-4,
                minimum_run_time=67.5,
                maximum_run_time=2000.0,
                decay_check_interval=10.0,
                gradient_output_path=args.gradient_output,
            )
            row.update({
                "repetition": args.repetition,
                "execution_order": args.execution_order,
                "cpu_affinity": " ".join(map(str, affinity)),
                "num_threads": os.environ.get("OMP_NUM_THREADS", "unset"),
                "machine_name": platform.node(),
                "python_version": platform.python_version(),
            })
            for key, value in row.items():
                print(f"{key.upper()} = {value}")
            print("TD_REPEAT_SUMMARY_END")


if __name__ == "__main__":
    main()
