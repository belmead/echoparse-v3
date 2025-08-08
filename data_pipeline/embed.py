#!/usr/bin/env python3
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
ROOT = pathlib.Path(__file__).resolve().parent.parent  # repo root
OUTPUT = ROOT / "embedded_reviews.csv"

APPLE_CSV = ROOT / "raw_apple_data.csv"
GOOGLE_CSV = ROOT / "raw_google_data.csv"

def is_azure() -> bool:
    return bool(OPENAI_DEPLOYMENT and OPENAI_API_VERSION) or ("azure.com" in OPENAI_URL)

def col(df: pd.DataFrame, candidates: List[str], default=None):
    for c in candidates:
        if c in df.columns:
            return c
    return default

def load_reviews() -> pd.DataFrame:
    logging.info("Loading app store data...")
    frames = []
    if APPLE_CSV.exists():
        a = pd.read_csv(APPLE_CSV); a["platform"] = "apple"; frames.append(a)
    if GOOGLE_CSV.exists():
        g = pd.read_csv(GOOGLE_CSV); g["platform"] = "google"; frames.append(g)
    if not frames:
        raise FileNotFoundError(f"No input CSVs found. Expected {APPLE_CSV.name} and/or {GOOGLE_CSV.name}")

    df = pd.concat(frames, ignore_index=True)

    id_c    = col(df, ["review_id","reviewId","id","guid","uuid"])
    text_c  = col(df, ["review_text","content","text","body","review","comment"])
    author_c= col(df, ["author_name","userName","author","user","name"])
    rating_c= col(df, ["rating","score","stars"])
    date_c  = col(df, ["review_date","at","date","time","updated"])
    ver_c   = col(df, ["app_version","version","reviewVersion","appVersion"])
    if not id_c or not text_c:
        raise KeyError(f"Missing id/text columns. Have: {list(df.columns)[:20]}")

    out = pd.DataFrame({
        "platform": df["platform"],
        "review_id": df[id_c].astype(str),
        "review_text": df[text_c].astype(str).str.strip(),
    })
    out["author_name"] = df[author_c].astype(str) if author_c else ""
    # ratings → numeric, enforce 1..5 and cast to int
    if rating_c:
        out["rating"] = pd.to_numeric(df[rating_c], errors="coerce")
    else:
        out["rating"] = pd.Series([None]*len(out), dtype="float")
    valid = out["rating"].between(1,5)
    dropped = int((~valid).sum())
    if dropped:
        logging.warning(f"Dropping {dropped} rows with invalid ratings")
    out = out[valid].copy()
    out["rating"] = out["rating"].astype(int)

    out["review_date"] = df[date_c].astype(str) if date_c else ""
    out["app_version"] = df[ver_c].astype(str) if ver_c else ""
    out["prepared_text"] = out["review_text"].str.replace(r"\s+", " ", regex=True).str.strip()
    out = out[out["prepared_text"].str.len() > 0].drop_duplicates(subset=["platform","review_id"])
    return out

def _azure_embed(batch: List[str]) -> List[List[float]]:
    url = f"{OPENAI_URL}/openai/deployments/{OPENAI_DEPLOYMENT}/embeddings"
    params = {"api-version": OPENAI_API_VERSION}
    headers = {"api-key": OPENAI_API_KEY, "Content-Type": "application/json"}
    r = requests.post(url, params=params, headers=headers, json={"input": batch}, timeout=60)
    r.raise_for_status()
    return [item["embedding"] for item in r.json()["data"]]

def _openai_embed(batch: List[str]) -> List[List[float]]:
    url = f"{OPENAI_URL}/embeddings"
    headers = {"Authorization": f"Bearer {OPENAI_API_KEY}", "Content-Type": "application/json"}
    r = requests.post(url, headers=headers, json={"model": OPENAI_EMBED_MODEL, "input": batch}, timeout=60)
    r.raise_for_status()
    return [item["embedding"] for item in r.json()["data"]]

def get_embeddings(batch: List[str]) -> List[List[float]]:
    fn = _azure_embed if is_azure() else _openai_embed
    delay = 1.0
    for attempt in range(1, 6):
        try:
            return fn(batch)
        except requests.HTTPError as e:
            code = e.response.status_code if e.response is not None else "?"
            logging.error(f"HTTP {code} on embeddings (attempt {attempt}/5): {e}")
            if code in (429,500,502,503,504):
                time.sleep(delay); delay = min(delay*2, 30); continue
            raise
        except requests.RequestException as e:
            logging.error(f"Request error (attempt {attempt}/5): {e}")
            time.sleep(delay); delay = min(delay*2, 30)
    raise RuntimeError("Failed to fetch embeddings after retries")

def main():
    if not OPENAI_API_KEY:
        raise ValueError("Missing OPENAI_API_KEY")
    df = load_reviews()
    texts = df["prepared_text"].tolist()
    logging.info(f"Total records to embed: {len(texts):,}")

    vectors: List[List[float]] = []
    for i in range(0, len(texts), BATCH_SIZE):
        batch = texts[i:i+BATCH_SIZE]
        logging.info(f"Processing batch {i//BATCH_SIZE + 1}/{(len(texts)+BATCH_SIZE-1)//BATCH_SIZE} ({len(batch)} items)...")
        vecs = get_embeddings(batch)
        if len(vecs) != len(batch):
            raise RuntimeError(f"Embedding count mismatch: got {len(vecs)} for {len(batch)} inputs")
        vectors.extend(vecs)

    df = df.reset_index(drop=True)
    df["embedding"] = [json.dumps(v) for v in vectors]
    df.to_csv(OUTPUT, index=False)
    logging.info(f"✓ Wrote embeddings to {OUTPUT}")

if __name__ == "__main__":
    main()
