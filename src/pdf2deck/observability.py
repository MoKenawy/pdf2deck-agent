from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

from .config import Settings


@contextmanager
def langfuse_context(settings: Settings, run_id: str) -> Iterator[dict[str, Any]]:
    """Best-effort Langfuse v4 context for short-lived Gradio executions."""
    if not settings.langfuse_public_key or not settings.langfuse_secret_key:
        yield {}
        return

    try:
        from langfuse import get_client, propagate_attributes
        from langfuse.langchain import CallbackHandler

        client = get_client()
        handler = CallbackHandler()
        with propagate_attributes(
            trace_name="pdf2deck",
            session_id=run_id,
            tags=["pdf2deck", settings.app_env],
            metadata={"run_id": run_id},
        ):
            yield {"callbacks": [handler], "client": client}
        client.flush()
    except Exception:
        # Observability must not take down artifact generation.
        yield {}
