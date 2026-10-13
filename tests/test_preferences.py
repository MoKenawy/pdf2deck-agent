from pathlib import Path

import pytest

from pdf2deck.preferences import load_preferences


def _write(tmp_path: Path, content: str) -> Path:
    path = tmp_path / "preferences.json"
    path.write_text(content, encoding="utf-8")
    return path


def test_loads_a_partial_file_and_defaults_the_rest(tmp_path: Path):
    path = _write(tmp_path, '{"name": "brand", "colors": {"main": "#32AEB8"}}')

    style = load_preferences(path)

    assert style.name == "brand"
    assert style.colors.main == "#32AEB8"
    assert style.colors.background == "#FFFFFF"
    assert style.fonts.body == "Aptos"


def test_names_every_invalid_field(tmp_path: Path):
    path = _write(tmp_path, '{"colours": {}, "colors": {"main": "teal"}}')

    with pytest.raises(ValueError) as error:
        load_preferences(path)

    message = str(error.value)
    assert "Invalid preferences file preferences.json" in message
    assert "- colours:" in message
    assert "- colors.main:" in message


def test_rejects_a_file_that_is_not_json(tmp_path: Path):
    path = _write(tmp_path, "name: brand")

    with pytest.raises(ValueError, match="Invalid preferences file preferences.json"):
        load_preferences(path)


def test_reports_a_missing_file(tmp_path: Path):
    with pytest.raises(ValueError, match="Could not read preferences file missing.json"):
        load_preferences(tmp_path / "missing.json")
