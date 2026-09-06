"""API checks for the synthetic Energy Retention Command Centre."""

from unittest.mock import Mock

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


def test_dashboard_chat_proxies_question_to_local_energy_agent(monkeypatch):
    """The dashboard sends a browser-safe question to the local Neuro SAN endpoint."""
    response = Mock(ok=True)
    response.json.return_value = {"messages": [{"message": {"text": "C-1002 is Critical risk."}}]}
    post = Mock(return_value=response)
    monkeypatch.setattr("apps.energy_churn_api.app.requests.post", post)

    payload = create_app().test_client().post("/api/chat", json={"message": "Give me details of C-1002"})

    assert payload.status_code == 200
    assert payload.get_json() == {"answer": "C-1002 is Critical risk."}
    assert post.call_args.kwargs["json"] == {"user_message": {"text": "Give me details of C-1002"}}


def test_dashboard_chat_requires_a_question():
    """Blank dashboard requests do not call the agent server."""
    response = create_app().test_client().post("/api/chat", json={"message": " "})

    assert response.status_code == 400


def test_dashboard_chat_returns_customer_fallback_when_agent_is_unavailable(monkeypatch):
    """Provider quota/connection errors still produce a safe deterministic assessment."""
    response = Mock(ok=False)
    response.json.return_value = {"error": {"message": "RESOURCE_EXHAUSTED"}}
    monkeypatch.setattr("apps.energy_churn_api.app.requests.post", Mock(return_value=response))

    result = create_app().test_client().post("/api/chat", json={"message": "Give me details", "customer_id": "C-1002"})

    assert result.status_code == 200
    assert result.get_json()["fallback"] is True
    assert "C-1002: Critical risk" in result.get_json()["answer"]
