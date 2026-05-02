from app import ai


def test_heuristic_classifies_network_urgent():
    ticket = {
        "subject": "VPN keeps disconnecting",
        "body": "Cisco AnyConnect VPN drops every 5 minutes — production down, urgent.",
        "requester": "alex@acme.com",
    }
    result = ai.heuristic_classify(ticket)
    assert result["category"] == "network"
    assert result["priority"] == "urgent"
    assert 0.0 <= result["confidence"] <= 1.0
    assert len(result["resolution_steps"]) >= 3
    assert "Hi Alex" in result["reply_draft"]
    assert result["source"] == "heuristic"


def test_heuristic_classifies_login():
    ticket = {
        "subject": "Account locked",
        "body": "I can't log in to Okta, my password reset email never arrived.",
        "requester": "user@acme.com",
    }
    result = ai.heuristic_classify(ticket)
    assert result["category"] == "login"


def test_heuristic_classifies_hardware():
    ticket = {
        "subject": "Laptop won't turn on",
        "body": "Dell XPS, no lights, tried different charger.",
        "requester": "jordan@acme.com",
    }
    result = ai.heuristic_classify(ticket)
    assert result["category"] == "hardware"


def test_heuristic_falls_back_to_other():
    ticket = {
        "subject": "Suggestion",
        "body": "Could we get more snacks in the kitchen?",
        "requester": "anon@acme.com",
    }
    result = ai.heuristic_classify(ticket)
    assert result["category"] == "other"


def test_analyze_uses_heuristic_without_key():
    ticket = {"subject": "wifi down", "body": "no internet", "requester": "x@y.com"}
    result = ai.analyze(ticket, api_key="", model="gpt-4o-mini")
    assert result["source"] == "heuristic"
    assert result["category"] == "network"


def test_analyze_falls_back_when_llm_raises(monkeypatch):
    def boom(*args, **kwargs):
        raise RuntimeError("network error")

    monkeypatch.setattr(ai, "llm_classify", boom)
    ticket = {"subject": "password reset", "body": "I forgot my password", "requester": "x@y.com"}
    result = ai.analyze(ticket, api_key="sk-fake", model="gpt-4o-mini")
    assert result["source"] == "heuristic"
    assert result["category"] == "login"
