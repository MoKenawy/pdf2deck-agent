from dataclasses import dataclass

from .prompts import OUTLINE_SYSTEM, OUTLINE_USER, REVISION_SYSTEM


@dataclass(frozen=True)
class PromptSkill:
    name: str
    version: str
    system: str
    user_template: str


OUTLINE_SKILL = PromptSkill(
    name="chapter-to-outline",
    version="1.0.0",
    system=OUTLINE_SYSTEM,
    user_template=OUTLINE_USER,
)

REVISION_SKILL = PromptSkill(
    name="outline-revision",
    version="1.0.0",
    system=REVISION_SYSTEM,
    user_template="{content}",
)
