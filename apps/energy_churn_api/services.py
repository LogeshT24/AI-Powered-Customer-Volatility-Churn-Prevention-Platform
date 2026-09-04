"""Assessment, market, and policy services used by the Flask routes."""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import requests

from apps.energy_churn_api.database import Customer

ROOT = Path(__file__).resolve().parents[2]


def customer_record(customer: Customer) -> dict[str, Any]:
    """Convert a SQLAlchemy customer model into the deterministic tool shape."""
    return {column.name: getattr(customer, column.name) for column in Customer.__table__.columns}


def calculate_score(record: dict[str, Any]) -> dict[str, Any]:
    """Calculate transparent score components without an LLM."""
    complaint = min(100, record["repeat_complaints"] * 20 + record["escalations"] * 20 + record["complaint_severity"] * 8)
    timeliness = 100 - record["sla_met_pct"]
    sentiment = min(100, (1 - record["sentiment_score"]) * 50 + max(0, -record["nps_change"]) * 5 + max(0, 75 - record["csat_pct"]))
    behaviour = min(100, record["tariff_comparisons"] * 20 + record["quote_requests"] * 25 + record["direct_debit_cancelled"] * 40 + max(0, 8 - record["app_logins_30d"]) * 5)
    score = round(min(100, 0.25 * complaint + 0.20 * timeliness + 0.20 * sentiment + 0.20 * record["market_risk_index"] + 0.15 * behaviour))
    band = "Critical" if score >= 75 else "High" if score >= 55 else "Watch" if score >= 35 else "Stable"
    return {
        "volatility_score": score,
        "risk_band": band,
        "baseline_churn_probability": round(min(0.95, 0.03 + score / 120), 2),
        "drivers": {"complaint_handling": round(complaint), "resolution_timeliness": round(timeliness), "sentiment": round(sentiment), "market_impact": round(record["market_risk_index"]), "customer_behaviour": round(behaviour)},
    }


def sentiment_summary(record: dict[str, Any]) -> dict[str, Any]:
    """Safe deterministic fallback until the Neuro SAN Sentiment Agent is invoked."""
    value = float(record["sentiment_score"])
    label = "negative" if value < -0.2 else "positive" if value > 0.2 else "neutral"
    theme = "unresolved service experience" if record["repeat_complaints"] else "general account experience"
    return {"label": label, "urgency": "high" if value < -0.5 else "normal", "themes": [theme], "model_status": "Agent analysis available in Neuro SAN chat"}


def intervention(record: dict[str, Any]) -> dict[str, Any]:
    """Return non-automated intervention and policy lookup terms."""
    if record["direct_debit_cancelled"] or record["payment_days_late"] > 14:
        action, query = "Human-led payment-support review", "payment direct debit arrears vulnerability"
    elif record["repeat_complaints"] >= 3 or record["escalations"] >= 1:
        action, query = "Senior complaint-owner callback within 24 hours", "repeat complaint escalation callback"
    elif record["tariff_comparisons"] >= 2 or record["quote_requests"] >= 1:
        action, query = "Human-approved tariff and loyalty review", "tariff quote comparison discount"
    else:
        action, query = "Proactive service check-in; no commercial offer", "complaint customer contact"
    return {"recommended_action": action, "policy_query": query, "approval_required": True, "guardrail": "AI recommendation only. A trained colleague must approve and record every action."}


def policy_citations(query: str) -> list[dict[str, str]]:
    """Use local persistent Chroma retrieval; retain a source-file fallback for setup failures."""
    files = list((ROOT / "data" / "policies").glob("*.md"))
    try:
        import chromadb
        from chromadb.utils.embedding_functions import OpenAIEmbeddingFunction

        api_key = os.getenv("OPENAI_API_KEY")
        if api_key and os.getenv("POLICY_VECTOR_ENABLED", "false").lower() == "true":
            client = chromadb.PersistentClient(path=str(ROOT / "data" / "policy_chroma"))
            embedding = OpenAIEmbeddingFunction(api_key=api_key, model_name=os.getenv("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small"))
            collection = client.get_or_create_collection("energy_policies", embedding_function=embedding)
            if not collection.count():
                collection.add(ids=[path.stem for path in files], documents=[path.read_text(encoding="utf-8") for path in files], metadatas=[{"document": path.stem.replace("_", " ").title(), "version": "1.0-demo"} for path in files])
            result = collection.query(query_texts=[query], n_results=min(3, collection.count()))
            return [{"document": meta["document"], "section": "Retrieved policy excerpt", "version": meta["version"], "path": "data/policies"} for meta in result["metadatas"][0]]
    except (ImportError, ValueError, RuntimeError, OSError):
        # The deterministic fallback keeps the live demo usable before policy indexing.
        pass
    tokens = set(query.lower().split())
    ranked = sorted(files, key=lambda path: len(tokens.intersection(set(path.read_text(encoding="utf-8").lower().split()))), reverse=True)[:3]
    return [{"document": path.stem.replace("_", " ").title(), "section": "Demo guidance", "version": "1.0-demo", "path": str(path.relative_to(ROOT))} for path in ranked if path.exists()]


def fallback_market() -> dict[str, Any]:
    """Load the reliable packaged snapshot."""
    return json.loads((ROOT / "data" / "market_fallback.json").read_text(encoding="utf-8"))


def live_market() -> dict[str, Any]:
    """Fetch one small public price response; never fail the dashboard on an API outage."""
    try:
        response = requests.get("https://api.energy-charts.info/v2/price_current", params={"bzn": "GB"}, timeout=int(os.getenv("MARKET_HTTP_TIMEOUT_SECONDS", "5")))
        response.raise_for_status()
        payload = response.json()
        values = payload.get("data", [{}])[0].get("values", {})
        price = next(iter(values.values())) if values else None
        if price is None:
            raise ValueError("No current price in response")
        snapshot = {"market_risk_index": min(100, max(0, round(float(price) / 2))), "price_eur_mwh": round(float(price), 2), "price_change_pct": 0.0, "source": "Energy-Charts API (Fraunhofer ISE)", "source_mode": "live", "retrieved_at": datetime.now(timezone.utc).isoformat()}
        return snapshot
    except (requests.RequestException, ValueError, KeyError, TypeError):
        return fallback_market()
