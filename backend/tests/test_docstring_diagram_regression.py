import pytest
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

sys.path.insert(0, str(Path(__file__).parent.parent))

from generators.docstring_generator import build_docstring_prompt, generate_docstrings
from generators.diagram_generator import build_diagram_prompt, generate_diagram


class TestBuildDocstringPrompt:
    def test_build_prompt_google_style(self):
        code = "def add(a, b): return a + b"
        prompt = build_docstring_prompt(code, "python", "google", [])
        assert "Google style" in prompt
        assert "def add" in prompt

    def test_build_prompt_numpy_style(self):
        code = "def add(a, b): return a + b"
        prompt = build_docstring_prompt(code, "python", "numpy", [])
        assert "NumPy style" in prompt


class TestGenerateDocstrings:
    @patch("generators.docstring_generator.call_llm_for_tests")
    def test_generate_docstrings_success(self, mock_llm):
        mock_llm.return_value = '''
def add(a, b):
    """Add two numbers.
    
    Args:
        a: First number
        b: Second number
    
    Returns:
        The sum of a and b
    """
    return a + b
'''
        code = "def add(a, b): return a + b"
        result = generate_docstrings(code, "python", "google")

        assert result["success"] is True
        assert "add" in result["functions_documented"]
        assert "def add" in result["documented_code"]

    @patch("generators.docstring_generator.call_llm_for_tests")
    def test_generate_docstrings_llm_failure(self, mock_llm):
        mock_llm.return_value = None
        code = "def add(a, b): return a + b"
        result = generate_docstrings(code, "python", "google")

        assert result["success"] is False
        assert "LLM unavailable" in result["error"]

    def test_generate_docstrings_no_functions(self):
        code = "x = 1"
        result = generate_docstrings(code, "python", "google")

        assert result["success"] is False
        assert "No functions found" in result["error"]


class TestBuildDiagramPrompt:
    def test_build_prompt_sequence(self):
        code = "def add(a, b): return a + b"
        prompt = build_diagram_prompt(code, "python", "sequence")
        assert "sequence" in prompt.lower()
        assert "Mermaid" in prompt


class TestGenerateDiagram:
    @patch("generators.diagram_generator.call_llm_for_tests")
    def test_generate_diagram_success(self, mock_llm):
        mock_llm.return_value = """sequenceDiagram
    A->>B: Hello
    B-->>A: Hi"""
        code = "def add(a, b): return a + b"
        result = generate_diagram(code, "python", "sequence")

        assert result["success"] is True
        assert "sequenceDiagram" in result["diagram_syntax"]

    @patch("generators.diagram_generator.call_llm_for_tests")
    def test_generate_diagram_strips_markdown(self, mock_llm):
        mock_llm.return_value = """```mermaid
sequenceDiagram
    A->>B: Hello
```"""
        code = "def add(a, b): return a + b"
        result = generate_diagram(code, "python", "sequence")

        assert result["success"] is True
        assert not result["diagram_syntax"].startswith("```")

    @patch("generators.diagram_generator.call_llm_for_tests")
    def test_generate_diagram_llm_failure(self, mock_llm):
        mock_llm.return_value = None
        code = "def add(a, b): return a + b"
        result = generate_diagram(code, "python", "sequence")

        assert result["success"] is False
        assert "LLM unavailable" in result["error"]

    def test_generate_diagram_no_functions(self):
        code = "x = 1"
        result = generate_diagram(code, "python", "sequence")

        assert result["success"] is False
        assert "No functions found" in result["error"]
