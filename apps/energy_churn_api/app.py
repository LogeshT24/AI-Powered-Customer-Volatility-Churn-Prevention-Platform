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


def _neuro_san_chat_url() -> str:
    """Return the local Energy Churn endpoint, unless explicitly overridden."""
    configured_url = os.getenv("NEURO_SAN_CHAT_URL", "").strip()
    if configured_url:
        return configured_url
    base_url = os.getenv("NEURO_SAN_BASE_URL", "http://127.0.0.1:8080").rstrip("/")
    return f"{base_url}/api/v1/energy_churn/streaming_chat"


def _response_text(value: object) -> str:
    """Extract a displayable answer from Neuro SAN's nested chat response."""
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        return "\n".join(part for item in value if (part := _response_text(item)))
    if isinstance(value, dict):
        text = value.get("text")
        if isinstance(text, str):
            return text
        for key in ("message", "messages", "response", "content", "error"):
            if key in value and (result := _response_text(value[key])):
                return result
    return ""


def _is_agent_error(answer: str) -> bool:
    """Detect provider failures returned as a successful streaming-chat response."""
    error_markers = ("agent stopped due to exception", "resource_exhausted", "quota", "api key", "connection error")
    return any(marker in answer.lower() for marker in error_markers)


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
        """Send a dashboard question to the local Energy Churn agent network."""
        payload = request.get_json(silent=True) or {}
        message = str(payload.get("message", "")).strip()
        if not message:
            return jsonify({"error": "Enter a question for the Energy Churn agent."}), 400

        def fallback(reason: str):
            customer_id = str(payload.get("customer_id", "")).strip()
            with get_session() as session:
                customer = session.get(Customer, customer_id)
                if not customer:
                    return None
                assessment = assess(customer)
            primary_driver = max(assessment["drivers"], key=assessment["drivers"].get).replace("_", " ")
            answer = (
                f"Fallback assessment for {customer_id}: {assessment['risk_band']} risk, "
                f"{assessment['volatility_score']}/100 volatility and "
                f"{assessment['baseline_churn_probability']:.0%} baseline churn probability. "
                f"Primary driver: {primary_driver} ({assessment['drivers'][primary_driver.replace(' ', '_')]}/100). "
                f"Recommended human-approved action: {assessment['intervention']['recommended_action']}."
            )
            return jsonify({"answer": answer, "fallback": True, "fallback_reason": reason})

        try:
            response = requests.post(
                _neuro_san_chat_url(),
                json={"user_message": {"text": message}},
                timeout=90,
            )
            response_payload = response.json()
            if not response.ok:
                fallback_response = fallback("The AI provider was unavailable.")
                if fallback_response is not None:
                    return fallback_response
                return jsonify({"error": _response_text(response_payload) or "Neuro SAN could not process the request."}), 502
            answer = _response_text(response_payload)
            if not answer or _is_agent_error(answer):
                fallback_response = fallback("The AI provider could not complete the request.")
                if fallback_response is not None:
                    return fallback_response
                return jsonify({"error": "Neuro SAN returned no readable agent response."}), 502
            return jsonify({"answer": answer})
        except (requests.RequestException, ValueError):
            fallback_response = fallback("Neuro SAN could not be reached.")
            if fallback_response is not None:
                return fallback_response
            return jsonify({"error": "Neuro SAN is unavailable. Start `ns run` and try again."}), 503

    return app


if __name__ == "__main__":
    create_app().run(port=int(os.getenv("FLASK_PORT", "5000")), debug=True)
