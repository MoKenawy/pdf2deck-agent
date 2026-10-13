from pathlib import Path

from pydantic import ValidationError

from .schemas import StylePreferences


def load_preferences(path: Path) -> StylePreferences:
    """Read a JSON preferences file, naming every invalid field if it does not validate."""
    try:
        return StylePreferences.model_validate_json(path.read_bytes())
    except OSError as exc:
        raise ValueError(f"Could not read preferences file {path.name}: {exc}") from exc
    except ValidationError as exc:
        problems = "\n".join(
            f"- {'.'.join(str(part) for part in error['loc']) or 'file'}: {error['msg']}"
            for error in exc.errors()
        )
        raise ValueError(f"Invalid preferences file {path.name}:\n{problems}") from exc
