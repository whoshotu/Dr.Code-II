import ast
import re
from typing import Any, Tuple
from generators.no_slop import sanitize_python_output

from generators.test_generator import extract_functions, call_llm_for_tests


def build_docstring_prompt(
    code: str,
    language: str,
    style: str,
    functions: list[Any],
) -> str:
    lang = language.lower()

    style_info = {
        "google": "Google style: Args:, Returns:, Raises:",
        "numpy": "NumPy style: Parameters, Returns with types",
        "sphinx": "Sphinx style: :param, :type, :return:, :rtype:",
    }.get(style.lower(), "Google style")

    prompt = f"""Generate docstrings for the following {lang} code.
Style: {style_info}

Source Code:
```{lang}
{code}
```

For each function, generate a docstring that describes:
- What the function does
- Each parameter with type and purpose
- Return value with type
- Any exceptions it may raise

Return ONLY the code with docstrings added, no explanations."""

    return prompt


def validate_python_syntax(code: str) -> Tuple[bool, str | None]:
    try:
        ast.parse(code)
        return True, None
    except SyntaxError as e:
        return False, str(e)


def validate_syntax(code: str, language: str) -> Tuple[bool, str | None]:
    language = language.lower()
    if language in ("python", "py"):
        return validate_python_syntax(code)
    return True, None


def generate_docstrings(
    code: str,
    language: str,
    style: str = "google",
    sanitizer_enabled: bool = True,
) -> dict[str, Any]:
    functions = extract_functions(code, language)

    if not functions:
        return {
            "success": False,
            "error": "No functions found in code",
            "documented_code": code,
            "functions_documented": [],
        }

    prompt = build_docstring_prompt(code, language, style, functions)

    documented_code: str | None = call_llm_for_tests(prompt)
    if sanitizer_enabled and documented_code is not None:
        documented_code = sanitize_python_output(documented_code)

    if not documented_code:
        return {
            "success": False,
            "error": "Failed to generate docstrings - LLM unavailable",
            "documented_code": code,
            "functions_documented": [],
        }

    valid, syntax_error = validate_syntax(documented_code, language)
    if not valid:
        return {
            "success": False,
            "error": f"Generated code has syntax errors: {syntax_error}",
            "documented_code": code,
            "functions_documented": [],
        }

    return {
        "success": True,
        "error": "",
        "documented_code": documented_code,
        "functions_documented": [f.name for f in functions],
    }
