from app.core.config import settings
from app.shared.ai.providers.omniroute import estimate_cost


def test_chatbot_defaults_match_spec():
    assert settings.CHATBOT_MODEL == "grok-chat"
    assert settings.CHATBOT_MAX_MESSAGE_CHARS == 500
    assert settings.CHATBOT_RATE_LIMIT_PER_MIN == 8
    assert settings.CHATBOT_HISTORY_TURNS == 10
    assert settings.CHATBOT_SESSION_TTL_SECONDS == 1800
    assert settings.CHATBOT_KNOWLEDGE_TTL_SECONDS == 300
    assert settings.CHATBOT_MAX_OUTPUT_TOKENS == 500


def test_grok_cost_is_not_zero():
    assert estimate_cost("grok-chat", 1_000_000, 1_000_000) > 0
    assert estimate_cost("grok-4-fast-non-reasoning", 1_000_000, 0) > 0
