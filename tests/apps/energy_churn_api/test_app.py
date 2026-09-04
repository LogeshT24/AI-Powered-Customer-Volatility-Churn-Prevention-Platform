"""API checks for the synthetic Energy Retention Command Centre."""

from apps.energy_churn_api.app import create_app


def test_customer_detail_exposes_explainable_risk_and_policy_citation():
    """Critical Customer B exposes score components and a safe recommendation."""
    client = create_app().test_client()
    response = client.get("/api/customers/C-1002")

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["risk_band"] == "Critical"
    assert payload["drivers"]["complaint_handling"] > 0
    assert payload["intervention"]["approval_required"] is True
    assert payload["intervention"]["policy_citations"]


def test_intervention_status_is_validated():
    """Only the four adviser-owned states may be recorded."""
    client = create_app().test_client()

    assert client.post("/api/interventions/C-1002", json={"status": "invalid"}).status_code == 400
    assert client.post("/api/interventions/C-1002", json={"status": "approved"}).status_code == 200


def test_dashboard_exposes_portfolio_summary():
    """Portfolio endpoint remains deterministic and usable without Neuro SAN chat."""
    client = create_app().test_client()
    payload = client.get("/api/dashboard").get_json()

    assert payload["portfolio_size"] == 8
    assert len(payload["priority_queue"]) == 5
    assert set(payload["distribution"]) == {"Stable", "Watch", "High", "Critical"}
