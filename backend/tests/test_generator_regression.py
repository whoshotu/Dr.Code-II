import pytest
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

sys.path.insert(0, str(Path(__file__).parent.parent))

from generators.test_generator import (
    extract_python_functions,
    extract_js_functions,
    extract_functions,
    build_test_prompt,
    validate_python_syntax,
    generate_tests,
    FunctionInfo,
)


class TestExtractPythonFunctions:
    def test_extract_simple_function(self):
        code = """
def add(a, b):
    return a + b
"""
        functions = extract_python_functions(code)
        assert len(functions) == 1
        assert functions[0].name == "add"
        assert functions[0].params == ["a", "b"]

    def test_extract_multiple_functions(self):
        code = """
def add(a, b):
    return a + b

def multiply(a, b):
    return a * b

def divide(a, b):
    return a / b
"""
        functions = extract_python_functions(code)
        assert len(functions) == 3
        assert [f.name for f in functions] == ["add", "multiply", "divide"]

    def test_extract_async_function(self):
        code = """
async def fetch_data(url):
    return await http.get(url)
"""
        functions = extract_python_functions(code)
        assert len(functions) == 1
        assert functions[0].name == "fetch_data"
        assert functions[0].is_async is True

    def test_extract_function_with_return_type(self):
        code = """
def add(a: int, b: int) -> int:
    return a + b
"""
        functions = extract_python_functions(code)
        assert len(functions) == 1
        assert functions[0].return_annotation == "int"

    def test_empty_code(self):
        code = ""
        functions = extract_python_functions(code)
        assert functions == []

    def test_invalid_syntax(self):
        code = "def invalid(   "
        functions = extract_python_functions(code)
        assert functions == []


class TestExtractJSFunctions:
    def test_extract_js_function(self):
        code = """
function add(a, b) {
    return a + b;
}
"""
        functions = extract_js_functions(code)
        assert len(functions) == 1
        assert functions[0].name == "add"

    def test_extract_arrow_function(self):
        code = """
const multiply = (a, b) => {
    return a * b;
};
"""
        functions = extract_js_functions(code)
        assert len(functions) == 1
        assert functions[0].name == "multiply"


class TestExtractFunctions:
    def test_extract_python(self):
        code = "def test(): pass"
        functions = extract_functions(code, "python")
        assert len(functions) == 1

    def test_extract_javascript(self):
        code = "function test() {}"
        functions = extract_functions(code, "javascript")
        assert len(functions) == 1

    def test_extract_typescript(self):
        code = "function test(): void {}"
        functions = extract_functions(code, "typescript")
        assert len(functions) == 1

    def test_unsupported_language(self):
        code = "function test() {}"
        functions = extract_functions(code, "ruby")
        assert functions == []


class TestBuildTestPrompt:
    def test_build_prompt_with_functions(self):
        code = "def add(a, b): return a + b"
        functions = [FunctionInfo("add", ["a", "b"], None, False, [])]
        prompt = build_test_prompt(code, "python", "pytest", functions, True)
        assert "def add(a, b)" in prompt
        assert "pytest" in prompt
        assert "edge cases" in prompt.lower()

    def test_build_prompt_without_edge_cases(self):
        code = "def add(a, b): return a + b"
        functions = [FunctionInfo("add", ["a", "b"], None, False, [])]
        prompt = build_test_prompt(code, "python", "pytest", functions, False)
        assert "edge cases" not in prompt.lower()


class TestValidatePythonSyntax:
    def test_valid_syntax(self):
        code = "def test(): assert True"
        valid, error = validate_python_syntax(code)
        assert valid is True
        assert error is None

    def test_invalid_syntax(self):
        code = "def test(:   "
        valid, error = validate_python_syntax(code)
        assert valid is False
        assert error is not None


class TestGenerateTests:
    @patch("generators.test_generator.call_llm_for_tests")
    def test_generate_tests_success(self, mock_llm):
        mock_llm.return_value = """
import pytest

def test_add():
    assert add(1, 2) == 3
    assert add(0, 0) == 0
"""
        code = "def add(a, b): return a + b"
        result = generate_tests(code, "python", "pytest", True)

        assert result["success"] is True
        assert result["test_count"] == 1
        assert "def test_add" in result["test_code"]
        assert "add" in result["functions_tested"]

    @patch("generators.test_generator.call_llm_for_tests")
    def test_generate_tests_llm_failure(self, mock_llm):
        mock_llm.return_value = None
        code = "def add(a, b): return a + b"
        result = generate_tests(code, "python", "pytest", True)

        assert result["success"] is False
        assert "LLM unavailable" in result["error"]

    def test_generate_tests_no_functions(self):
        code = "x = 1"
        result = generate_tests(code, "python", "pytest", True)

        assert result["success"] is False
        assert "No functions found" in result["error"]

    @patch("generators.test_generator.call_llm_for_tests")
    def test_generate_tests_invalid_syntax(self, mock_llm):
        mock_llm.return_value = "def test(: invalid syntax here!!!"
        code = "def add(a, b): return a + b"
        result = generate_tests(code, "python", "pytest", True)

        assert result["success"] is False
        assert "syntax errors" in result["error"]
