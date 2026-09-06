#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
import time
import json
import csv
from datetime import datetime, timezone
from typing import Any, Dict, Optional

# =========================================================
# PATHS (đúng theo bạn chốt)
# =========================================================
CODE_DIR = os.path.dirname(os.path.abspath(__file__))      # .../12A09/mqtt-code
PROJECT_ROOT = os.path.dirname(CODE_DIR)                   # .../12A09

JSONL_PATH = os.path.join(PROJECT_ROOT, "mqtt-data", "raw", "telemetry.jsonl")
CSV_PATH   = os.path.join(PROJECT_ROOT, "mqtt-data", "raw", "telecsv.csv")

FIELDS = ["ts", "level", "level_rate"]
REQUIRED = ["level", "level_rate"]

def _now_ts() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

def _iso_from_ts_ms(ts_ms: Any) -> Optional[str]:
    try:
        ms = float(ts_ms)
        if ms < 1e12:
            return None
        dt = datetime.fromtimestamp(ms / 1000.0, tz=timezone.utc).astimezone()
        return dt.strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        return None

def _flatten_payload(data: Dict[str, Any]) -> Dict[str, Any]:
    metrics = data.get("metrics")
    if isinstance(metrics, dict):
        merged = dict(data)
        merged.update(metrics)
        return merged
    return data

def append_row(csv_path: str, row: Dict[str, Any]) -> None:
    os.makedirs(os.path.dirname(csv_path), exist_ok=True)
    file_exists = os.path.exists(csv_path)
    with open(csv_path, "a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        if not file_exists:
            w.writeheader()
        w.writerow(row)
        f.flush()
        os.fsync(f.fileno())

def parse_line_to_row(line: str) -> Dict[str, Any]:
    obj = json.loads(line)
    if not isinstance(obj, dict):
        raise ValueError("JSON must be an object")

    obj = _flatten_payload(obj)

    ts = obj.get("ts")
    if ts:
        ts_str = str(ts)
    else:
        ts_str = _iso_from_ts_ms(obj.get("ts_ms")) or _now_ts()

    missing = [k for k in REQUIRED if k not in obj]
    if missing:
        raise ValueError(f"Missing field(s): {missing}")

    return {
        "ts": ts_str,
        "level": float(obj["level"]),
        "level_rate": float(obj["level_rate"]),
    }

def follow_file(path: str, start_at_end: bool = True, sleep_s: float = 0.2) -> None:
    """
    Theo dõi file giống tail -f.
    - start_at_end=True: chỉ xử lý dữ liệu mới từ lúc chạy.
    - start_at_end=False: chạy từ đầu file rồi theo dõi tiếp.
    """
    while not os.path.exists(path):
        print(f"[WAIT] {path} not found yet... (waiting)", file=sys.stderr)
        time.sleep(1)

    with open(path, "r", encoding="utf-8") as f:
        if start_at_end:
            f.seek(0, os.SEEK_END)

        print(f"[FOLLOW] {path}")
        while True:
            pos = f.tell()
            line = f.readline()

            if not line:
                time.sleep(sleep_s)
                continue

            line = line.strip()
            if not line:
                continue

            try:
                row = parse_line_to_row(line)
                append_row(CSV_PATH, row)
                print(f"[OK] {row}")
            except json.JSONDecodeError:
                # thường xảy ra nếu đọc trúng lúc line đang ghi dở -> quay lại đọc lại
                f.seek(pos)
                time.sleep(0.05)
            except Exception as e:
                print(f"[ERR] {e} | line={line[:120]!r}", file=sys.stderr)

def main():
    # RESET_CSV=1 nếu muốn xóa file csv cũ mỗi lần chạy
    if os.getenv("RESET_CSV", "0") == "1" and os.path.exists(CSV_PATH):
        os.remove(CSV_PATH)

    # START_FROM_BEGIN=1 nếu muốn convert từ đầu file rồi mới follow
    start_at_end = (os.getenv("START_FROM_BEGIN", "0") != "1")

    print(f"[IN ] {JSONL_PATH}")
    print(f"[OUT] {CSV_PATH}")
    follow_file(JSONL_PATH, start_at_end=start_at_end)

if __name__ == "__main__":
    main()
