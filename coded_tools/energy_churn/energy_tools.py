"""Deterministic, PII-free demo tools for the Energy Retention Command Centre."""
import csv
import json
from pathlib import Path
from typing import Any, Dict

from neuro_san.interfaces.coded_tool import CodedTool

DATA_FILE = Path(__file__).resolve().parents[2] / "data" / "energy_churn_demo.csv"


def _records() -> Dict[str, Dict[str, Any]]:
    with DATA_FILE.open(newline="", encoding="utf-8") as source:
        return {row["customer_id"]: row for row in csv.DictReader(source)}


def _number(record: Dict[str, Any], name: str) -> float:
    return float(record[name])


def _score(record: Dict[str, Any]) -> Dict[str, Any]:
    # Each component is normalised to 0-100 before applying the agreed weights.
    complaint_handling = min(100, _number(record, "repeat_complaints") * 20 + _number(record, "escalations") * 20 + _number(record, "complaint_severity") * 8)
    timeliness = 100 - _number(record, "sla_met_pct")
    sentiment = min(100, (1 - _number(record, "sentiment_score")) * 50 + max(0, -_number(record, "nps_change")) * 5 + max(0, 75 - _number(record, "csat_pct")))
    market = _number(record, "market_risk_index")
    behaviour = min(100, _number(record, "tariff_comparisons") * 20 + _number(record, "quote_requests") * 25 + _number(record, "direct_debit_cancelled") * 40 + max(0, 8 - _number(record, "app_logins_30d")) * 5)
    raw = (0.25 * complaint_handling + 0.20 * timeliness + 0.20 * sentiment + 0.20 * market + 0.15 * behaviour)
    volatility = round(min(100, raw))
    band = "Critical" if volatility >= 75 else "High" if volatility >= 55 else "Watch" if volatility >= 35 else "Stable"
    churn_probability = round(min(0.95, 0.03 + volatility / 120), 2)
    drivers = {"complaint_handling": round(complaint_handling), "resolution_timeliness": round(timeliness), "sentiment": round(sentiment), "market_impact": round(market), "customer_behaviour": round(behaviour)}
    return {"volatility_score": volatility, "risk_band": band, "baseline_churn_probability": churn_probability, "drivers": drivers}


def _get(customer_id: str) -> Dict[str, Any]:
    record = _records().get(customer_id)
    if not record:
        raise ValueError("Unknown customer_id. Use a demo ID such as C-1002.")
    return record


class Customer360Tool(CodedTool):
    def invoke(self, args: Dict[str, Any], sly_data: Dict[str, Any]):
        record = _get(args["customer_id"])
        safe = {key: value for key, value in record.items() if key not in {"customer_id"}}
        return json.dumps({"customer_id": args["customer_id"], "customer360": safe}, indent=2)


class VolatilityScoreTool(CodedTool):
    def invoke(self, args: Dict[str, Any], sly_data: Dict[str, Any]):
        record = _get(args["customer_id"])
        return json.dumps({"customer_id": args["customer_id"], **_score(record), "formula": "25% complaint handling + 20% resolution timeliness + 20% sentiment + 20% market impact + 15% customer behaviour"}, indent=2)


class InterventionTool(CodedTool):
    def invoke(self, args: Dict[str, Any], sly_data: Dict[str, Any]):
        record = _get(args["customer_id"])
        assessment = _score(record)
        if _number(record, "direct_debit_cancelled") or _number(record, "payment_days_late") > 14:
            action = "Human-led payment-support review"
            policy = "Payment Support Guidance v1.0-demo"
        elif _number(record, "repeat_complaints") >= 3 or _number(record, "escalations") >= 1:
            action = "Senior complaint-owner callback within 24 hours"
            policy = "Complaint Escalation Policy v1.0-demo"
        elif _number(record, "tariff_comparisons") >= 2 or _number(record, "quote_requests") >= 1:
            action = "Human-approved tariff and loyalty review"
            policy = "Tariff and Loyalty Review Policy v1.0-demo"
        else:
            action = "Proactive service check-in; no commercial offer"
            policy = "Complaint Escalation Policy v1.0-demo"
        return json.dumps({"customer_id": args["customer_id"], "risk_band": assessment["risk_band"], "recommended_action": action, "policy_reference": policy, "guardrail": "Recommendation only: trained colleague must approve and record the outcome."}, indent=2)


class PortfolioDashboardTool(CodedTool):
    def invoke(self, args: Dict[str, Any], sly_data: Dict[str, Any]):
        scored = [{"customer_id": key, **_score(value)} for key, value in _records().items()]
        priority = sorted(scored, key=lambda item: item["volatility_score"], reverse=True)
        return json.dumps({"portfolio_size": len(scored), "average_volatility": round(sum(item["volatility_score"] for item in scored) / len(scored), 1), "critical_or_high": sum(item["risk_band"] in {"Critical", "High"} for item in scored), "priority_queue": priority[:5], "model_status": "Deterministic demo baseline — not a production ML model."}, indent=2)
