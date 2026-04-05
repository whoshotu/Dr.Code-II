import ast
from typing import Optional


def sanitize_python_output(code: str) -> str:
    if not code:
        return ""
    try:
        ast.parse(code)
        return code
    except Exception:
        # Try to salvage after identifying obvious code blocks
        blocks = []
        current = []
        for line in code.splitlines():
            s = line.strip()
            if s.startswith(("def ", "class ", "import ", "from ")):
                if current:
                    blocks.append("\n".join(current))
                    current = []
                current = [line]
            else:
                if current:
                    current.append(line)
        if current:
            blocks.append("\n".join(current))
        for b in blocks:
            try:
                ast.parse(b)
                return b
            except Exception:
                continue
        return ""


def sanitize_mermaid_output(code: str) -> str:
    if not code:
        return ""
    s = code.strip()
    if s.startswith("```mermaid"):
        inner = s.split("```mermaid", 1)[1]
        inner = inner.split("```")[0]
        return inner.strip()
    if "sequenceDiagram" in s or "graph" in s:
        return s
    return ""
