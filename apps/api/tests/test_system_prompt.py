"""Tests for system prompt builder."""

from app.models.business import Business
from app.services.pipeline.system_prompt import build_system_prompt


def test_build_system_prompt_includes_all_rules():
    """Verify prompt combines business name, instructions, language, tone, and tool rules."""
    biz = Business(
        name="Royal Ethnic Wear",
        system_prompt="We sell premium kurtas and sarees across India.",
        language_pref="hinglish",
        tone="polite and warm",
    )

    prompt = build_system_prompt(biz)

    # 1. Identity & Context
    assert "Royal Ethnic Wear" in prompt
    assert "We sell premium kurtas and sarees across India." in prompt

    # 2. Tone & Language
    assert "polite and warm" in prompt
    assert "hinglish" in prompt
    assert "Hindi" in prompt
    assert "English" in prompt

    # 3. Truthfulness & Tool rules
    assert "NEVER guess" in prompt
    assert "prices" in prompt
    assert "stock" in prompt

    # 4. Human handoff
    assert "HUMAN HANDOFF" in prompt
    assert "WhatsApp" in prompt
