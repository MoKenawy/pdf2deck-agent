import pytest
from pydantic import ValidationError

from pdf2deck.schemas import Fonts, Palette, StylePreferences


def test_style_rejects_unknown_fields():
    with pytest.raises(ValidationError):
        StylePreferences(unknown="x")


def test_style_validates_density():
    style = StylePreferences(density="dense")
    assert style.density == "dense"


def test_style_rejects_unknown_nested_fields():
    with pytest.raises(ValidationError):
        StylePreferences.model_validate({"colors": {"primary": "#112233"}})


@pytest.mark.parametrize("color", ["112233", "#12345", "#GGGGGG", "teal"])
def test_palette_rejects_colors_that_are_not_hex(color):
    with pytest.raises(ValidationError):
        Palette(main=color)


def test_style_round_trips_through_json():
    style = StylePreferences(
        name="brand",
        colors=Palette(main="#32AEB8", highlight="#F2A40D"),
        fonts=Fonts(heading="Arial", body="Georgia"),
    )
    assert StylePreferences.model_validate_json(style.model_dump_json()) == style
