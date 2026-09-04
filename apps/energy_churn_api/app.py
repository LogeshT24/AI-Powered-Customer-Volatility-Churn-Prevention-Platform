"""HTTP API for the React Energy Retention Command Centre."""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone

import requests
from flask import Flask, jsonify, request
from flask_cors import CORS

from apps.energy_churn_api.database import Assessment, Customer, Intervention, MarketSnapshot, get_session, seed_database
from apps.energy_churn_api.services import calculate_score, customer_record, intervention, live_market, policy_citations, sentiment_summary


def create_app() -> Flask:
    """Create a configured Flask app."""
    seed_database()
    app = Flask(__name__)
    CORS(app)

    def assess(customer: Customer) -> dict:
        record = customer_record(customer)
        score = calculate_score(record)
        recommendation = intervention(record)
        return {"customer_id": customer.customer_id, "customer360": record, **score, "sentiment": sentiment_summary(record), "intervention": {**recommendation, "policy_citations": policy_citations(recommendation["policy_query"])}}

    @app.get("/api/customers")
    def customers():
        with get_session() as session:
            results = [assess(customer) for customer in session.query(Customer).all()]
        return jsonify(sorted(results, key=lambda item: item["volatility_score"], reverse=True))

    @app.get("/api/customers/<customer_id>")
    def customer_detail(customer_id: str):
        with get_session() as session:
            customer = session.get(Customer, customer_id)
            if not customer:
                return jsonify({"error": "Unknown synthetic customer"}), 404
            return jsonify(assess(customer))

    @app.post("/api/customers/<customer_id>/assess")
    def refresh_assessment(customer_id: str):
        with get_session() as session:
            customer = session.get(Customer, customer_id)
            if not customer:
                return jsonify({"error": "Unknown synthetic customer"}), 404
            result = assess(customer)
            session.add(Assessment(customer_id=customer_id, volatility_score=result["volatility_score"], risk_band=result["risk_band"], churn_probability=result["baseline_churn_probability"], drivers_json=json.dumps(result["drivers"]), sentiment_label=result["sentiment"]["label"], recommendation=result["intervention"]["recommended_action"]))
            session.commit()
            return jsonify(result)

    @app.post("/api/interventions/<customer_id>")
    def update_intervention(customer_id: str):
        payload = request.get_json(silent=True) or {}
        if payload.get("status") not in {"pending", "approved", "completed", "declined"}:
            return jsonify({"error": "status must be pending, approved, completed, or declined"}), 400
        with get_session() as session:
            item = session.query(Intervention).filter_by(customer_id=customer_id).one_or_none() or Intervention(customer_id=customer_id)
            item.status, item.adviser_note, item.updated_at = payload["status"], payload.get("adviser_note", ""), datetime.now(timezone.utc)
            session.add(item)
            session.commit()
            return jsonify({"customer_id": customer_id, "status": item.status, "adviser_note": item.adviser_note})

    @app.get("/api/market")
    def market():
        snapshot = live_market()
        with get_session() as session:
            stored_snapshot = dict(snapshot)
            stored_snapshot["retrieved_at"] = datetime.fromisoformat(stored_snapshot["retrieved_at"].replace("Z", "+00:00"))
            session.add(MarketSnapshot(**stored_snapshot))
            session.commit()
        return jsonify(snapshot)

    @app.get("/api/dashboard")
    def dashboard():
        with get_session() as session:
            results = [assess(customer) for customer in session.query(Customer).all()]
            intervention_states = {item.customer_id: item.status for item in session.query(Intervention).all()}
        distribution = {band: sum(item["risk_band"] == band for item in results) for band in ["Stable", "Watch", "High", "Critical"]}
        pending = sum(item["risk_band"] in {"Critical", "High"} and intervention_states.get(item["customer_id"], "pending") == "pending" for item in results)
        return jsonify({"portfolio_size": len(results), "average_volatility": round(sum(item["volatility_score"] for item in results) / len(results), 1), "critical_or_high": distribution["Critical"] + distribution["High"], "interventions_pending": pending, "distribution": distribution, "priority_queue": sorted(results, key=lambda item: item["volatility_score"], reverse=True)[:5]})

    @app.post("/api/chat")
    def chat():
        """Proxy chat only when a local Neuro SAN server is running."""
        endpoint = os.getenv("NEURO_SAN_CHAT_URL", "")
        if not endpoint:
            return jsonify({"error": "Start Neuro SAN and set NEURO_SAN_CHAT_URL to enable agent chat."}), 503
        try:
            response = requests.post(endpoint, json=request.get_json(silent=True) or {}, timeout=30)
            return jsonify(response.json()), response.status_code
        except requests.RequestException:
            return jsonify({"error": "Neuro SAN is unavailable. Dashboard data remains available."}), 503

    return app


if __name__ == "__main__":
    create_app().run(port=int(os.getenv("FLASK_PORT", "5000")), debug=True)
