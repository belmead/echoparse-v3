"""
main.py - FastAPI Backend for echoparse v3

This API serves dashboard metrics and handles live app store rating requests.

Endpoints:
- GET /metrics - Returns all pre-calculated dashboard metrics
- GET /live-ratings - Returns current app store ratings (live)
- GET /health - Health check endpoint

Usage: uvicorn main:app --reload
"""

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
import psycopg2
import psycopg2.extras
import os
from dotenv import load_dotenv
from typing import Dict, Any
import requests
import json
import re
import openai
from pydantic import BaseModel

# Load environment variables from .env file
load_dotenv()

app = FastAPI(
    title="echoparse v3 API",
    description="Dashboard metrics and live ratings API",
    version="3.0.0"
)

# CORS middleware for React frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins for local development
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class LLMRequest(BaseModel):
    prompt: str

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
        raise HTTPException(status_code=500, detail=f"Database connection failed: {e}")

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "service": "echoparse-v3-api"}

@app.get("/metrics")
async def get_dashboard_metrics():
    """
    Get all pre-calculated dashboard metrics
    
    Returns:
        dict: All metrics formatted for dashboard consumption
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        
        # Get all metrics for 30-day period
        cursor.execute("""
            SELECT metric_name, metric_value, metric_metadata, calculation_date
            FROM dashboard_metrics 
            WHERE time_period = '30d'
            ORDER BY metric_name
        """)
        
        raw_metrics = cursor.fetchall()
        
        # Format metrics for dashboard
        formatted_metrics = {}
        
        for metric in raw_metrics:
            name = metric['metric_name']
            value = float(metric['metric_value'])
            metadata = metric['metric_metadata']
            
            # Format specific metrics with special handling and sentinel value detection
            if name == 'one_star_reviews_pct':
                if value == -1.0:
                    formatted_metrics['one_star_reviews'] = {
                        'value': "N/A",
                        'raw_value': None
                    }
                else:
                    formatted_metrics['one_star_reviews'] = {
                        'value': f"{value}%",
                        'raw_value': value
                    }
            
            elif name == 'avg_sentiment':
                if value == -999.0:
                    formatted_metrics['avg_sentiment'] = {
                        'value': "N/A",
                        'raw_value': None,
                        'scale': "on [-1.0, 1.0] scale"
                    }
                else:
                    formatted_metrics['avg_sentiment'] = {
                        'value': f"{value:.2f}",
                        'raw_value': value,
                        'scale': "on [-1.0, 1.0] scale"
                    }
            
            elif name == 'trending_topic':
                topic = metadata.get('topic', 'N/A') if metadata else 'N/A'
                formatted_metrics['trending_topic'] = {
                    'value': topic,
                    'raw_value': topic
                }
            
            elif name == 'review_volume_delta_pct':
                sign = "+" if value >= 0 else ""
                formatted_metrics['review_volume_delta'] = {
                    'value': f"{sign}{value}%",
                    'raw_value': value
                }
            
            elif name == 'platform_score_gap':
                gap_text = metadata.get('gap_text', 'N/A') if metadata else 'N/A'
                formatted_metrics['platform_score_gap'] = {
                    'value': gap_text,
                    'raw_value': gap_text
                }
            
            elif name == 'app_store_rating_30d':
                if value == -1.0:
                    formatted_metrics['app_store_rating'] = {
                        'value': "N/A",
                        'raw_value': None
                    }
                else:
                    formatted_metrics['app_store_rating'] = {
                        'value': f"{value:.1f}",
                        'raw_value': value
                    }
            
            elif name == 'play_store_rating_30d':
                if value == -1.0:
                    formatted_metrics['play_store_rating'] = {
                        'value': "N/A", 
                        'raw_value': None
                    }
                else:
                    formatted_metrics['play_store_rating'] = {
                        'value': f"{value:.1f}",
                        'raw_value': value
                    }
        
        cursor.close()
        conn.close()
        
        return {
            "success": True,
            "data": formatted_metrics,
            "last_updated": raw_metrics[0]['calculation_date'].isoformat() if raw_metrics else None
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching metrics: {e}")

@app.get("/live-ratings")
async def get_live_ratings():
    """
    Get current live app store ratings
    Returns:
        dict: Current live ratings from both app stores
    """
    try:
        # --- App Store scraping ---
        ios_rating = None
        try:
            ios_resp = requests.get("https://itunes.apple.com/lookup?id=677420559", timeout=10)
            ios_resp.raise_for_status()
            ios_data = ios_resp.json()
            ios_rating = ios_data.get('results', [{}])[0].get('averageUserRating')
        except Exception as e:
            print(f"App Store scrape error: {e}")
            ios_rating = None

        # --- Google Play scraping (fallback to regex if no API) ---
        android_rating = None
        try:
            play_resp = requests.get("https://play.google.com/store/apps/details?id=com.ifs.banking.fiid1454&hl=en&gl=US", timeout=10)
            play_resp.raise_for_status()
            # Try to extract the rating from the HTML
            match = re.search(r'"aggregateRating":\{"@type":"AggregateRating","ratingValue":"([0-9.]+)"', play_resp.text)
            if match:
                android_rating = float(match.group(1))
        except Exception as e:
            print(f"Google Play scrape error: {e}")
            android_rating = None

        live_ratings = {
            "app_store_live": {
                "value": f"{ios_rating:.1f}" if ios_rating is not None else "N/A",
                "raw_value": ios_rating,
                "source": "live"
            },
            "play_store_live": {
                "value": f"{android_rating:.1f}" if android_rating is not None else "N/A",
                "raw_value": android_rating,
                "source": "live"
            }
        }

        return {
            "success": True,
            "data": live_ratings,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching live ratings: {e}")

@app.post("/llm-context")
async def llm_context(body: LLMRequest):
    prompt = body.prompt
    if not prompt:
        raise HTTPException(status_code=400, detail="Missing prompt")

    # Get embedding from OpenAI (new API)
    try:
        client = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        response = client.embeddings.create(
            input=prompt,
            model="text-embedding-3-small"
        )
        embedding = response.data[0].embedding
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"OpenAI embedding error: {e}")

    # Query Supabase/Postgres for similar reviews
    try:
        conn = psycopg2.connect(os.getenv("DATABASE_URL"))
        cur = conn.cursor()
        emb_str = str(list(embedding))
        cur.execute(f'''
            SELECT id, review_text, author_name, rating, review_date, app_version, platform, 1 - (embedding <#> %s::vector) AS similarity
            FROM app_reviews
            ORDER BY embedding <#> %s::vector
            LIMIT 5
        ''', (emb_str, emb_str))
        results = cur.fetchall()
        cur.close()
        conn.close()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Supabase/pgvector error: {e}")

    # Format results
    formatted = [
        {
            "id": r[0],
            "review_text": r[1],
            "author_name": r[2],
            "rating": r[3],
            "review_date": r[4].isoformat() if r[4] else None,
            "app_version": r[5],
            "platform": r[6],
            "similarity": float(r[7])
        }
        for r in results
    ]

    # 1. Clean the user query using OpenAI (like fixTyposAndShorthand)
    try:
        clean_prompt = '''You are a query preprocessor for a banking app feedback system. 
Your job is to clean up user queries while preserving their intent and key terms.

Rules:
1. Fix obvious typos and spelling errors
2. Expand common abbreviations and shorthand
3. Preserve banking/finance terminology exactly
4. Keep the query concise and searchable
5. Don't change the core meaning or intent
6. Return ONLY the cleaned query, no explanations

Example: "what are ppl sayhing about tranfers" → "what are people saying about transfers"'''
        clean_response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": clean_prompt},
                {"role": "user", "content": prompt}
            ],
            max_tokens=100,
            temperature=0.1
        )
        cleaned_query = clean_response.choices[0].message.content.strip()
    except Exception as e:
        cleaned_query = prompt

    # 2. Analyze the query using OpenAI (like analyzeQuery in query-intelligence.ts)
    try:
        analysis_prompt = '''You are a query intelligence system for a banking app feedback database. Your job is to analyze user queries and determine the optimal search strategy.\n\nAvailable metadata fields:\n- rating: 1-5 (integer)\n- platform: "android" or "apple" \n- source: "clean_google_play", "clean_app_store", "clean_mes_data"\n- review_date: ISO date string (e.g., "2025-03-15T23:15:51-07:00")\n- text: Full review content\n\nQuery types:\n1. STRUCTURED: Queries requesting specific metadata values (ratings, platforms, dates)\n2. SEMANTIC: Queries about concepts, themes, or content (sentiment, features, issues)\n3. HYBRID: Queries combining both structured filters and semantic concepts\n\nInstructions:\n- For structured queries, extract precise metadata filters\n- For semantic queries, clean and optimize the search terms\n- For hybrid queries, separate the structured parts from semantic parts\n- Always provide the reasoning for your classification\n\nReturn a JSON object with this exact structure:\n{\n  "intent": "structured|semantic|hybrid",\n  "structuredFilters": {\n    // Only include relevant filters, omit others\n    "rating": {"$in": [1,2]} or {"$gte": 4} etc,\n    "platform": {"$in": ["android"]},\n    "source": {"$in": ["clean_google_play"]},\n    "year": 2025,\n    "dateRange": {"startDate": "2025-01-01", "endDate": "2025-03-31"}\n  },\n  "semanticQuery": "optimized search terms for semantic matching",\n  "reasoning": "explanation of classification and strategy"\n}\n\nExamples:\nUser: "Show me all 1 and 2 star reviews from 2025"\nResponse: {"intent": "structured", "structuredFilters": {"rating": {"$in": [1,2]}, "year": 2025}, "semanticQuery": "", "reasoning": "Pure structured query requesting specific rating values and year"}\n\nUser: "What are people saying about transfers?"\nResponse: {"intent": "semantic", "semanticQuery": "transfer money banking functionality", "reasoning": "Conceptual query about transfer-related feedback requiring semantic understanding"}\n\nUser: "Android transfer issues in 2025"\nResponse: {"intent": "hybrid", "structuredFilters": {"platform": {"$in": ["android"]}, "year": 2025}, "semanticQuery": "transfer issues problems", "reasoning": "Combines platform/date filters with semantic search for transfer-related issues"}'''
        analysis_response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": analysis_prompt},
                {"role": "user", "content": cleaned_query}
            ],
            max_tokens=500,
            temperature=0.1
        )
        analysis_content = analysis_response.choices[0].message.content or '{}'
        import re as _re
        import json as _json
        clean_content = _re.sub(r'```json|```', '', analysis_content).strip()
        query_analysis = _json.loads(clean_content)
    except Exception as e:
        query_analysis = {
            "intent": "semantic",
            "semanticQuery": cleaned_query,
            "reasoning": f"Query analysis failed: {e}",
            "structuredFilters": {}
        }

    # 3. Generate search queries for semantic matching (like buildSearchQuery)
    try:
        search_prompt = '''You are an expert at searching banking app feedback databases. Given a user's question, generate 2-3 targeted search queries that would find the most relevant feedback.\n\nConsider:\n- Banking terminology (transfers, payments, deposits, external accounts, wire transfers, etc.)\n- User experience terms (crashes, bugs, interface, usability, etc.) \n- Mobile banking context\n\nReturn ONLY a JSON array of search strings, no explanations.\n\nExample: ["transfer external account", "payment mobile banking", "send money functionality"]'''
        search_response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": search_prompt},
                {"role": "user", "content": f'User question: "{cleaned_query}"'}
            ],
            max_tokens=150,
            temperature=0.1
        )
        search_content = search_response.choices[0].message.content or '["' + cleaned_query + '"]'
        search_content = _re.sub(r'```json|```', '', search_content).strip()
        search_queries = _json.loads(search_content)
        if not isinstance(search_queries, list):
            search_queries = [cleaned_query]
    except Exception as e:
        search_queries = [cleaned_query]

    # Keyword boosting and high similarity filtering (Pinecone-style)
    SIMILARITY_THRESHOLD = 0.7
    semantic_keywords = set(str(query_analysis.get('semanticQuery', '')).lower().split())
    def contains_keyword(text, keywords):
        return any(kw in text.lower() for kw in keywords if kw)
    filtered_results = [
        r for r in results
        if float(r[7]) >= SIMILARITY_THRESHOLD and contains_keyword(r[1] or '', semantic_keywords)
    ]
    # Fallback: if not enough, just use top 3 by similarity
    if len(filtered_results) < 2:
        filtered_results = sorted(results, key=lambda r: -float(r[7]))[:3]

    # Compose context for LLM (limit to top 3, Pinecone-style formatting)
    formatted_snippets = []
    for i, r in enumerate(filtered_results[:3]):
        platform = r[6] or 'unknown'
        rating = r[3] or ''
        review_text = r[1] or ''
        date = r[4].isoformat() if r[4] else 'unknown date'
        formatted_snippets.append(f"[{platform}] ⭐{rating}: {review_text} (date: {date})")
    pinecone_context = "\n".join(formatted_snippets)

    # 4. Improved system prompt with explicit summary instructions and Pinecone-style example
    system_message = (
        "You are a data analyst providing executive summaries for app feedback.\n"
        "ALWAYS start your answer with a summary paragraph labeled 'Summary:' that answers the user's question based on the context and query analysis below.\n"
        "If you do not include a summary, your answer is incomplete.\n"
        "Then, provide up to 5 supporting quotes in the following format:\n\n"
        "Source: [source] | Platform: [platform] | Date: [date] | Rating: [rating]\n"
        "Quote: \"[exact quote]\"\n\n"
        "RULES:\n"
        "- NO asterisks, NO markdown, NO HTML\n"
        "- NO \"Citation 1\", NO \"Citation 2\"\n"
        "- Use ONLY the word \"Source:\" and \"Quote:\"\n"
        "- Each quote on separate lines\n"
        "- MUST select quotes from DIFFERENT sources when multiple sources are available\n"
        "- Only use data that actually exists in the context provided\n"
        "- If insufficient data exists, say so rather than fabricating sources\n"
        "- Minimum 1 quote, maximum 5 quotes\n"
        "- Prioritize diversity of sources and platforms in your analysis\n\n"
        "EXAMPLE OUTPUT:\nSummary: Most users in 2025 praised the new transfer feature, but some Android users reported issues.\n\nSource: clean_app_store | Platform: apple | Date: 2025-02-15 | Rating: 5\nQuote: \"Transfers are so much easier now!\"\n\nSource: clean_google_play | Platform: android | Date: 2025-03-01 | Rating: 2\nQuote: \"Transfer keeps failing on my phone.\"\n\nUser Query Analysis:\nIntent: {intent}\nFilters: {filters}\nSemantic Query: {semantic_query}\nReasoning: {reasoning}\nSearch Queries: {search_queries}\n\nContext:\n{pinecone_context}"
    ).format(
        intent=query_analysis.get('intent'),
        filters=query_analysis.get('structuredFilters'),
        semantic_query=query_analysis.get('semanticQuery'),
        reasoning=query_analysis.get('reasoning'),
        search_queries=search_queries,
        pinecone_context=pinecone_context
    )
    llm_prompt = (
        f"Summarize the following reviews for: {cleaned_query}. Then provide up to 5 supporting quotes."
    )

    # Call OpenAI LLM for summary/answer
    try:
        completion = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": system_message},
                {"role": "user", "content": llm_prompt}
            ],
            max_tokens=300,
            temperature=0.2
        )
        answer = completion.choices[0].message.content
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"OpenAI completion error: {e}")

    # LOGGING for root-cause analysis
    print("\n=== LLM DEBUG LOG ===")
    print(f"Cleaned Query: {cleaned_query}")
    print(f"Query Analysis: {query_analysis}")
    print(f"Search Queries: {search_queries}")
    print(f"Filtered Context Snippets (for LLM):\n{pinecone_context}")
    print(f"\n--- SYSTEM PROMPT ---\n{system_message}\n--- USER PROMPT ---\n{llm_prompt}\n")
    print("=== END LLM DEBUG LOG ===\n")

    return {
        "matches": formatted,
        "llm_answer": answer
    }

@app.get("/")
async def root():
    """Root endpoint with API information"""
    return {
        "message": "echoparse v3 API",
        "version": "3.0.0",
        "endpoints": {
            "/metrics": "Get dashboard metrics",
            "/live-ratings": "Get live app store ratings", 
            "/health": "Health check"
        }
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=True)