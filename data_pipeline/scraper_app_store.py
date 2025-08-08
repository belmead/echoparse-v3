"""
scraper_app_store.py

This module reaches out to the App Store (via requests.get) and parses
the JSON to return the first 10 pages of app reviews and writes them to a
CSV.

Return: CSV with app rating data, ready to be put into a DataFrame.
"""

import time
import requests
import json
import csv

def scrape_app_store(app_id, start_page, end_page, country, delay):
    all_reviews = []

    for page in range(start_page, end_page + 1):
        try:
            response = requests.get(
                f"https://itunes.apple.com/{country}/rss/customerreviews/page={page}/id={app_id}/json"
            )
            print(f"HTTP status for page {page}" + ":" +" {requests.response}")  # Check HTTP status
            response.raise_for_status()
            json_data = response.json()
            entries = json_data.get('feed', {}).get('entry', [])
            
            if isinstance(entries, dict):  # If only one review exists
                entries = [entries]
            
            for entry in entries:
                review = extract_review_data(entry)
                all_reviews.append(review)
            
            time.sleep(delay)
        
        except Exception as e:
            print(f"Error extracting review data: {e}")
            continue  # Try the next page

    return all_reviews

def extract_review_data(entry):
    author = entry.get('author', {}).get('name', {}).get('label', 'N/A')
    rating = entry.get('im:rating', {}).get('label', 'N/A')
    review_text = entry.get('content', {}).get('label', 'N/A')
    review_date = entry.get('updated', {}).get('label', 'N/A')
    title = entry.get('title', {}).get('label', 'N/A')
    version = entry.get('im:version', {}).get('label', 'N/A')

    return {
        "author_name": author,
        "rating": rating,
        "review_text": review_text,
        "review_date": review_date,
        "title": title,
        "app_version": version
    }

def main():
    app_id = 677420559
    start_page = 1
    end_page = 10
    country = "us"
    delay = 1.5

    reviews = scrape_app_store(app_id, start_page, end_page, country, delay)

    if reviews:
        with open('raw_apple_data.csv', 'w', newline='') as csv_file:
            writer = csv.DictWriter(csv_file, fieldnames=reviews[0].keys())
            writer.writeheader()
            writer.writerows(reviews)
        print(f"✅ Successfully wrote {len(reviews)} reviews to raw_apple_data.csv")
    else:
        print("⚠️ No reviews found. Are you pointing to the correct app ID?")

if __name__ == "__main__":
    main()
