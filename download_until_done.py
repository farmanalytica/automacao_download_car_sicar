#!/usr/bin/env python3
"""Download every SICAR state x polygon zip, looping until the set is complete.

Runs download passes over all 27 states x all 9 polygon types (243 zips into
per-layer subdirs of ``source/``, same layout as downloader.py). Each pass
only attempts what is still missing or corrupt, so the script is fully
resumable — kill it at any time and rerun. Zips from the old flat ``source/``
layout are moved into the subdirs automatically on startup.

Strategy:
  - a zip counts as done only if it passes ``zipfile.is_zipfile`` (truncated
    downloads are deleted and retried);
  - short pause after each download, longer pause after a failure;
  - after several consecutive failures the SICAR session is rebuilt and the
    script cools down for a few minutes (server throttling / CAPTCHA streaks);
  - between passes, exponential backoff that resets whenever a pass makes
    progress;
  - loops forever until nothing is missing (or ``--max-passes`` is hit).

Usage:
    python download_until_done.py                 # run until complete
    python download_until_done.py --max-passes 10
"""

from __future__ import annotations

import argparse
import os
import shutil
import sys
import time
import zipfile
from collections import deque
from pathlib import Path

from SICAR import Sicar, Polygon

TAG = "until-done"


def log(tag: str, message: str, *, err: bool = False) -> None:
    """Print "[tag] message", routed to stderr when err=True."""
    print(f"[{tag}] {message}", file=sys.stderr if err else sys.stdout, flush=True)

OUTPUT_DIR = Path("source")

# Same per-layer directory layout as downloader.py
OVERLAY_DIRS = {
    Polygon.AREA_PROPERTY: "area_overlay",
    Polygon.APPS: "app_overlay",
    Polygon.NATIVE_VEGETATION: "native_vegetation_overlay",
    Polygon.LEGAL_RESERVE: "legal_reserve_overlay",
    Polygon.CONSOLIDATED_AREA: "consolidated_area_overlay",
    Polygon.HYDROGRAPHY: "hydrography_overlay",
    Polygon.AREA_FALL: "fallow_overlay",
    Polygon.RESTRICTED_USE: "restricted_use_overlay",
    Polygon.ADMINISTRATIVE_SERVICE: "administrative_service_overlay",
}

PAUSE_AFTER_SUCCESS = 5  # seconds between downloads, be polite to gov server
PAUSE_AFTER_FAILURE = 15
CONSECUTIVE_FAILURES_LIMIT = 5  # then: rebuild session + cooldown
FAILURE_STREAK_COOLDOWN = 300
PASS_BACKOFF_BASE = 60  # between passes with zero progress: 60s, 120s, ... cap
PASS_BACKOFF_CAP = 900


def fmt_duration(seconds: float) -> str:
    seconds = int(seconds)
    h, rem = divmod(seconds, 3600)
    m, s = divmod(rem, 60)
    if h:
        return f"{h}h{m:02d}m"
    if m:
        return f"{m}m{s:02d}s"
    return f"{s}s"


class Progress:
    """Tracks completed downloads and estimates remaining time.

    ETA = remaining files x rolling average duration of the last completed
    downloads (pauses included). File sizes vary wildly between states, so
    the estimate is rough and stabilises as more files complete.
    """

    def __init__(self, total: int, already_done: int):
        self.total = total
        self.done = already_done
        self.durations: deque[float] = deque(maxlen=30)
        self.started = time.monotonic()

    def record(self, duration: float) -> None:
        self.done += 1
        self.durations.append(duration)

    def eta(self) -> str:
        if not self.durations:
            return "estimating..."
        avg = sum(self.durations) / len(self.durations)
        return fmt_duration(avg * (self.total - self.done))

    def line(self) -> str:
        pct = 100 * self.done / self.total
        return (
            f"[{self.done}/{self.total}] {pct:.1f}% done | "
            f"elapsed {fmt_duration(time.monotonic() - self.started)} | "
            f"ETA {self.eta()}"
        )


def ensure_tesseract() -> None:
    """Make the Tesseract binary reachable even if PATH is stale (Windows)."""
    if shutil.which("tesseract"):
        return
    default = Path(r"C:\Program Files\Tesseract-OCR")
    if (default / "tesseract.exe").exists():
        os.environ["PATH"] = str(default) + os.pathsep + os.environ["PATH"]
        log(TAG, f"Added {default} to PATH for this run")


def is_valid_zip(path: Path) -> bool:
    return path.exists() and zipfile.is_zipfile(path)


def target_path(state, polygon) -> Path:
    return OUTPUT_DIR / OVERLAY_DIRS[polygon] / f"{state.value}_{polygon.value}.zip"


def migrate_flat_layout(states, polygons) -> None:
    """Move zips from the old flat source/ layout into per-layer subdirs."""
    moved = 0
    for state in states:
        for polygon in polygons:
            old = OUTPUT_DIR / f"{state.value}_{polygon.value}.zip"
            new = target_path(state, polygon)
            if old.exists() and not new.exists():
                new.parent.mkdir(parents=True, exist_ok=True)
                old.rename(new)
                moved += 1
    if moved:
        log(TAG, f"Moved {moved} zips from flat {OUTPUT_DIR}/ into per-layer subdirs")


def connect() -> Sicar:
    """Build a SICAR session, retrying with backoff until it succeeds."""
    attempt = 0
    while True:
        attempt += 1
        try:
            car = Sicar()
            car.get_release_dates()  # probe the connection for real
            return car
        except Exception as e:
            wait = min(60 * attempt, 300)
            log(TAG, f"Connection attempt {attempt} failed: {e}. Retrying in {wait}s", err=True)
            time.sleep(wait)


def missing_targets(states, polygons) -> list:
    missing = []
    for state in states:
        for polygon in polygons:
            path = target_path(state, polygon)
            if not is_valid_zip(path):
                missing.append((state, polygon))
    return missing


def run_pass(car: Sicar, todo: list, progress: Progress) -> tuple[int, Sicar]:
    """Attempt every (state, polygon) in todo. Returns (downloads_ok, car).

    The session is rebuilt in place after too many consecutive failures.
    """
    ok = 0
    consecutive_failures = 0

    for state, polygon in todo:
        path = target_path(state, polygon)

        if path.exists() and not zipfile.is_zipfile(path):
            log(TAG, f"Removing corrupt/partial {path.name}")
            path.unlink()

        started = time.monotonic()
        try:
            log(TAG, f"Downloading {state.name} / {polygon.name}")
            car.download_state(state, polygon, folder=path.parent)
            if is_valid_zip(path):
                ok += 1
                consecutive_failures = 0
                time.sleep(PAUSE_AFTER_SUCCESS)
                progress.record(time.monotonic() - started)
                size_mb = path.stat().st_size / 1e6
                log(TAG, f"{path.name} OK ({size_mb:.1f} MB) — {progress.line()}")
            else:
                raise RuntimeError("download finished but zip is missing/invalid")
        except KeyboardInterrupt:
            raise
        except Exception as e:
            consecutive_failures += 1
            log(TAG, f"ERROR: {state.name} / {polygon.name}: {e}", err=True)

            if consecutive_failures >= CONSECUTIVE_FAILURES_LIMIT:
                log(
                    TAG,
                    f"{consecutive_failures} failures in a row — rebuilding session, "
                    f"cooling down {FAILURE_STREAK_COOLDOWN}s",
                    err=True,
                )
                time.sleep(FAILURE_STREAK_COOLDOWN)
                car = connect()
                consecutive_failures = 0
            else:
                time.sleep(PAUSE_AFTER_FAILURE)

    return ok, car


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--max-passes",
        type=int,
        default=0,
        help="stop after N passes even if incomplete (0 = loop until done)",
    )
    args = parser.parse_args()

    ensure_tesseract()
    for overlay in OVERLAY_DIRS.values():
        (OUTPUT_DIR / overlay).mkdir(parents=True, exist_ok=True)

    car = connect()
    states = list(car.get_release_dates().keys())
    polygons = list(Polygon)
    total = len(states) * len(polygons)

    migrate_flat_layout(states, polygons)

    pass_num = 0
    passes_without_progress = 0
    progress = Progress(total, total - len(missing_targets(states, polygons)))

    while True:
        pass_num += 1
        todo = missing_targets(states, polygons)

        if not todo:
            log(TAG, f"COMPLETE: all {total} zips present and valid in {OUTPUT_DIR}/")
            return 0

        log(TAG, f"Pass {pass_num}: {total - len(todo)}/{total} done, {len(todo)} to go")

        ok, car = run_pass(car, todo, progress)
        log(TAG, f"Pass {pass_num} finished: {ok}/{len(todo)} downloaded — {progress.line()}")

        if args.max_passes and pass_num >= args.max_passes:
            remaining = len(missing_targets(states, polygons))
            log(TAG, f"Stopping at --max-passes={args.max_passes}, {remaining} still missing", err=True)
            return 1 if remaining else 0

        if ok > 0:
            passes_without_progress = 0
        else:
            passes_without_progress += 1

        if missing_targets(states, polygons):
            wait = min(
                PASS_BACKOFF_BASE * (2 ** passes_without_progress), PASS_BACKOFF_CAP
            )
            log(TAG, f"Pausing {wait}s before next pass")
            time.sleep(wait)


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        log(TAG, "Interrupted — progress kept, rerun to resume", err=True)
        sys.exit(130)
