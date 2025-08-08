#!/usr/bin/env python3
import os, sys, subprocess, time, pathlib
from datetime import datetime

ROOT = pathlib.Path(__file__).parent.resolve()
STEPS = [
    "scraper_app_store.py",
    "scraper_google_play.py",
    "clean_app_store.py",
    "clean_google_play.py",
    "calculate_metrics.py",
    "upload_to_supabase.py",
]

# Optional embeddings step
if os.getenv("EMBED_AFTER_INGEST", "").lower() in {"1","true","yes"}:
    STEPS.insert(-1, "embed.py")

def run(step: str):
    p = ROOT / step
    if not p.exists():
        raise SystemExit(f"[pipeline] missing step: {p}")
    print(f"[pipeline] ▶ {step}")
    start = time.time()
    subprocess.run([sys.executable, str(p)], check=True)
    print(f"[pipeline] ✓ {step} ({time.time()-start:.1f}s)")

def main():
    rid = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
    print(f"[pipeline] start run_id={rid}")
    for s in STEPS:
        run(s)
    print("[pipeline] success")

if __name__ == "__main__":
    sys.exit(main())
