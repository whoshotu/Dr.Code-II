import ast
import re
from typing import Any
from generators.no_slop import sanitize_mermaid_output

from generators.test_generator import extract_functions, call_llm_for_tests


def build_diagram_prompt(
    code: str,
    language: str,
    diagram_type: str,
) -> str:
    lang = language.lower()

    prompt = f"""Generate a Mermaid {diagram_type} diagram for the following {lang} code.

Source Code:
```{lang}
{code}
```

Generate Mermaid diagram syntax that shows:
- Participants/classes involved
- Function calls or relationships between components
- Data flow

Return ONLY the Mermaid diagram syntax, wrapped in ```mermaid``` code blocks if needed. No explanations."""

    return prompt


def generate_diagram(
    code: str,
    language: str,
    diagram_type: str = "sequence",
    sanitizer_enabled: bool = True,
) -> dict[str, Any]:
    functions = extract_functions(code, language)

    if not functions:
        return {
            "success": False,
            "error": "No functions found in code",
            "diagram_syntax": "",
            "diagram_type": diagram_type,
        }

    prompt = build_diagram_prompt(code, language, diagram_type)

    diagram_syntax: str | None = call_llm_for_tests(prompt)
    if sanitizer_enabled and diagram_syntax is not None:
        diagram_syntax = sanitize_mermaid_output(diagram_syntax)

    if not diagram_syntax:
        return {
            "success": False,
            "error": "Failed to generate diagram - LLM unavailable",
            "diagram_syntax": "",
            "diagram_type": diagram_type,
        }

    diagram_syntax = diagram_syntax.strip()
    if "```mermaid" in diagram_syntax:
        diagram_syntax = diagram_syntax.split("```mermaid")[1].split("```")[0].strip()
    elif "```" in diagram_syntax:
        diagram_syntax = diagram_syntax.split("```")[1].strip()
        if diagram_syntax.startswith("mermaid"):
            diagram_syntax = diagram_syntax[8:].strip()

    return {
        "success": True,
        "error": "",
        "diagram_syntax": diagram_syntax,
        "diagram_type": diagram_type,
    }
