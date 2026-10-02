import pytest
from pydantic import ValidationError

from pdf2deck.schemas import StylePreferences


def test_style_rejects_unknown_fields():
    with pytest.raises(ValidationError):
        StylePreferences(unknown="x")


def test_style_validates_density():
    style = StylePreferences(density="dense")
    assert style.density == "dense"
