#!/usr/bin/env python3
"""
Quick recording test: records ~5 seconds using default device (-1),
stops gracefully, and reports transcript/summary locations.

Note: Summarization may fail in restricted network environments;
the transcript should still be created in the working directory.
"""

import time
import sys
from pathlib import Path

from meeting_service import MeetingService
from config import Config


def main():
    svc = MeetingService()

    errors = Config.validate_paths()
    if errors:
        print("Configuration errors:")
        for e in errors:
            print(f"  - {e}")
        sys.exit(1)

    meeting_name = "quick_test"
    device_id = -1  # system default
    prompt_type = "meeting"

    print("Starting 5-second quick recording test...")
    meeting_id = svc.start_recording(meeting_name, device_id, prompt_type)

    # Peek at internal record for filenames (for test visibility)
    rec = svc.active_recordings.get(meeting_id, {})
    transcript_filename = rec.get("transcript_filename")
    summary_filename = rec.get("summary_filename")
    if transcript_filename:
        print(f"Transcript (working dir): {Path(transcript_filename).resolve()}")
    if summary_filename:
        print(f"Summary (working dir):    {Path(summary_filename).resolve()}")

    time.sleep(5)
    print("\nStopping recording...")
    svc.stop_recording(meeting_id)

    # Wait for processing to finish (or fail)
    deadline = time.time() + 120
    last_status = None
    while time.time() < deadline:
        status = svc.get_meeting_status(meeting_id)
        if status and status != last_status:
            print(f"Status: {status}")
            last_status = status
        if status in ("complete", "error"):
            break
        time.sleep(1)

    final = svc.get_meeting_status(meeting_id)
    print(f"Final status: {final}")

    # After move, files should be under calls output path
    calls = Config.CALLS_OUTPUT_PATH
    if calls.exists():
        print(f"Calls output directory: {calls}")
        # List newest txt files for quick inspection
        txts = sorted(calls.glob("*.txt"), key=lambda p: p.stat().st_mtime, reverse=True)[:5]
        for p in txts:
            print(f" - {p.name} ({p.stat().st_size} bytes)")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nInterrupted.")
        sys.exit(130)

