from langchain_openai import ChatOpenAI

from ..config import Settings
from ..prompts import OUTLINE_SYSTEM, OUTLINE_USER, REVISION_SYSTEM
from ..schemas import DeckOutline, SourceDocument


class LlmService:
    def __init__(self, settings: Settings) -> None:
        self.model = ChatOpenAI(
            model=settings.model_name,
            temperature=settings.model_temperature,
            api_key=settings.openai_api_key,
            base_url=settings.openai_base_url,
        )

    def create_outline(
        self,
        document: SourceDocument,
        tone: str,
        density: str,
        max_slides: int,
    ) -> DeckOutline:
        prompt = OUTLINE_USER.format(
            tone=tone,
            density=density,
            max_slides=max_slides,
            source=source_text(document),
        )
        structured = self.model.with_structured_output(DeckOutline)
        return structured.invoke(
            [
                ("system", OUTLINE_SYSTEM),
                ("human", prompt),
            ]
        )

    def revise_outline(self, outline: DeckOutline, document: SourceDocument) -> DeckOutline:
        prompt = (
            f"{REVISION_SYSTEM}\n\nCURRENT OUTLINE:\n"
            f"{outline.model_dump_json(indent=2)}\n\nSOURCE:\n{source_text(document)}"
        )
        structured = self.model.with_structured_output(DeckOutline)
        return structured.invoke([("system", REVISION_SYSTEM), ("human", prompt)])


def source_text(document: SourceDocument) -> str:
    return "\n\n".join(f"[page {page.number}]\n{page.text.strip()}" for page in document.pages)
