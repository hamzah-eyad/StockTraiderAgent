"""
MCP Server 2: Geopolitical Intelligence Server
Fetches global news, performs sentiment analysis, and computes geopolitical risk scores.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta

from newsapi import NewsApiClient
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

from mcp.server.fastmcp import FastMCP
from config import NEWS_API_KEY

logger = logging.getLogger(__name__)

mcp = FastMCP("Geopolitical Intelligence Server")

_news_client: NewsApiClient | None = None
_sentiment_analyzer = SentimentIntensityAnalyzer()

GEOPOLITICAL_KEYWORDS = {
    "conflict": ["war", "military", "attack", "missile", "troops", "invasion", "conflict", "bombing"],
    "sanctions": ["sanctions", "embargo", "trade ban", "tariff", "trade war", "restrictions"],
    "political": ["election", "coup", "protest", "regime", "political crisis", "impeachment"],
    "economic": ["recession", "inflation", "default", "debt crisis", "currency crash", "bank collapse"],
    "energy": ["oil crisis", "pipeline", "OPEC", "energy shortage", "gas prices", "oil embargo"],
}

REGION_KEYWORDS = {
    "middle_east": ["Iran", "Israel", "Saudi Arabia", "Iraq", "Syria", "Yemen", "Palestine", "Gaza"],
    "east_asia": ["China", "Taiwan", "North Korea", "South Korea", "Japan"],
    "europe": ["Russia", "Ukraine", "NATO", "EU", "European Union"],
    "south_asia": ["India", "Pakistan", "Afghanistan"],
    "americas": ["US", "United States", "Mexico", "Venezuela", "Brazil"],
}

SECTOR_SENSITIVITY = {
    "energy": {"conflict": 0.9, "sanctions": 0.8, "political": 0.4, "economic": 0.6, "energy": 1.0},
    "defense": {"conflict": 1.0, "sanctions": 0.5, "political": 0.6, "economic": 0.3, "energy": 0.2},
    "technology": {"conflict": 0.4, "sanctions": 0.7, "political": 0.5, "economic": 0.6, "energy": 0.3},
    "finance": {"conflict": 0.5, "sanctions": 0.6, "political": 0.7, "economic": 1.0, "energy": 0.4},
    "healthcare": {"conflict": 0.3, "sanctions": 0.4, "political": 0.5, "economic": 0.5, "energy": 0.2},
    "consumer": {"conflict": 0.3, "sanctions": 0.5, "political": 0.4, "economic": 0.8, "energy": 0.5},
}


def _get_news_client() -> NewsApiClient:
    global _news_client
    if _news_client is None:
        _news_client = NewsApiClient(api_key=NEWS_API_KEY)
    return _news_client


def _analyze_sentiment(text: str) -> dict:
    scores = _sentiment_analyzer.polarity_scores(text)
    return {
        "positive": round(scores["pos"], 3),
        "negative": round(scores["neg"], 3),
        "neutral": round(scores["neu"], 3),
        "compound": round(scores["compound"], 3),
    }


def _categorize_article(title: str, description: str) -> list[str]:
    text = f"{title} {description}".lower()
    categories = []
    for category, keywords in GEOPOLITICAL_KEYWORDS.items():
        if any(kw.lower() in text for kw in keywords):
            categories.append(category)
    return categories if categories else ["general"]


def _detect_regions(title: str, description: str) -> list[str]:
    text = f"{title} {description}"
    regions = []
    for region, keywords in REGION_KEYWORDS.items():
        if any(kw.lower() in text.lower() for kw in keywords):
            regions.append(region)
    return regions if regions else ["global"]


@mcp.tool()
def get_global_news(query: str = "geopolitical", count: int = 10) -> str:
    """Fetch latest global news articles related to a query. Returns headlines, sources, and sentiment."""
    try:
        client = _get_news_client()
        response = client.get_everything(
            q=query,
            language="en",
            sort_by="publishedAt",
            page_size=min(count, 50),
            from_param=(datetime.now() - timedelta(days=3)).strftime("%Y-%m-%d"),
        )

        articles = []
        for art in response.get("articles", [])[:count]:
            title = art.get("title", "")
            desc = art.get("description", "") or ""
            sentiment = _analyze_sentiment(f"{title}. {desc}")
            categories = _categorize_article(title, desc)
            regions = _detect_regions(title, desc)

            articles.append({
                "title": title,
                "source": art.get("source", {}).get("name", "Unknown"),
                "published_at": art.get("publishedAt", ""),
                "description": desc[:300],
                "url": art.get("url", ""),
                "sentiment": sentiment,
                "categories": categories,
                "regions": regions,
            })

        return json.dumps({
            "query": query,
            "count": len(articles),
            "articles": articles,
        })
    except Exception as e:
        return json.dumps({"error": str(e), "query": query})


@mcp.tool()
def get_news_sentiment(query: str = "global economy") -> str:
    """
    Get aggregate sentiment analysis for recent news on a topic.
    Returns overall sentiment and breakdown.
    """
    try:
        client = _get_news_client()
        response = client.get_everything(
            q=query,
            language="en",
            sort_by="publishedAt",
            page_size=30,
            from_param=(datetime.now() - timedelta(days=3)).strftime("%Y-%m-%d"),
        )

        sentiments = []
        for art in response.get("articles", []):
            title = art.get("title", "")
            desc = art.get("description", "") or ""
            score = _analyze_sentiment(f"{title}. {desc}")
            sentiments.append(score["compound"])

        if not sentiments:
            return json.dumps({"error": "No articles found", "query": query})

        avg = sum(sentiments) / len(sentiments)
        positive_count = sum(1 for s in sentiments if s > 0.05)
        negative_count = sum(1 for s in sentiments if s < -0.05)
        neutral_count = len(sentiments) - positive_count - negative_count

        if avg > 0.1:
            overall = "positive"
        elif avg < -0.1:
            overall = "negative"
        else:
            overall = "neutral"

        return json.dumps({
            "query": query,
            "articles_analyzed": len(sentiments),
            "average_sentiment": round(avg, 3),
            "overall": overall,
            "positive_articles": positive_count,
            "negative_articles": negative_count,
            "neutral_articles": neutral_count,
            "most_negative": round(min(sentiments), 3),
            "most_positive": round(max(sentiments), 3),
        })
    except Exception as e:
        return json.dumps({"error": str(e)})


@mcp.tool()
def get_geopolitical_risk_score() -> str:
    """
    Compute a composite geopolitical risk score (0-100).
    0 = calm, 50 = moderate risk, 100 = extreme risk.
    Analyzes multiple geopolitical categories.
    """
    try:
        client = _get_news_client()
        category_scores = {}

        for category, keywords in GEOPOLITICAL_KEYWORDS.items():
            query = " OR ".join(keywords[:4])
            response = client.get_everything(
                q=query,
                language="en",
                sort_by="publishedAt",
                page_size=20,
                from_param=(datetime.now() - timedelta(days=2)).strftime("%Y-%m-%d"),
            )

            articles = response.get("articles", [])
            if not articles:
                category_scores[category] = {"score": 0, "article_count": 0}
                continue

            sentiments = []
            for art in articles:
                title = art.get("title", "")
                desc = art.get("description", "") or ""
                score = _analyze_sentiment(f"{title}. {desc}")
                sentiments.append(score["compound"])

            avg_sentiment = sum(sentiments) / len(sentiments)
            negative_ratio = sum(1 for s in sentiments if s < -0.05) / len(sentiments)

            # Risk = high volume of negative news
            raw_score = (negative_ratio * 60) + (max(0, -avg_sentiment) * 40)
            # Boost by volume (more articles = more significant)
            volume_factor = min(len(articles) / 10, 1.5)
            score = min(raw_score * volume_factor, 100)

            category_scores[category] = {
                "score": round(score, 1),
                "article_count": len(articles),
                "avg_sentiment": round(avg_sentiment, 3),
                "negative_ratio": round(negative_ratio, 2),
            }

        weights = {"conflict": 0.3, "sanctions": 0.2, "political": 0.15, "economic": 0.25, "energy": 0.1}
        composite = sum(
            category_scores.get(cat, {}).get("score", 0) * w
            for cat, w in weights.items()
        )

        if composite < 30:
            level = "low"
            advice = "Markets relatively stable. Normal trading conditions."
        elif composite < 70:
            level = "medium"
            advice = "Elevated geopolitical tensions. Consider hedging and reducing position sizes."
        else:
            level = "high"
            advice = "Significant geopolitical risk. Defensive positioning recommended. Focus on safe-haven assets."

        return json.dumps({
            "composite_score": round(composite, 1),
            "risk_level": level,
            "advice": advice,
            "category_breakdown": category_scores,
            "timestamp": datetime.utcnow().isoformat(),
        })
    except Exception as e:
        return json.dumps({"error": str(e), "composite_score": 50, "risk_level": "unknown"})


@mcp.tool()
def get_region_risk(region: str) -> str:
    """
    Get risk assessment for a specific region.
    Regions: middle_east, east_asia, europe, south_asia, americas
    """
    try:
        keywords = REGION_KEYWORDS.get(region.lower())
        if not keywords:
            available = list(REGION_KEYWORDS.keys())
            return json.dumps({"error": f"Unknown region. Available: {available}"})

        client = _get_news_client()
        query = " OR ".join(keywords[:4]) + " AND (conflict OR crisis OR tension OR military)"
        response = client.get_everything(
            q=query,
            language="en",
            sort_by="publishedAt",
            page_size=20,
            from_param=(datetime.now() - timedelta(days=3)).strftime("%Y-%m-%d"),
        )

        articles = response.get("articles", [])
        if not articles:
            return json.dumps({
                "region": region,
                "risk_score": 10,
                "risk_level": "low",
                "article_count": 0,
            })

        sentiments = []
        key_headlines = []
        for art in articles[:15]:
            title = art.get("title", "")
            desc = art.get("description", "") or ""
            score = _analyze_sentiment(f"{title}. {desc}")
            sentiments.append(score["compound"])
            if score["compound"] < -0.1:
                key_headlines.append(title)

        avg_sent = sum(sentiments) / len(sentiments)
        neg_ratio = sum(1 for s in sentiments if s < -0.05) / len(sentiments)
        risk_score = min((neg_ratio * 60) + (max(0, -avg_sent) * 40), 100)

        if risk_score < 30:
            level = "low"
        elif risk_score < 70:
            level = "medium"
        else:
            level = "high"

        return json.dumps({
            "region": region,
            "risk_score": round(risk_score, 1),
            "risk_level": level,
            "article_count": len(articles),
            "avg_sentiment": round(avg_sent, 3),
            "negative_ratio": round(neg_ratio, 2),
            "key_headlines": key_headlines[:5],
        })
    except Exception as e:
        return json.dumps({"error": str(e)})


@mcp.tool()
def get_sector_impact(sector: str) -> str:
    """
    Analyze how current geopolitical events impact a specific market sector.
    Sectors: energy, defense, technology, finance, healthcare, consumer
    """
    try:
        sensitivity = SECTOR_SENSITIVITY.get(sector.lower())
        if not sensitivity:
            available = list(SECTOR_SENSITIVITY.keys())
            return json.dumps({"error": f"Unknown sector. Available: {available}"})

        risk_data = json.loads(get_geopolitical_risk_score())
        breakdown = risk_data.get("category_breakdown", {})

        weighted_impact = 0
        impact_details = {}
        for category, weight in sensitivity.items():
            cat_score = breakdown.get(category, {}).get("score", 0)
            impact = cat_score * weight
            weighted_impact += impact
            impact_details[category] = {
                "raw_risk": cat_score,
                "sector_sensitivity": weight,
                "impact_score": round(impact, 1),
            }

        max_possible = sum(100 * w for w in sensitivity.values())
        normalized_impact = (weighted_impact / max_possible * 100) if max_possible > 0 else 0

        if normalized_impact < 30:
            outlook = "low_risk"
            recommendation = f"Geopolitical conditions are favorable for {sector} sector."
        elif normalized_impact < 60:
            outlook = "moderate_risk"
            recommendation = f"Some headwinds for {sector} sector. Monitor closely."
        else:
            outlook = "high_risk"
            recommendation = f"Significant geopolitical pressure on {sector} sector. Consider reducing exposure."

        return json.dumps({
            "sector": sector,
            "impact_score": round(normalized_impact, 1),
            "outlook": outlook,
            "recommendation": recommendation,
            "category_impacts": impact_details,
            "overall_geopolitical_risk": risk_data.get("composite_score", 0),
        })
    except Exception as e:
        return json.dumps({"error": str(e)})


@mcp.tool()
def get_conflict_monitor() -> str:
    """Monitor active global conflicts and their potential market impact."""
    conflicts = [
        {"name": "Russia-Ukraine", "region": "europe", "query": "Russia Ukraine war"},
        {"name": "Israel-Palestine", "region": "middle_east", "query": "Israel Palestine Gaza"},
        {"name": "China-Taiwan", "region": "east_asia", "query": "China Taiwan tension"},
        {"name": "Iran-Israel", "region": "middle_east", "query": "Iran Israel conflict"},
        {"name": "India-Pakistan", "region": "south_asia", "query": "India Pakistan tension"},
    ]

    try:
        client = _get_news_client()
        results = []

        for conflict in conflicts:
            response = client.get_everything(
                q=conflict["query"],
                language="en",
                sort_by="publishedAt",
                page_size=10,
                from_param=(datetime.now() - timedelta(days=3)).strftime("%Y-%m-%d"),
            )
            articles = response.get("articles", [])

            if not articles:
                results.append({
                    "conflict": conflict["name"],
                    "region": conflict["region"],
                    "activity_level": "quiet",
                    "risk_score": 5,
                    "article_count": 0,
                })
                continue

            sentiments = []
            headlines = []
            for art in articles:
                title = art.get("title", "")
                desc = art.get("description", "") or ""
                score = _analyze_sentiment(f"{title}. {desc}")
                sentiments.append(score["compound"])
                headlines.append(title)

            avg_sent = sum(sentiments) / len(sentiments)
            neg_ratio = sum(1 for s in sentiments if s < -0.05) / len(sentiments)
            risk = min((neg_ratio * 50) + (max(0, -avg_sent) * 30) + (len(articles) * 2), 100)

            if risk < 25:
                activity = "quiet"
            elif risk < 50:
                activity = "simmering"
            elif risk < 75:
                activity = "escalating"
            else:
                activity = "critical"

            results.append({
                "conflict": conflict["name"],
                "region": conflict["region"],
                "activity_level": activity,
                "risk_score": round(risk, 1),
                "article_count": len(articles),
                "avg_sentiment": round(avg_sent, 3),
                "top_headlines": headlines[:3],
            })

        return json.dumps({
            "conflicts": results,
            "timestamp": datetime.utcnow().isoformat(),
        })
    except Exception as e:
        return json.dumps({"error": str(e)})


if __name__ == "__main__":
    mcp.run(transport="streamable-http", host="localhost", port=8002)
