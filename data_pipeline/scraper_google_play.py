"""
scraper_google_play.py

This module uses the google_play_scraper library to assist in reaching out to the Google Play
Store to fetch 1,000 app reviews (Google 500s requests past that point).

The logic is slightly different in that Google Play does not paginate reviews.

Return: CSV with app rating data, ready to be put into a DataFrame.
"""

from google_play_scraper import reviews, Sort
import csv

def scrape_google_play(app_id, count, lang, country):
    result, _ = reviews(
        app_id,
        lang=lang,
        country=country,
        count=count,
        sort=Sort.NEWEST
    )
    return result

def main():
    count = 1000
    lang = "en"
    country = "us"
    app_id = "com.ifs.banking.fiid1454"  
     
    reviews = scrape_google_play(app_id, count, lang, country)

    if reviews:
        with open('raw_google_data.csv', 'w', newline='') as csv_file:
            writer = csv.DictWriter(csv_file, fieldnames=reviews[0].keys())
            writer.writeheader()
            writer.writerows(reviews)
            print(f"✅ Successfully wrote {len(reviews)} reviews to raw_google_data.csv")
    else:
        print("⚠️ No reviews found. Are you pointing to the correct app ID?")

if __name__ == "__main__":
    main()