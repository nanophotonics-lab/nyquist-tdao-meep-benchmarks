#!/usr/bin/env python3
"""Resumable CPU-pinned forward-only sweep with median/IQR aggregation."""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import os
import re
import subprocess
import sys
from pathlib import Path

import numpy as np

from run_repeated_sweep import NF_VALUES, parse_value, schedule, write_csv


SUMMARY_RE = re.compile(
    r"FORWARD_ONLY_SUMMARY_BEGIN\s*(.*?)\s*FORWARD_ONLY_SUMMARY_END", re.DOTALL
)


def parse_log(path):
    matches = SUMMARY_RE.findall(path.read_text(encoding="utf-8", errors="replace"))
    if len(matches) != 1:
        return None
    row = {"LOG_FILE": str(path)}
    for line in matches[0].splitlines():
        if "=" in line:
            key, value = line.split("=", 1)
            row[key.strip()] = parse_value(value.strip())
    row["LOG_MTIME_UTC"] = dt.datetime.fromtimestamp(
        path.stat().st_mtime, tz=dt.timezone.utc
    ).isoformat()
    return row


def collect_rows(log_root):
    rows = [row for path in sorted(log_root.glob("*/*.log")) if (row := parse_log(path))]
    rows.sort(key=lambda row: row["LOG_MTIME_UTC"])
    for index, row in enumerate(rows, 1):
        row["ACTUAL_COMPLETION_ORDER"] = index
    return rows


def summarize(rows):
    metrics = (
        "RUNTIME_SECONDS", "TIME_PER_STEP_MS", "STEPS", "MEEP_TIME",
        "INCIDENT_RUNTIME_SECONDS", "EVAL_TOTAL_SECONDS", "OBJECTIVE", "PEAK_RSS_MB",
    )
    output = []
    terminations = tuple(dict.fromkeys(
        row.get("TERMINATION") for row in rows if row.get("TERMINATION")
    ))
    for termination in terminations:
        for n_f in NF_VALUES:
            group = [
                row for row in rows
                if row.get("TERMINATION") == termination and int(row.get("N_F", -1)) == n_f
            ]
            if not group:
                continue
            valid = [row for row in group if not bool(row["CAP_HIT"])]
            summary = {
                "termination": termination,
                "N_f": n_f,
                "repetitions": len(group),
                "valid_repetitions": len(valid),
                "cap_hits": sum(bool(row["CAP_HIT"]) for row in group),
                "cpu_affinity": group[0]["CPU_AFFINITY"],
            }
            for metric in metrics:
                values = np.asarray([float(row[metric]) for row in valid])
                q1, q3 = np.percentile(values, [25, 75])
                prefix = metric.lower()
                summary.update({
                    f"{prefix}_median": float(np.median(values)),
                    f"{prefix}_q1": float(q1),
                    f"{prefix}_q3": float(q3),
                    f"{prefix}_min": float(np.min(values)),
                    f"{prefix}_max": float(np.max(values)),
                })
            output.append(summary)
    return output


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--repetitions", type=int, default=5)
    parser.add_argument("--seed", type=int, default=20260805)
    parser.add_argument("--cpu", type=int, default=8)
    parser.add_argument("--output-root", type=Path, default=Path("forward_only_sweep"))
    parser.add_argument(
        "--termination", choices=("fixed", "moderate", "common_field_decay"),
        default=None,
    )
    parser.add_argument("--skip-warmup", action="store_true")
    args = parser.parse_args()
    root = args.output_root
    runner = Path(__file__).resolve().with_name("run_forward_only_benchmark.py")
    env = os.environ.copy()
    for name in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS"):
        env[name] = "1"

    rows = collect_rows(root / "logs")
    if not rows and not args.skip_warmup:
        warmup_termination = args.termination or "fixed"
        warmup = root / "warmup" / f"Nf002_{warmup_termination}.log"
        command = [sys.executable, str(runner), "--Nf", "2", "--repetition", "0",
                   "--execution-order", "0", "--termination", warmup_termination, "--cpu", str(args.cpu),
                   "--log", str(warmup)]
        print(f"WARMUP Nf=2 {warmup_termination}")
        subprocess.run(command, check=True, env=env)

    completed = {(str(r["TERMINATION"]), int(r["N_F"]), int(r["REPETITION"])) for r in rows}
    tasks = schedule(args.repetitions, args.seed)
    if args.termination:
        tasks = [
            (order, repetition, n_f, args.termination)
            for order, repetition, n_f, original_termination in tasks
            if original_termination == "fixed"
        ]
    for order, repetition, n_f, termination in tasks:
        key = (termination, n_f, repetition)
        if key in completed:
            print(f"SKIP completed: {key}")
            continue
        log = root / "logs" / termination / f"Nf{n_f:03d}_rep{repetition:02d}.log"
        command = [sys.executable, str(runner), "--Nf", str(n_f),
                   "--repetition", str(repetition), "--execution-order", str(order),
                   "--termination", termination, "--cpu", str(args.cpu), "--log", str(log)]
        print(f"RUN order={order} rep={repetition} Nf={n_f} termination={termination}")
        subprocess.run(command, check=True, env=env)
        rows = collect_rows(root / "logs")
        write_csv(root / "data" / "forward_only_raw.csv", rows)
        write_csv(root / "data" / "forward_only_median_iqr.csv", summarize(rows))
        print(f"UPDATED: {len(rows)} forward runs")


if __name__ == "__main__":
    main()
