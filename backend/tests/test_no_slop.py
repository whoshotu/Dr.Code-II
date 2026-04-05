import os
import sys
import pytest
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from generators.no_slop import sanitize_python_output, sanitize_mermaid_output


def test_sanitize_python_valid():
    code = "def add(a,b):\n    return a+b\n"
    assert sanitize_python_output(code) == code


def test_sanitize_python_invalid():
    bad = "def add(a,b) return a+b"
    salvaged = sanitize_python_output(bad)
    assert isinstance(salvaged, str)


def test_sanitize_mermaid():
    mermaid = "```mermaid\nsequenceDiagram\nA->B: Hello\n```"
    out = sanitize_mermaid_output(mermaid)
    assert "sequenceDiagram" in out
