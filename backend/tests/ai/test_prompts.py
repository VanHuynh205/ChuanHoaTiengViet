"""Tests for app.ai.prompts."""

from __future__ import annotations

from string import Template

import pytest

from app.ai.prompts import (
    DIACRITIC_RESTORE_TEMPLATE,
    PHRASE_DISAMBIGUATE_TEMPLATE,
    render,
)


@pytest.mark.unit
def test_render_substitutes_all_placeholders() -> None:
    template = Template("Hello $name, $greeting!")
    out = render(template, {"name": "Linh", "greeting": "chào"})
    assert out == "Hello Linh, chào!"


@pytest.mark.unit
def test_render_missing_placeholder_raises() -> None:
    template = Template("Need $a and $b")
    with pytest.raises(KeyError):
        render(template, {"a": "1"})


@pytest.mark.unit
def test_diacritic_template_has_required_placeholders() -> None:
    out = render(
        DIACRITIC_RESTORE_TEMPLATE,
        {
            "few_shot_examples": "- toi -> tôi\n- com -> cơm",
            "input_text": "toi an com",
        },
    )
    assert "toi an com" in out
    assert "toi -> tôi" in out
    assert "$" not in out


@pytest.mark.unit
def test_phrase_disambiguate_template_renders() -> None:
    out = render(
        PHRASE_DISAMBIGUATE_TEMPLATE,
        {
            "context": "Hôm nay tôi đk hp.",
            "phrase": "đk hp",
            "options": "1) đăng ký học phần\n2) địa kiến học phần",
        },
    )
    assert "đk hp" in out
    assert "đăng ký học phần" in out
    assert "$" not in out
