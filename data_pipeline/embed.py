#!/usr/bin/env python3
"""
Embeddings pipeline (OpenAI or Azure OpenAI)

Inputs (created earlier in the pipeline):
  - raw_apple_data.csv
  - raw_google_data.csv

Output (consumed by upload_to_supabase.py):
  - embedded_reviews.csv  (at repo root)

Env (standard OpenAI):
  OPENAI_API_KEY          (required)
  OPENAI_URL              (default: https://api.openai.com/v1)
  OPENAI_EMBED_MODEL      (default: text-embedding-3-small)

Env (Azure OpenAI):
  OPENAI_API_KEY          (required)
  OPENAI_URL              (e.g., https://<resource>.openai.azure.com)
  OPENAI_DEPLOYMENT       (deployment name for the embedding model)
  OPENAI_API_VERSION      (e.g., 2024-02-01)

Other:
  EMBED_BATCH_SIZE        (default: 100)
  EMBED_OUTPUT            (default: embedded_reviews.csv)
"""

import os, sys, json, time, logging, pathlib
from typing import List
import pandas as pd
import requests

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_URL = os.getenv("OPENAI_URL", "https://api.openai.com/v1").rstrip("/")
OPENAI_EMBED_MODEL = os.getenv("OPENAI_EMBED_MODEL", "text-embedding-3-small")
OPENAI_DEPLOYMENT = os.getenv("OPENAI_DEPLOYMENT")
OPENAI_API_VERSION = os.getenv("OPENAI_API_VERSION")
BATCH_SIZE = int(os.getenv("EMBED_BATCH_SIZE", "100"))
OUTPUT = pathlib.Path(os.getenv("EMBED_OUTPUT", "embedded_reviews.csv"))

ROOT = pathlib.Path(__file__).resolve().parent.parent  # repo root
APPLE_CSV = ROOT / "raw_apple_data.csv"
GOOGLE_CSV = ROOT / "raw_google_data.csv"

def require(cond, msg):
    if not cond:
        raise ValueError(msg)

def is_azure() -> bool:
    # If a deployment or api-version is provided, assume Azure. Otherwise detect azure.com in URL.
    return bool(OPENAI_DEPLOYMENT and OPENAI_API_VERSION) or ("azure.com" in OPENAI_URL)

def pick_col(df: pd.DataFrame, candidates: List[str]) -> str:
    for c in candidates:
        if c in df.columns:
            return c
    raise KeyError(f"None of the columns found: {candidates}  (have: {list(df.columns)[:20]})")

def load_reviews() -> pd.DataFrame:
    logging.info("Loading app store data...")
    frames = []
    if APPLE_CSV.exists():
        a = pd.read_csv(APPLE_CSV)
        a["platform"] = "apple"
        frames.append(a)
    if GOOGLE_CSV.exists():
        g = pd.read_csv(GOOGLE_CSV)
        g["platform"] = "google"
        frames.append(g)
    require(frames, f"No input CSVs found. Expected {APPLE_CSV.name} and/or {GOOGLE_CSV.name}")
    df = pd.concat(frames, ignore_index=True)

    # Pick text & id columns heuristically
    text_col = pick_col(df, ["review_text","content","text","body","review","comment"])
    id_col = pick_col(df, ["review_id","reviewId","id","guid","uuid"])
    df = df[[ "platform", id_col, text_col ]].rename(columns={id_col:"review_id", text_col:"review_text"})
    df["review_text"] = df["review_text"].astype(str).str.strip()
    df = df.dropna(subset=["review_text"])
    df = df[df["review_text"].str.len()>0].drop_duplicates(subset=["platform","review_id"])
    logging.info(f"Loaded {len(df):,} reviews after cleaning")
    return df

def _azure_embed(batch: List[str]) -> List[List[float]]:
    require(OPENAI_DEPLOYMENT and OPENAI_API_VERSION, "Azure mode requires OPENAI_DEPLOYMENT and OPENAI_API_VERSION")
    url = f"{OPENAI_URL}/openai/deployments/{OPENAI_DEPLOYMENT}/embeddings"
    params = {"api-version": OPENAI_API_VERSION}
    headers = {"api-key": OPENAI_API_KEY, "Content-Type": "application/json"}
    body = {"input": batch}
    r = requests.post(url, params=params, headers=headers, json=body, timeout=60)
    r.raise_for_status()
    data = r.json()["data"]
    return [item["embedding"] for item in data]

def _openai_embed(batch: List[str]) -> List[List[float]]:
    url = f"{OPENAI_URL}/embeddings"
    headers = {"Authorization": f"Bearer {OPENAI_API_KEY}", "Content-Type": "application/json"}
    body = {"model": OPENAI_EMBED_MODEL, "input": batch}
    r = requests.post(url, headers=headers, json=body, timeout=60)
    r.raise_for_status()
    data = r.json()["data"]
    return [item["embedding"] for item in data]

def get_embeddings(batch: List[str]) -> List[List[float]]:
    fn = _azure_embed if is_azure() else _openai_embed
    delay = 1.0
    for attempt in range(1, 6):
        try:
            return fn(batch)
        except requests.HTTPError as e:
            status = e.response.status_code if e.response is not None else "?"
            logging.error(f"HTTP {status} getting embeddings (attempt {attempt}/5): {e}")
            if status in (429, 500, 502, 503, 504):
                time.sleep(delay)
                delay = min(delay * 2, 30)
                continue
            raise
        except requests.RequestException as e:
            logging.error(f"Request error (attempt {attempt}/5): {e}")
            time.sleep(delay)
            delay = min(delay * 2, 30)
    raise RuntimeError("Failed to fetch embeddings after retries")

def main():
    require(OPENAI_API_KEY, "Missing OPENAI_API_KEY")
    df = load_reviews()
    total = len(df)
    logging.info(f"Total records to embed: {total:,}")
    texts = df["review_text"].tolist()

    all_vectors: List[List[float]] = []
    for i in range(0, total, BATCH_SIZE):
        batch = texts[i:i+BATCH_SIZE]
        logging.info(f"Processing batch {i//BATCH_SIZE + 1}/{(total + BATCH_SIZE - 1)//BATCH_SIZE} ({len(batch)} items)...")
        vectors = get_embeddings(batch)
        if len(vectors) != len(batch):
            raise RuntimeError(f"Embedding count mismatch: got {len(vectors)} for {len(batch)} inputs")
        all_vectors.extend(vectors)

    # Attach back to df and write CSV
    df = df.reset_index(drop=True)
    df["embedding"] = [json.dumps(v) for v in all_vectors]
    OUTPUT_PATH = ROOT / OUTPUT  # repo root
    df.to_csv(OUTPUT_PATH, index=False)
    logging.info(f"✓ Wrote embeddings to {OUTPUT_PATH}")

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        logging.error(f"Embedding pipeline failed: {e}")
        raise
