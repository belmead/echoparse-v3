# data_pipeline/embed.py

import os
import json
import logging
import pandas as pd
import requests
from dotenv import load_dotenv

load_dotenv()

# Configuration: model and batch size are configurable via env
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_URL = os.getenv("OPENAI_URL", "https://api.openai.com/v1").rstrip("/")
OPENAI_EMBED_MODEL = os.getenv("OPENAI_EMBED_MODEL", "text-embedding-ada-002")
BATCH_SIZE = int(os.getenv("EMBED_BATCH_SIZE", "100"))

CLEAN_APP_STORE = "clean_app_store.csv"
CLEAN_GOOGLE_PLAY = "clean_google_play.csv"
OUTPUT_CSV = "embedded_reviews.csv"

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

def load_data():
    """Load cleaned CSVs and concatenate them."""
    frames = []
    if os.path.exists(CLEAN_APP_STORE):
        a = pd.read_csv(CLEAN_APP_STORE)
        frames.append(a)
    if os.path.exists(CLEAN_GOOGLE_PLAY):
        g = pd.read_csv(CLEAN_GOOGLE_PLAY)
        frames.append(g)
    if not frames:
        raise FileNotFoundError(f"Expected at least one of {CLEAN_APP_STORE}, {CLEAN_GOOGLE_PLAY}")
    df = pd.concat(frames, ignore_index=True)
    return df

def ensure_prepared_text(df: pd.DataFrame) -> pd.DataFrame:
    """Ensure a prepared_text column by trimming whitespace and filling missing values."""
    if "prepared_text" not in df.columns:
        df["prepared_text"] = df["review_text"].astype(str).fillna("").str.strip()
    else:
        df["prepared_text"] = df["prepared_text"].astype(str).fillna("").str.strip()
    return df

def get_embeddings(texts):
    """Call OpenAI API (or Azure if configured) to get embeddings for a batch of texts."""
    headers = {"Authorization": f"Bearer {OPENAI_API_KEY}", "Content-Type": "application/json"}
    body = {"model": OPENAI_EMBED_MODEL, "input": texts}
    response = requests.post(f"{OPENAI_URL}/embeddings", headers=headers, json=body, timeout=60)
    response.raise_for_status()
    data = response.json()["data"]
    return [json.dumps(item["embedding"]) for item in data]

def main():
    df = load_data()
    df = ensure_prepared_text(df)

    # Remove rows with empty prepared_text
    df = df[df["prepared_text"].str.len() > 0].copy()
    logging.info(f"Embedding {len(df)} reviews...")

    all_embeddings = []
    texts = df["prepared_text"].tolist()

    for i in range(0, len(texts), BATCH_SIZE):
        batch = texts[i : i + BATCH_SIZE]
        logging.info(f"Processing batch {i // BATCH_SIZE + 1} of {(len(texts) + BATCH_SIZE - 1) // BATCH_SIZE}")
        embeddings = get_embeddings(batch)
        all_embeddings.extend(embeddings)

    df["embedding"] = all_embeddings

    # If sentiment scores are needed, you can compute them here (e.g., using TextBlob/VADER)
    # For now, leave as None/NaN so upload_to_supabase.py can handle or ignore.
    if "sentiment_score" not in df.columns:
        df["sentiment_score"] = None

    df.to_csv(OUTPUT_CSV, index=False)
    logging.info(f"✓ Wrote embeddings for {len(df)} reviews to {OUTPUT_CSV}")

if __name__ == "__main__":
    main()
