"""Agent repair contract: a stable code, a plain-language fix, and a docs
pointer on every expected failure. Modelled on Solid 2.0's agent diagnostics.
"""

from __future__ import annotations

from dataclasses import dataclass

DOCS = "docs/diagnostics.md"

CATALOG: dict[str, str] = {
    "SUP_INPUT_EMPTY": "send non-blank text for the required field",
    "SUP_INPUT_TOO_LARGE": "shorten the input to 8,000 chars or less",
    "SUP_NO_SKILLS": "name concrete skills in the JD/topic; the extractor returned none",
    "SUP_TOOL_UNKNOWN": "use one of the tools advertised by the supervisor",
    "SUP_DELEGATION_FAILED": "check the skills-agent/engine is running and retry",
}


@dataclass(frozen=True)
class Diagnostic(ValueError):
    """A caller-fixable failure. Inherits ValueError so existing handlers work."""

    code: str
    message: str

    def __post_init__(self) -> None:
        if self.code not in CATALOG:
            raise ValueError(f"undocumented diagnostic code: {self.code}")

    @property
    def hint(self) -> str:
        return CATALOG[self.code]

    @property
    def docs(self) -> str:
        return f"{DOCS}#{self.code.casefold()}"

    def to_dict(self) -> dict:
        return {
            "code": self.code,
            "message": self.message,
            "hint": self.hint,
            "docs": self.docs,
        }

    def __str__(self) -> str:
        return f"[{self.code}] {self.message} (fix: {self.hint}) (docs: {self.docs})"
