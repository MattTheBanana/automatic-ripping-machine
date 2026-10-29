import json
from unittest.mock import Mock, patch

from arm.ui.metadata import smart_title_candidate


def test_optional_model_can_choose_franchise_title_over_exact_short_match():
    candidates = [
        {
            "Title": "Catching Fire",
            "Year": "2020",
            "Type": "movie",
            "Plot": "An independent film with a similar title.",
        },
        {
            "Title": "The Hunger Games: Catching Fire",
            "Year": "2013",
            "Type": "movie",
            "Plot": "Katniss Everdeen competes in the Quarter Quell.",
            "popularity": 80.0,
            "vote_count": 12000,
        },
    ]
    response = Mock()
    response.raise_for_status.return_value = None
    response.json.return_value = {
        "message": {"content": json.dumps({"index": 1, "confidence": 0.94})}
    }

    with patch("arm.ui.metadata.requests.post", return_value=response) as post:
        selected = smart_title_candidate(
            candidates,
            query="Catching Fire",
            label="Catching Fire",
            endpoint="http://ollama:11434",
            model="qwen2.5:3b",
        )

    assert selected == candidates[1]
    assert post.call_args.args[0] == "http://ollama:11434/api/chat"
    request_payload = post.call_args.kwargs["json"]
    assert request_payload["stream"] is False
    assert "The Hunger Games: Catching Fire" in request_payload["messages"][1]["content"]


def test_optional_model_rejects_unconfident_or_invalid_candidate():
    candidates = [{"Title": "Catching Fire", "Year": "2020", "Type": "movie"}]
    response = Mock()
    response.raise_for_status.return_value = None
    response.json.return_value = {
        "message": {"content": json.dumps({"index": 0, "confidence": 0.2})}
    }
    with patch("arm.ui.metadata.requests.post", return_value=response):
        assert smart_title_candidate(
            candidates, query="Catching Fire", endpoint="http://ollama:11434", model="qwen2.5:3b"
        ) is None

    response.json.return_value = {
        "message": {"content": json.dumps({"index": 5, "confidence": 0.99})}
    }
    with patch("arm.ui.metadata.requests.post", return_value=response):
        assert smart_title_candidate(
            candidates, query="Catching Fire", endpoint="http://ollama:11434", model="qwen2.5:3b"
        ) is None


def test_optional_model_is_a_noop_without_endpoint_or_candidates():
    assert smart_title_candidate([], query="Catching Fire", endpoint="http://ollama:11434",
                                 model="qwen2.5:3b") is None
    assert smart_title_candidate([{"Title": "Catching Fire"}], query="Catching Fire",
                                 endpoint="", model="qwen2.5:3b") is None
