"""
embed.py

This script embeds review data using a hosted OpenAI-compatible model endpoint.

Steps:
1. Load cleaned data from the Apple and Google CSVs.
2. Concatenate and format data into a prompt-friendly string.
3. Send batches of data to an OpenAI-compatible embedding endpoint.
4. Store the embeddings with the original data in a CSV file.
"""

import pandas as pd
import requests
import time
import logging
import os
from dotenv import load_dotenv

# Load environment variables from project root
load_dotenv('')

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Configuration from environment variables
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_URL = os.getenv("OPENAI_URL")
MODEL = os.getenv("OPENAI_MODEL")
API_VERSION = os.getenv("OPENAI_API_VERSION")

# Non-sensitive configuration
BATCH_SIZE = 100

# Validate required environment variables
required_vars = ["OPENAI_API_KEY", "OPENAI_URL"]
missing_vars = [var for var in required_vars if not os.getenv(var)]
if missing_vars:
    raise ValueError(f"Missing required environment variables: {', '.join(missing_vars)}")

def load_app_store_data():
    """Load and standardize app store review data."""
    logger.info("Loading app store data...")
    
    google_df = pd.read_csv("clean_google_play.csv")
    apple_df = pd.read_csv("clean_app_store.csv")
    
    # Combine app store data
    app_df = pd.concat([google_df, apple_df], ignore_index=True)
    
    # Add data source metadata
    app_df['data_source'] = 'app_review'
    app_df['has_text_content'] = True  # App reviews always have text
    
    logger.info(f"Loaded {len(app_df)} app store reviews")
    return app_df

def prepare_prompts(df):
    """Prepare text prompts for embedding based on data source."""
    prepared_texts = []
    
    for idx, row in df.iterrows():
        if row['data_source'] == 'app_review':
            # Format app review data
            prompt = (
                f"platform: {row.get('platform', 'unknown')}. "
                f"date: {row.get('date', 'unknown')}. "
                f"rating: {row.get('rating', 'unknown')}. "
                f"version: {row.get('app_version', 'unknown')}. "
                f"passage: {row.get('text_content', '')}"
            )
        else:
            # Fallback for unknown data sources
            prompt = f"content: {row.get('text_content', '')}"
        
        prepared_texts.append(prompt)
    
    return prepared_texts

def get_embeddings(batch):
    """Get embeddings from OpenAI-compatible endpoint."""
    url = f"{OPENAI_URL}/{MODEL}/embeddings?api-version={API_VERSION}"
    headers = {
        "api-key": OPENAI_API_KEY,
        "Content-Type": "application/json"
    }
    body = {"input": batch}
    
    try:
        response = requests.post(url, headers=headers, json=body)
        response.raise_for_status()
        return [item["embedding"] for item in response.json()["data"]]
    except requests.exceptions.RequestException as e:
        logger.error(f"Error getting embeddings: {e}")
        raise

def main():
    """Main embedding pipeline."""
    logger.info("Starting embedding pipeline...")
    
    # Load all data sources
    app_df = load_app_store_data()
        
    # Combine all data
    all_df = pd.concat([app_df], ignore_index=True, sort=False)
    logger.info(f"Total records loaded: {len(all_df)}")
    
    # Filter to only records that should be embedded
    embed_df = all_df[all_df['has_text_content'] == True].copy()
    logger.info(f"Records to embed: {len(embed_df)}")
    
    # Prepare prompts for embedding
    logger.info("Preparing prompts...")
    embed_df['prepared_text'] = prepare_prompts(embed_df)
    
    # Generate embeddings in batches
    logger.info("Generating embeddings...")
    all_embeddings = []
    
    for i in range(0, len(embed_df), BATCH_SIZE):
        batch_texts = embed_df["prepared_text"].iloc[i:i + BATCH_SIZE].tolist()
        batch_num = (i // BATCH_SIZE) + 1
        total_batches = (len(embed_df) + BATCH_SIZE - 1) // BATCH_SIZE
        
        logger.info(f"Processing batch {batch_num}/{total_batches} ({len(batch_texts)} items)...")
        
        try:
            embeddings = get_embeddings(batch_texts)
            all_embeddings.extend(embeddings)
            
            # Rate limiting
            time.sleep(1)
            
        except Exception as e:
            logger.error(f"Failed to process batch {batch_num}: {e}")
            raise
    
    # Add embeddings to dataframe
    embed_df['embedding'] = all_embeddings
    
    # Save embedded records
    embed_df.to_csv("embedded_reviews.csv", index=False)
    logger.info(f"Saved {len(embed_df)} embedded records to embedded_reviews.csv")
    
    # Summary statistics
    logger.info("\n=== EMBEDDING SUMMARY ===")
    logger.info(f"Total records processed: {len(all_df)}")
    logger.info(f"App reviews embedded: {len(embed_df[embed_df['data_source'] == 'app_review'])}")
    logger.info("Embedding pipeline completed successfully!")

if __name__ == "__main__":
    main()