import re

import commands.config as config

_FAKE_TOOL_RE = re.compile(
    r"script\s+(?:was\s+)?(?:created|saved|generated|written|initiated)"
    r"|(?:created|saved|generated|wrote)\s+\w+\.py"
    r"|(?:here(?:'s| is| are)\s+(?:the\s+)?(?:list|result|output).*\.py)"
    r"|(?:I (?:ran|executed|run|generate|created)\s+(?:a\s+)?(?:the\s+)?(?:script|\w+\.py))"
    r"|(?:generate\s+(?:a\s+)?script)"
    r"|prints?\s+(?:the\s+)?first\s+\w+\s+\w+\s+numbers",
    re.IGNORECASE,
)

_LIMITATION_RE = re.compile(
    r"\b(i can(?:not|'t)|i do not|i don't|i am unable|i'm unable|i cannot|not able|can't access)\b",
    re.IGNORECASE,
)
_SUGGESTION_RE = re.compile(
    r"\b(you could|you can|instead|try|use\s+web_search|use\s+the\s+\w+\s+tool|call\s+\w+)\b",
    re.IGNORECASE,
)


def looks_like_fake_tool_use(text: str) -> bool:
    return bool(_FAKE_TOOL_RE.search(text))


def looks_like_limitation_or_suggestion(text: str) -> bool:
    has_limitation = bool(_LIMITATION_RE.search(text))
    has_suggestion = bool(_SUGGESTION_RE.search(text))
    return has_limitation and has_suggestion


def should_run_plan_round(full_text: str) -> bool:
    if not getattr(config, "CPU_MODE_PLAN_FIRST", True):
        return False

    lowered = full_text.lower()
    words = lowered.split()

    if any(
        phrase in lowered
        for phrase in (
            "list scripts",
            "list script",
            "show scripts",
            "what scripts",
            "which scripts",
        )
    ):
        return False

    action_terms = {"execute", "run", "test", "build", "create", "generate", "write"}
    script_terms = {"script", "python", "program"}
    if any(term in words for term in action_terms) and any(term in words for term in script_terms):
        return True

    complex_terms = {"estimate", "forecast", "calculate", "compare", "analyze", "research", "find"}
    if len(words) >= 10 and any(term in words for term in complex_terms):
        return True

    return False
