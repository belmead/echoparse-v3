"""
calculate_metrics.py

This script calculates all dashboard metrics from the app_reviews table
and populates the dashboard_metrics table for fast dashboard loading.

Uses sentinel values for "N/A" cases:
- Platform ratings: -1.0 when no reviews in time period
- One star percentage: -1.0 when no reviews in time period  
- Avg sentiment: -999.0 when no reviews with sentiment scores

Usage: python calculate_metrics.py
"""

import os
import psycopg2
import psycopg2.extras
from psycopg2.extras import Json
from datetime import datetime, timedelta
from collections import Counter
import re
from dotenv import load_dotenv

# Load .env if present
load_dotenv()

def get_db_connection():
    """Connect to Supabase PostgreSQL database"""
    try:
        database_url = os.getenv('DATABASE_URL')
        if database_url:
            return psycopg2.connect(database_url)
        return psycopg2.connect(
            host=os.getenv('SUPABASE_HOST'),
            database=os.getenv('SUPABASE_DATABASE', 'postgres'),
            user=os.getenv('SUPABASE_USER', 'postgres'),
            password=os.getenv('SUPABASE_PASSWORD'),
            port=os.getenv('SUPABASE_PORT', '5432'),
            sslmode='require'
        )
    except Exception as e:
        print(f"❌ Database connection failed: {e}")
        print("💡 Make sure you have set either:")
        print("   DATABASE_URL environment variable, or")
        print("   SUPABASE_HOST, SUPABASE_PASSWORD, etc.")
        raise

def calculate_one_star_percentage(cursor, days=30):
    cursor.execute("""
        SELECT 
            COUNT(*) FILTER (WHERE rating = 1) AS one_star_count,
            COUNT(*) AS total_count
        FROM app_reviews 
        WHERE review_date >= NOW() - INTERVAL '%s days'
    """, (days,))
    result = cursor.fetchone() or {}
    one_star = result.get('one_star_count', 0)
    total    = result.get('total_count',    0)
    
    # If no reviews, return -1 as sentinel value for "N/A"
    if total == 0:
        return -1.0
    
    return round(one_star / total * 100, 2)

def calculate_avg_sentiment(cursor, days=30):
    cursor.execute("""
        SELECT AVG(sentiment_score) AS avg_sentiment, COUNT(*) AS review_count
        FROM app_reviews 
        WHERE review_date >= NOW() - INTERVAL '%s days'
          AND sentiment_score IS NOT NULL
    """, (days,))
    result = cursor.fetchone() or {}
    avg = result.get('avg_sentiment')
    count = result.get('review_count', 0)
    
    # If no reviews with sentiment scores, return -999 as sentinel value for "N/A"
    if count == 0 or avg is None:
        return -999.0
    
    return round(float(avg), 2)

def calculate_trending_topic(cursor, days=30):
    stop_words = {
        'the', 'and', 'for', 'are', 'but', 'not', 'you', 'all', 'can', 'had', 'her', 'was', 'one', 'our',
        'out', 'day', 'get', 'has', 'him', 'his', 'how', 'man', 'new', 'now', 'old', 'see', 'two', 'way',
        'who', 'boy', 'did', 'its', 'let', 'put', 'say', 'she', 'too', 'use', 'app', 'this', 'that', 'with',
        'have', 'from', 'they', 'know', 'want', 'been', 'good', 'much', 'some', 'time', 'very', 'when', 'come',
        'here', 'just', 'like', 'long', 'make', 'many', 'over', 'such', 'take', 'than', 'them', 'well', 'were'
    }
    
    cursor.execute("""
        SELECT review_text
        FROM app_reviews 
        WHERE review_date >= NOW() - INTERVAL '%s days'
          AND review_text IS NOT NULL
    """, (days,))
    
    all_words = []
    for row in cursor.fetchall():
        text = row.get('review_text', '').lower()
        words = re.findall(r'\b[a-z]{3,}\b', text)
        all_words.extend([w for w in words if w not in stop_words])
    
    if not all_words:
        return "N/A"
    
    most_common = Counter(all_words).most_common(1)[0][0]
    return f"'{most_common}'"

def calculate_review_volume_delta(cursor):
    cursor.execute("""
        SELECT 
            COUNT(*) FILTER (WHERE review_date >= NOW() - INTERVAL '30 days')      AS current_30d,
            COUNT(*) FILTER (WHERE review_date >= NOW() - INTERVAL '60 days'
                           AND review_date <  NOW() - INTERVAL '30 days')      AS previous_30d
        FROM app_reviews
    """)
    result = cursor.fetchone() or {}
    current  = result.get('current_30d',  0)
    previous = result.get('previous_30d', 0)
    
    if previous == 0:
        return 0.0 if current == 0 else 100.0
    
    return round((current - previous) / previous * 100, 1)

def calculate_platform_score_gap(cursor, days=30):
    cursor.execute("""
        SELECT platform, AVG(rating) AS avg_rating, COUNT(*) AS review_count
        FROM app_reviews 
        WHERE review_date >= NOW() - INTERVAL '%s days'
        GROUP BY platform
    """, (days,))
    rows = cursor.fetchall() or []
    
    ratings = {}
    for r in rows:
        platform = r['platform']
        avg_rating = r['avg_rating']
        review_count = r['review_count']
        
        # Only include platforms that have reviews
        if review_count > 0 and avg_rating is not None:
            ratings[platform] = avg_rating
    
    ios = ratings.get('apple')
    andr = ratings.get('android')
    
    # Handle cases where one or both platforms have no data
    if ios is None and andr is None:
        return "No data available"
    elif ios is None:
        return f"iOS: N/A vs Android: {andr:.1f}"
    elif andr is None:
        return f"iOS: {ios:.1f} vs Android: N/A"
    else:
        return f"iOS: {ios:.1f} vs Android: {andr:.1f}"

def calculate_platform_rating(cursor, platform, days=30):
    cursor.execute("""
        SELECT AVG(rating) AS avg_rating, COUNT(*) AS review_count
        FROM app_reviews 
        WHERE platform = %s
          AND review_date >= NOW() - INTERVAL '%s days'
    """, (platform, days))
    result = cursor.fetchone() or {}
    avg = result.get('avg_rating')
    count = result.get('review_count', 0)
    
    # If no reviews in the time period, return -1 as sentinel value for "N/A"
    if count == 0 or avg is None:
        return -1.0
    
    return round(float(avg), 1)

def insert_or_update_metric(cursor, metric_name, metric_value, time_period='30d', metadata=None):
    """Insert or update a metric; wrap metadata as JSON if provided"""
    meta_val = Json(metadata) if metadata is not None else None
    cursor.execute("""
        INSERT INTO dashboard_metrics (metric_name, metric_value, metric_metadata, time_period)
        VALUES (%s, %s, %s, %s)
        ON CONFLICT (metric_name, time_period) 
        DO UPDATE SET 
            metric_value     = EXCLUDED.metric_value,
            metric_metadata  = EXCLUDED.metric_metadata,
            calculation_date = NOW()
    """, (metric_name, metric_value, meta_val, time_period))

def main():
    print("🔄 Starting metrics calculation...")
    try:
        conn = get_db_connection()
        cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

        # Calculate all metrics
        one_star_pct     = calculate_one_star_percentage(cursor)
        insert_or_update_metric(cursor, 'one_star_reviews_pct', one_star_pct)

        avg_sentiment    = calculate_avg_sentiment(cursor)
        insert_or_update_metric(cursor, 'avg_sentiment', avg_sentiment)

        trending_topic   = calculate_trending_topic(cursor)
        insert_or_update_metric(cursor, 'trending_topic', 0, metadata={'topic': trending_topic})

        volume_delta     = calculate_review_volume_delta(cursor)
        insert_or_update_metric(cursor, 'review_volume_delta_pct', volume_delta)

        platform_gap     = calculate_platform_score_gap(cursor)
        insert_or_update_metric(cursor, 'platform_score_gap', 0, metadata={'gap_text': platform_gap})

        app_store_rating = calculate_platform_rating(cursor, 'apple')
        insert_or_update_metric(cursor, 'app_store_rating_30d', app_store_rating)

        play_store_rating= calculate_platform_rating(cursor, 'android')
        insert_or_update_metric(cursor, 'play_store_rating_30d', play_store_rating)

        conn.commit()
        print("✅ All metrics calculated and saved successfully!")
        
        # Print summary of calculated values for debugging
        print(f"📊 Calculated metrics:")
        print(f"   One star %: {one_star_pct if one_star_pct != -1.0 else 'N/A'}")
        print(f"   Avg sentiment: {avg_sentiment if avg_sentiment != -999.0 else 'N/A'}")
        print(f"   Trending topic: {trending_topic}")
        print(f"   Volume delta: {volume_delta}%")
        print(f"   Platform gap: {platform_gap}")
        print(f"   App Store rating: {app_store_rating if app_store_rating != -1.0 else 'N/A'}")
        print(f"   Play Store rating: {play_store_rating if play_store_rating != -1.0 else 'N/A'}")

    except Exception as e:
        print(f"❌ Error calculating metrics: {e}")
        if 'conn' in locals():
            conn.rollback()
        raise
    finally:
        if 'cursor' in locals(): 
            cursor.close()
        if 'conn' in locals(): 
            conn.close()

if __name__ == "__main__":
    main()