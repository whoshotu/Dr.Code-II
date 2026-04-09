from pathlib import Path
import sys
import os

# Add project root to sys.path to allow 'from backend.xxx' imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import asyncio
import base64
import binascii
import hashlib
import hmac
import io
import json
import logging
import os
import re
import subprocess
import tempfile
import time
import uuid
import zipfile
from datetime import datetime, timezone
from time import perf_counter
from typing import Any, Annotated

import requests
from cryptography.fernet import Fernet, InvalidToken
from dotenv import load_dotenv
from fastapi import APIRouter, FastAPI, Header, HTTPException, Request
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, model_validator
from starlette.middleware.cors import CORSMiddleware

# Moved imports to facilitate top-level package resolution
from backend.database_sqlite import SQLiteDatabase
from backend.generators.diagram_generator import generate_diagram
from backend.generators.docstring_generator import generate_docstrings
from backend.generators.test_generator import generate_tests
from backend.local_provider import call_provider_local


# --- Constants ---
ISSUE_SQL_INJECTION = "SQL Injection Risk"
ISSUE_WEAK_CRYPTO = "Weak Cryptography"
ISSUE_COMMAND_INJECTION = "Command Injection"
ISSUE_PATH_TRAVERSAL = "Path Traversal Risk"
ISSUE_INSECURE_RANDOM = "Insecure Randomness"
ISSUE_INSECURE_DESERIAL = "Insecure Deserialization"
SUGGESTION_MASK_DATA = "Remove or mask sensitive data."
ERROR_SESSION_NOT_FOUND = "Repository session not found"
ERROR_GENERATION_FAILED = "Error message if generation failed"
CONTENT_TYPE_JSON = "application/json"
DEFAULT_OLLAMA_URL = "http://localhost:11434"
MSG_REPO_ANALYZED = "analyzed"
STATUS_SUCCESS = "success"
STATUS_ERROR = "error"

# --- Environment & Roots ---
ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / ".env")

# --- SQLite Migration: No longer using MongoDB for 'Judge-Ready' mode ---
db = SQLiteDatabase(str(ROOT_DIR / "drcode.db"))
MONGO_URL = "sqlite://local"  # Standardized naming


def discover_ollama_url() -> tuple[str, str]:
    """Auto-discover Ollama: localhost → docker internal → env var"""
    _logger = logging.getLogger(__name__)

    # 1. Try localhost first (works in CI and local), then docker internal
    for url in [
        DEFAULT_OLLAMA_URL,
        "http://host.docker.internal:11434",
        "http://ollama:11434",
    ]:
        try:
            r = requests.get(f"{url}/api/tags", timeout=3)
            if r.ok:
                _logger.info("Ollama auto-detected: %s", url)
                return (url, os.environ.get("OLLAMA_MODEL", "codellama"))
        except requests.exceptions.RequestException:
            continue

    # 2. Use env vars as fallback
    base_url = os.environ.get("OLLAMA_BASE_URL", DEFAULT_OLLAMA_URL)
    model = os.environ.get("OLLAMA_MODEL", "codellama")
    _logger.info("Ollama from environment: %s (%s)", base_url, model)
    return (base_url, model)


# Initialize with SQLite
# Already initialized above as 'db'


app = FastAPI(title="DR.CODE v2")


@app.on_event("startup")
async def startup_db():
    await db.init_all()


api_router = APIRouter(prefix="/api")


class LocalAnalysisRequest(BaseModel):
    path: str


@api_router.post(
    "/repository/analyze-local",
    responses={
        400: {"description": "Invalid directory path or no supported files found"}
    },
)
async def analyze_local_folder(req: LocalAnalysisRequest):
    """Analyze a folder directly on the server's filesystem."""
    path = Path(req.path)
    if not path.exists() or not path.is_dir():
        raise HTTPException(status_code=400, detail="Invalid directory path")

    session_id = str(uuid.uuid4())
    logging.getLogger(__name__).info(
        "Starting local analysis for: %s (Session: %s)", path, session_id
    )

    # Standard analysis pipeline for local files
    files_to_analyze = await _discover_local_files(path)

    if not files_to_analyze:
        raise HTTPException(
            status_code=400, detail="No supported source files found in directory"
        )

    # Record session
    session = {
        "session_id": session_id,
        "repository_name": path.name,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "files": files_to_analyze,
        "file_count": len(files_to_analyze),
        "status": MSG_REPO_ANALYZED,
        "summary": f"Local analysis of {path.name}",
        "fixes": [],
        "applied_fix_count": 0,
    }
    await db.repository_sessions.insert_one(session)

    return {"session_id": session_id, "file_count": len(files_to_analyze)}


async def _discover_local_files(base_path: Path) -> list[dict[str, str]]:
    """Helper to discover and read supported files recursively."""
    discovered = []
    for dir_path, _, files in os.walk(base_path):
        for file_name in files:
            if Path(file_name).suffix.lower() in SUPPORTED_REPO_EXTENSIONS:
                full_path = Path(dir_path) / file_name
                try:
                    rel_path = full_path.relative_to(base_path)
                    content = await asyncio.to_thread(
                        full_path.read_text, encoding="utf-8", errors="ignore"
                    )
                    if content.strip():
                        discovered.append({"path": str(rel_path), "content": content})
                except (OSError, ValueError):
                    continue
    return discovered


@api_router.post("/reset-analysis")
async def reset_analysis():
    """Archive everything to trash and clear active analysis tables."""
    await db.move_all_to_trash()
    await db.clear_analysis_tables()
    return {"message": "Analysis state archived to trash"}


@api_router.delete(
    "/trash-file/{file_id}",
    responses={404: {"description": "File or report not found in the primary tables"}},
)
async def trash_file(file_id: str):
    """Soft-delete a specific report by moving it to the trash table."""
    success = await db.move_to_trash(file_id)
    if not success:
        raise HTTPException(status_code=404, detail="File/Report not found")
    return {"message": "File moved to trash"}


@api_router.get("/trash")
async def list_trash():
    """List all items currently in the trash."""
    items = await db.get_trash_contents()
    return items


class SeverityThresholds(BaseModel):
    critical: int = Field(
        default=85,
        ge=0,
        le=100,
        description="Minimum score to classify an issue as critical",
    )
    high: int = Field(
        default=70,
        ge=0,
        le=100,
        description="Minimum score to classify an issue as high severity",
    )
    medium: int = Field(
        default=45,
        ge=0,
        le=100,
        description="Minimum score to classify an issue as medium severity",
    )
    low: int = Field(
        default=0,
        ge=0,
        le=100,
        description="Minimum score to classify an issue as low severity",
    )

    @model_validator(mode="after")
    def check_order(self):
        if not (self.critical > self.high > self.medium >= self.low):
            raise ValueError("Thresholds must follow: critical > high > medium >= low")
        return self


class AnalyzerSettings(BaseModel):
    id: str = "default"
    use_ollama: bool = False
    ollama_base_url: str | None = None
    ollama_model: str | None = None
    severity: SeverityThresholds = Field(default_factory=SeverityThresholds)
    providers: dict[str, dict[str, Any]] = Field(default_factory=dict)
    routing: dict[str, Any] = Field(default_factory=dict)


class AnalyzerSettingsUpdate(BaseModel):
    use_ollama: bool | None = None
    ollama_base_url: str | None = None
    ollama_model: str | None = None
    severity: SeverityThresholds
    providers: dict[str, dict[str, Any]] | None = None
    routing: dict[str, Any] | None = None


PROVIDER_KEYS = ["ollama", "openai_compatible", "gemini", "anthropic", "local"]

DEFAULT_MODELS = {
    "ollama": "llama3.1:8b",
    "openai_compatible": "gpt-5.2",
    "gemini": "gemini-2.5-pro",
    "anthropic": "claude-sonnet-4-6",
}
DEFAULT_MODELS.setdefault("local", DEFAULT_MODELS.get("ollama") or "llama3.2:latest")

DEFAULT_BASE_URLS = {
    "ollama": "http://localhost:11434",
    "local": "http://localhost:8003",
    "openai_compatible": "https://api.openai.com/v1",
    "gemini": "https://generativelanguage.googleapis.com/v1beta",
    "anthropic": "https://api.anthropic.com/v1",
}


class Issue(BaseModel):
    issue_id: str = Field(
        default_factory=lambda: str(uuid.uuid4()),
        description="Unique identifier for the issue",
    )
    category: str = Field(
        ..., description="Logical category of the issue (e.g., security, style)"
    )
    title: str = Field(..., description="Short descriptive title of the issue")
    detail: str = Field(
        ..., description="Detailed explanation of the issue and its impact"
    )
    severity: str = Field(
        ..., description="Severity level: critical, high, medium, or low"
    )
    score: int = Field(..., description="Numeric severity score (0-100)")
    line_number: int | None = Field(
        default=None, description="1-indexed line number where the issue was found"
    )
    fix_suggestion: str = Field(
        ..., description="Proactive advice on how to resolve the issue"
    )
    code_snippet: str | None = Field(
        default=None, description="The relevant snippet of code containing the issue"
    )
    source: str = Field(
        default="rule", description="Detection source: rule or ai provider"
    )
    confidence: float = Field(
        default=0.7, description="Detection confidence score (0.0-1.0)"
    )
    risk_tags: list[str] = Field(
        default_factory=list, description="Categorical tags for risk classification"
    )
    decision_trace: list[str] = Field(
        default_factory=list,
        description="Internal trace explaining the detection logic",
    )


class AnalyzeRequest(BaseModel):
    code: str = Field(..., min_length=1, description="Source code to be analyzed")
    filename: str | None = Field(
        default="untitled", description="Optional name of the file being analyzed"
    )
    language: str = Field(
        default="python", description="Programming language of the code snippet"
    )


class AnalysisReport(BaseModel):
    report_id: str = Field(
        default_factory=lambda: str(uuid.uuid4()),
        description="Unique identifier for the generated report",
    )
    created_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(),
        description="ISO timestamp of when the report was created",
    )
    filename: str = Field(..., description="Name of the file analyzed")
    language: str = Field(..., description="Detected or specified programming language")
    source_code: str = Field(
        ..., description="The original source code that was analyzed"
    )
    summary: str = Field(
        ..., description="High-level executive summary of the health of the code"
    )
    issues: list[Issue] = Field(
        ..., description="List of identified issues and slop patterns"
    )
    documentation: str = Field(
        ..., description="Generated documentation or architectural notes"
    )
    ai_notes: str | None = Field(
        default=None,
        description="Additional context or qualitative notes from the AI provider",
    )
    mode: str = Field(..., description="Analysis mode: rule-based or ai-assisted")
    governance: dict[str, Any] = Field(
        default_factory=dict, description="Governance and policy compliance metadata"
    )
    quality_checks: list[dict[str, Any]] = Field(
        default_factory=list,
        description="Detailed records of internal quality validation steps",
    )
    monitoring: dict[str, Any] = Field(
        default_factory=dict,
        description="Performance and runtime monitoring telemetry for the analysis",
    )


class ReportSummary(BaseModel):
    report_id: str = Field(
        ..., description="Unique ID of the associated analysis report"
    )
    created_at: str = Field(..., description="ISO timestamp of report creation")
    filename: str = Field(
        ..., description="Name of the file associated with this report"
    )
    language: str = Field(..., description="Programming language of the source file")
    summary: str = Field(
        ..., description="Brief one-line summary of the analysis results"
    )
    mode: str = Field(..., description="Method used for analysis (rule vs ai)")
    issue_count: int = Field(..., description="Total number of issues identified")
    critical_count: int = Field(
        ..., description="Total number of critical severity issues"
    )


class GitWebhookEvent(BaseModel):
    repository: str = Field(
        ..., description="Name of the repository where the event occurred"
    )
    event_type: str = Field(
        ..., description="Type of git event (e.g., push, pull_request)"
    )
    branch: str | None = Field(
        default=None, description="The git branch associated with the event"
    )
    commit_sha: str | None = Field(
        default=None,
        description="The commit identifier (SHA) associated with the event",
    )
    payload_preview: str | None = Field(
        default=None, description="A truncated preview of the raw event payload"
    )


class CIEvent(BaseModel):
    pipeline: str = Field(..., description="Name of the CI/CD pipeline")
    status: str = Field(
        ..., description="Outcome status of the pipeline (e.g., success, failure)"
    )
    branch: str = Field(..., description="Branch name on which the pipeline ran")
    commit_sha: str = Field(..., description="Commit SHA that triggered the pipeline")


class IntegrationEvent(BaseModel):
    event_id: str = Field(
        default_factory=lambda: str(uuid.uuid4()),
        description="Unique ID for the integration event",
    )
    created_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(),
        description="ISO timestamp of event ingestion",
    )
    source: str = Field(..., description="Source system (e.g., github, jenkins)")
    event_type: str = Field(..., description="Type of event specific to the source")
    status: str = Field(..., description="Current processing status")
    details: dict[str, Any] = Field(
        ..., description="Structured payload details from the source"
    )


# --- GitHub Integration Models (v2 addition) ---


class GitHubSettingsUpdate(BaseModel):
    token: str | None = Field(
        default=None, description="New GitHub Personal Access Token"
    )
    webhook_secret: str | None = Field(
        default=None, description="New secret for webhook HMAC verification"
    )
    clear_token: bool = Field(
        default=False, description="Flag to explicitly clear the stored token"
    )


class GitHubSettingsPublic(BaseModel):
    token_configured: bool = Field(..., description="True if a GitHub token is stored")
    token_masked: str | None = Field(
        default=None, description="A masked preview of the token for UI display"
    )
    webhook_secret_configured: bool = Field(
        ..., description="True if a webhook secret is stored"
    )


class GitHubPRWebhookPayload(BaseModel):
    """Shape of a real GitHub pull_request webhook event."""

    action: str = Field(
        ..., description="GitHub PR event action (e.g., opened, synchronize)"
    )
    pull_request: dict[str, Any] = Field(
        ..., description="Full pull request object data"
    )
    repository: dict[str, Any] = Field(..., description="Repository object data")


SUPPORTED_REPO_EXTENSIONS = {
    ".py",
    ".js",
    ".jsx",
    ".ts",
    ".tsx",
    ".json",
    ".md",
    ".txt",
    ".yml",
    ".yaml",
    ".css",
    ".html",
}


class GenerateTestsRequest(BaseModel):
    code: str = Field(
        ..., description="Source code for which unit tests should be generated"
    )
    language: str = Field(
        default="python", description="Programming language of the source code"
    )
    framework: str = Field(
        default="pytest", description="Testing framework to target (e.g., pytest, jest)"
    )
    include_edge_cases: bool = Field(
        default=True,
        description="Whether to generate tests for edge cases and failure modes",
    )


class GenerateTestsResponse(BaseModel):
    success: bool = Field(
        ..., description="Indicates if test generation was successful"
    )
    error: str = Field(default="", description="Error message if generation failed")
    test_code: str = Field(..., description="The generated test suite source code")
    test_count: int = Field(..., description="Number of test cases generated")
    functions_tested: list[str] = Field(
        ..., description="List of function names covered by the tests"
    )
    coverage_notes: str = Field(
        ..., description="Qualitative notes on test coverage and logic"
    )


class GenerateDocstringsRequest(BaseModel):
    code: str = Field(
        ..., description="Code snippet for which docstrings should be generated"
    )
    language: str = Field(
        default="python", description="Programming language of the code"
    )
    style: str = Field(
        default="google",
        description="Docstring style convention (e.g., google, numpy, sphinx)",
    )
    sanitizer: bool | None = Field(
        default=True, description="Whether to sanitize sensitive text in the code"
    )


class GenerateDocstringsResponse(BaseModel):
    success: bool = Field(
        ..., description="Indicates if docstring generation was successful"
    )
    error: str = Field(default="", description="Error message if generation failed")
    documented_code: str = Field(
        ..., description="The updated code with generated docstrings included"
    )
    functions_documented: list[str] = Field(
        ..., description="List of function names that were documented"
    )


class GenerateDiagramRequest(BaseModel):
    code: str = Field(..., description="Code snippet to visualize as a diagram")
    language: str = Field(
        default="python", description="Programming language of the code"
    )
    diagram_type: str = Field(
        default="sequence",
        description="Type of diagram to generate (e.g., sequence, class)",
    )
    sanitizer: bool | None = Field(
        default=True, description="Whether to sanitize sensitive text in the code"
    )


class GenerateDiagramResponse(BaseModel):
    success: bool = Field(
        ..., description="Indicates if diagram generation was successful"
    )
    error: str = Field(default="", description="Error message if generation failed")
    diagram_syntax: str = Field(
        ..., description="Mermaid.js or equivalent diagram syntax"
    )
    diagram_type: str = Field(..., description="The type of diagram generated")


class RepositoryFile(BaseModel):
    path: str = Field(..., description="Relative file path within the repository")
    content: str = Field(..., description="Text content of the file")


class RepositoryAnalyzeRequest(BaseModel):
    repository_name: str = Field(
        default="uploaded-repository",
        description="Human-readable name for the repository",
    )
    files: list[RepositoryFile] = Field(
        ..., description="List of files to analyze as a batch"
    )

    @model_validator(mode="after")
    def validate_repo_payload(self):
        if len(self.files) == 0:
            raise ValueError("Repository payload must include at least one file")
        if len(self.files) > 300:
            raise ValueError("Maximum 300 files allowed per repository scan")
        total_size = sum(len(file.content) for file in self.files)
        if total_size > 3_000_000:
            raise ValueError("Repository payload exceeds maximum size (3MB)")
        return self


class FixProposal(BaseModel):
    fix_id: str = Field(
        default_factory=lambda: str(uuid.uuid4()),
        description="Unique identifier for the fix proposal",
    )
    file_path: str = Field(
        ..., description="Path to the file relative to repository root"
    )
    line_number: int = Field(
        ..., description="1-indexed line number where the fix should be applied"
    )
    title: str = Field(..., description="Short title describing the nature of the fix")
    detail: str = Field(
        ..., description="In-depth explanation of why this fix is recommended"
    )
    severity: str = Field(
        ..., description="Severity of the original problem (e.g., critical, high)"
    )
    score: int = Field(..., description="Impact score or priority weight (0-100)")
    original_line: str = Field(
        ..., description="The original line of code before the fix"
    )
    replacement_line: str = Field(..., description="The proposed replacement code")
    approved: bool = Field(
        default=False, description="Whether this fix has been approved by the user"
    )
    auto_applicable: bool = Field(
        default=True,
        description="Whether the fix can be applied automatically without manual intervention",
    )


class RepositoryAnalysisResult(BaseModel):
    session_id: str = Field(
        ..., description="Unique session ID for the repository analysis"
    )
    repository_name: str = Field(..., description="Name of the analyzed repository")
    created_at: str = Field(..., description="ISO timestamp of analysis completion")
    file_count: int = Field(
        ..., description="Number of files processed in this session"
    )
    status: str = Field(
        ..., description="Current session status (e.g., analyzed, applying)"
    )
    summary: str = Field(
        ..., description="Executive summary of the repository-wide analysis"
    )
    fixes: list[FixProposal] = Field(
        ..., description="Comprehensive list of proposed fixes for all files"
    )
    applied_fix_count: int = Field(
        default=0, description="Number of fixes currently applied to the repository"
    )


class ApplyRepositoryFixesRequest(BaseModel):
    session_id: str = Field(
        ..., description="ID of the repository session to apply fixes for"
    )
    approve_all: bool = Field(
        default=False, description="Flag to approve all proposed fixes in the session"
    )
    approved_fix_ids: list[str] = Field(
        default_factory=list, description="Explicit list of fix IDs to apply"
    )


class ApplyRepositoryFixesResponse(BaseModel):
    session_id: str = Field(..., description="ID of the repository session")
    status: str = Field(..., description="Current status after applying fixes")
    applied_fix_count: int = Field(
        ..., description="Total number of fixes successfully applied"
    )
    updated_file_count: int = Field(
        ..., description="Number of files that were modified"
    )
    message: str = Field(..., description="Result message or summary of changes")


class ActorContext(BaseModel):
    actor_id: str = Field(
        ..., description="Identifier of the user or system performing the action"
    )
    role: str = Field(..., description="Role of the actor (e.g., admin, reviewer)")


class GovernancePolicy(BaseModel):
    id: str = "default"
    version: int = 1
    allowed_providers: list[str] = Field(
        default_factory=lambda: ["ollama", "openai_compatible", "gemini", "anthropic"],
        description="List of AI providers permitted by policy",
    )
    blocked_patterns: list[str] = Field(
        default_factory=lambda: ["rm -rf", "drop database", "private_key"],
        description="Regexp patterns that trigger policy violations",
    )
    max_code_length: int = Field(
        default=70000, description="Maximum length of code snippets allowed in analysis"
    )
    require_reviewer_for_high_risk: bool = Field(
        default=True, description="Enforce dual-review for high-risk changes"
    )
    min_transparency_confidence: float = Field(
        default=0.45,
        ge=0.0,
        le=1.0,
        description="Minimum confidence score for AI detections",
    )
    updated_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(),
        description="ISO timestamp of policy update",
    )
    updated_by: str = Field(
        default="system",
        description="Identifier of the actor who last updated the policy",
    )


class GovernancePolicyUpdate(BaseModel):
    allowed_providers: list[str] = Field(..., description="Permitted AI providers")
    blocked_patterns: list[str] = Field(..., description="Regexp patterns to block")
    max_code_length: int = Field(ge=1000, le=250000, description="Maximum snippet size")
    require_reviewer_for_high_risk: bool = Field(..., description="Enforce review flag")
    min_transparency_confidence: float = Field(
        ge=0.0, le=1.0, description="Min detection threshold"
    )


class GovernanceAuditEvent(BaseModel):
    event_id: str = Field(
        default_factory=lambda: str(uuid.uuid4()), description="Unique audit event ID"
    )
    created_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(),
        description="Timestamp of the audit event",
    )
    actor_id: str = Field(..., description="ID of the actor who triggered the event")
    role: str = Field(..., description="Role of the actor at time of event")
    action: str = Field(..., description="Nature of the action performed")
    status: str = Field(..., description="Result status of the action")
    details: dict[str, Any] = Field(..., description="Structured audit context")


class SecurityEvent(BaseModel):
    event_id: str = Field(
        default_factory=lambda: str(uuid.uuid4()),
        description="Unique security event ID",
    )
    created_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(),
        description="Detection timestamp",
    )
    severity: str = Field(..., description="Security severity level")
    event_type: str = Field(..., description="Logical type of security event")
    actor_id: str = Field(
        ..., description="ID of the actor who triggered the alert (if applicable)"
    )
    details: dict[str, Any] = Field(
        ..., description="Detailed technical payload for investigation"
    )


ALLOWED_ROLES = {"admin", "reviewer"}
ALLOWED_LANGUAGES = {"python", "javascript", "typescript"}


def resolve_actor_context(actor_id: str | None, role: str | None) -> ActorContext:
    normalized_role = (role or "reviewer").strip().lower()
    if normalized_role not in ALLOWED_ROLES:
        normalized_role = "reviewer"
    return ActorContext(
        actor_id=(actor_id or "anonymous").strip() or "anonymous", role=normalized_role
    )


def require_admin(actor: ActorContext):
    if actor.role != "admin":
        raise HTTPException(
            status_code=403, detail="Admin role is required for this action"
        )


def redact_sensitive_text(text: str | None) -> str | None:
    if text is None:
        return None
    redacted = re.sub(
        r"(?i)(password|secret|token|api_key)\s*[:=]\s*['\"][^'\"]+['\"]",
        r"\1 = \"***\"",
        text,
    )
    redacted = re.sub(r"sk-[A-Za-z0-9_-]{8,}", "sk-***", redacted)
    return redacted


def redact_issue(issue: Issue) -> Issue:
    issue.code_snippet = redact_sensitive_text(issue.code_snippet)
    issue.detail = redact_sensitive_text(issue.detail) or issue.detail
    return issue


async def record_governance_event(
    actor: ActorContext, action: str, status: str, details: dict[str, Any]
):
    event = GovernanceAuditEvent(
        actor_id=actor.actor_id,
        role=actor.role,
        action=action,
        status=status,
        details=details,
    )
    await db.governance_audit_logs.insert_one(event.model_dump())


async def record_security_event(
    severity: str, event_type: str, actor: ActorContext, details: dict[str, Any]
):
    event = SecurityEvent(
        severity=severity,
        event_type=event_type,
        actor_id=actor.actor_id,
        details=details,
    )
    await db.security_events.insert_one(event.model_dump())


def default_governance_policy_doc() -> dict[str, Any]:
    return GovernancePolicy().model_dump()


async def get_or_create_governance_policy() -> GovernancePolicy:
    doc = await db.governance_policies.find_one({"id": "default"}, {"_id": 0})
    if doc:
        return GovernancePolicy(**doc)
    default_policy = GovernancePolicy()
    await db.governance_policies.insert_one(default_policy.model_dump())
    return default_policy


def run_data_validation_checks(
    code: str, language: str, policy: GovernancePolicy
) -> list[dict[str, Any]]:
    checks: list[dict[str, Any]] = []

    checks.append(
        {
            "check": "language-allowlist",
            "status": "passed" if language in ALLOWED_LANGUAGES else "failed",
            "detail": language,
        }
    )
    checks.append(
        {
            "check": "max-length",
            "status": "passed" if len(code) <= policy.max_code_length else "failed",
            "detail": len(code),
        }
    )
    checks.append(
        {
            "check": "non-empty",
            "status": "passed" if code.strip() else "failed",
            "detail": "content present" if code.strip() else "empty",
        }
    )
    checks.append(
        {
            "check": "null-byte",
            "status": "passed" if "\x00" not in code else "failed",
            "detail": "no null bytes",
        }
    )

    lowered = code.lower()
    blocked = [
        pattern for pattern in policy.blocked_patterns if pattern.lower() in lowered
    ]
    checks.append(
        {
            "check": "blocked-patterns",
            "status": "failed" if blocked else "passed",
            "detail": blocked,
        }
    )

    return checks


def ensure_checks_pass(checks: list[dict[str, Any]]):
    failed = [check for check in checks if check["status"] == "failed"]
    if failed:
        summary = "; ".join(
            [f"{check['check']} ({check['detail']})" for check in failed]
        )
        raise HTTPException(
            status_code=400, detail=f"Data validation failed: {summary}"
        )


def score_to_severity(score: int, thresholds: SeverityThresholds) -> str:
    if score >= thresholds.critical:
        return "critical"
    if score >= thresholds.high:
        return "high"
    if score >= thresholds.medium:
        return "medium"
    return "low"


def build_issue(
    thresholds: SeverityThresholds,
    category: str,
    title: str,
    detail: str,
    score: int,
    fix_suggestion: str,
    line_number: int | None = None,
    code_snippet: str | None = None,
    source: str = "rule",
    confidence: float = 0.78,
    risk_tags: list[str] | None = None,
    decision_trace: list[str] | None = None,
) -> Issue:
    trace = decision_trace or [
        f"Matched category '{category}' with score {score}",
        "Mapped score to severity threshold",
        "Generated deterministic fix suggestion",
    ]
    return Issue(
        category=category,
        title=title,
        detail=detail,
        score=score,
        severity=score_to_severity(score, thresholds),
        line_number=line_number,
        fix_suggestion=fix_suggestion,
        code_snippet=code_snippet,
        source=source,
        confidence=max(0.0, min(confidence, 1.0)),
        risk_tags=risk_tags or [category],
        decision_trace=trace,
    )


def rule_based_slop_detection(
    code: str, language: str, thresholds: SeverityThresholds
) -> list[Issue]:
    issues: list[Issue] = []
    lines = code.splitlines()

    for idx, line in enumerate(lines, start=1):
        _check_line_length(issues, idx, line, thresholds)
        _check_secrets(issues, idx, line, thresholds)
        _check_dynamic_execution(issues, idx, line, thresholds)
        _check_variable_naming(issues, idx, line, thresholds)
        _check_magic_numbers(issues, idx, line, thresholds)

    _check_duplicate_lines(issues, lines, thresholds)
    _check_nesting_depth(issues, lines, thresholds)
    _check_function_count(issues, lines, language, thresholds)
    _check_incomplete_markers(issues, lines, thresholds)
    _check_unused_imports(issues, lines, language, thresholds)

    return issues


def _check_line_length(
    issues: list[Issue], idx: int, line: str, thresholds: SeverityThresholds
):
    if len(line) > 120:
        issues.append(
            build_issue(
                thresholds,
                "complexity",
                "Overly long line",
                f"Line {idx} is {len(line)} characters and is hard to review.",
                55,
                "Wrap the statement into smaller expressions and use helper variables.",
                idx,
                line.strip(),
            )
        )


def _check_secrets(
    issues: list[Issue], idx: int, line: str, thresholds: SeverityThresholds
):
    if re.search(
        r"(password|secret|token|api_key)\s*=\s*['\"][^'\"]+['\"]",
        line,
        re.IGNORECASE,
    ):
        issues.append(
            build_issue(
                thresholds,
                "security",
                "Hardcoded secret-like value",
                f"Potential credential detected on line {idx}.",
                92,
                SUGGESTION_MASK_DATA,
                idx,
                line.strip(),
            )
        )


def _check_dynamic_execution(
    issues: list[Issue], idx: int, line: str, thresholds: SeverityThresholds
):
    if re.search(r"\b(eval|exec)\s*\(", line):
        issues.append(
            build_issue(
                thresholds,
                "security",
                "Dynamic execution risk",
                f"Dynamic execution detected on line {idx}.",
                88,
                "Replace eval/exec with explicit parsing or allowlisted operations.",
                idx,
                line.strip(),
            )
        )


def _check_variable_naming(
    issues: list[Issue], idx: int, line: str, thresholds: SeverityThresholds
):
    var_match = re.search(r"\b([a-zA-Z_]\w*)\s*=", line)
    if var_match:
        var_name = var_match.group(1)
        if len(var_name) <= 2 and var_name not in {"i", "j", "k", "x", "y"}:
            issues.append(
                build_issue(
                    thresholds,
                    "readability",
                    "Poor variable naming",
                    f"Variable '{var_name}' on line {idx} is not descriptive.",
                    52,
                    "Use a descriptive name that communicates business intent.",
                    idx,
                    line.strip(),
                )
            )


def _check_magic_numbers(
    issues: list[Issue], idx: int, line: str, thresholds: SeverityThresholds
):
    if re.search(r"=\s*\d{3,}", line) and "const" not in line.lower():
        issues.append(
            build_issue(
                thresholds,
                "slop",
                "Hardcoded numeric value",
                f"Magic number detected on line {idx}.",
                46,
                "Extract this value into a named constant or configuration setting.",
                idx,
                line.strip(),
            )
        )


def _check_duplicate_lines(
    issues: list[Issue], lines: list[str], thresholds: SeverityThresholds
):
    clean_lines = [
        line.strip() for line in lines if line.strip() and len(line.strip()) > 8
    ]
    line_counts: dict[str, int] = {}
    for line in clean_lines:
        line_counts[line] = line_counts.get(line, 0) + 1
    repeated = [line for line, count in line_counts.items() if count > 1]
    for item in repeated[:4]:
        issues.append(
            build_issue(
                thresholds,
                "redundancy",
                "Duplicate line detected",
                "Repeated logic found in multiple places.",
                61,
                "Extract repeated logic into a reusable helper function.",
                code_snippet=item,
            )
        )


def _check_nesting_depth(
    issues: list[Issue], lines: list[str], thresholds: SeverityThresholds
):
    max_indent = max(
        (len(line) - len(line.lstrip(" ")) for line in lines if line.strip()), default=0
    )
    if max_indent >= 16:
        issues.append(
            build_issue(
                thresholds,
                "complexity",
                "Deep nesting",
                "Deeply nested blocks reduce readability and increase bug risk.",
                73,
                "Use early returns and smaller functions to flatten control flow.",
            )
        )


def _check_function_count(
    issues: list[Issue], lines: list[str], language: str, thresholds: SeverityThresholds
):
    function_pattern = (
        r"^\s*def\s+\w+\s*\("
        if language.lower() == "python"
        else r"^\s*(function\s+\w+\s*\(|const\s+\w+\s*=\s*\()"
    )
    function_lines = [
        idx
        for idx, line in enumerate(lines, start=1)
        if re.search(function_pattern, line)
    ]
    if len(function_lines) >= 8:
        issues.append(
            build_issue(
                thresholds,
                "architecture",
                "High function count in single file",
                "This file has many functions and may be doing too much.",
                58,
                "Split responsibilities into modules by domain.",
            )
        )


def _check_incomplete_markers(
    issues: list[Issue], lines: list[str], thresholds: SeverityThresholds
):
    comment_pattern = r"#.*\b(TODO|FIXME|HACK|XXX|BUG|NOTE)\b"
    for idx, line in enumerate(lines, start=1):
        if re.search(comment_pattern, line, re.IGNORECASE):
            issues.append(
                build_issue(
                    thresholds,
                    "maintenance",
                    "Incomplete work marker",
                    f"Line {idx} contains an incomplete work marker (TODO/FIXME/HACK).",
                    38,
                    "Address the marker or document why it's pending.",
                    idx,
                    line.strip()[:80],
                )
            )


def _check_unused_imports(
    issues: list[Issue], lines: list[str], language: str, thresholds: SeverityThresholds
):
    import_patterns = {
        "python": r"^\s*(?:import|from\s+\w+\s+import)\s+([a-zA-Z_]\w*)",
        "javascript": r'^\s*(?:import|require)\s+[\'"]([a-zA-Z_][a-zA-Z0-9_-]*)',
        "java": r"^\s*import\s+([a-zA-Z_][a-zA-Z0-9_.]*)",
        "go": r'^\s*import\s+"([a-zA-Z_][a-zA-Z0-9_/]*)"',
    }
    lang_key = language.lower() if language.lower() in import_patterns else "javascript"
    import_re = import_patterns.get(lang_key, import_patterns["javascript"])

    imported_modules = set()
    defined_names = set()

    for line in lines:
        imp_match = re.search(import_re, line)
        if imp_match:
            imported_modules.add(imp_match.group(1).split(".")[0].split("/")[0])

        func_match = re.search(
            r"^\s*(?:def|function|const|class|class\s+\w+)[:{\s]+([a-zA-Z_]\w*)", line
        )
        if func_match:
            defined_names.add(func_match.group(1))

    unused_imports = (
        imported_modules
        - defined_names
        - {
            "os",
            "sys",
            "json",
            "re",
            "math",
            "logging",
            "typing",
            "List",
            "Dict",
            "Optional",
            "Any",
            "Union",
        }
    )
    for unused in list(unused_imports)[:3]:
        issues.append(
            build_issue(
                thresholds,
                "unused",
                "Potentially unused import",
                f"Module '{unused}' may not be used in this file.",
                42,
                "Remove unused imports to reduce clutter.",
                code_snippet=unused,
            )
        )

    for idx, line in enumerate(lines, start=1):
        if re.search(r"try:\s*(?:#[^\n]*)?\s*except\s*:", line) or re.search(
            r"try\s*{\s*}", line
        ):
            issues.append(
                build_issue(
                    thresholds,
                    "error-handling",
                    "Empty try-except block",
                    f"Empty try-except on line {idx} swallows exceptions silently.",
                    67,
                    "Add exception handling or remove the block.",
                    idx,
                    line.strip()[:80],
                )
            )

        if re.search(r"except\s*:", line) and "except" in line:
            issues.append(
                build_issue(
                    thresholds,
                    "error-handling",
                    "Bare except clause",
                    f"Line {idx} catches all exceptions, hiding bugs.",
                    72,
                    "Catch specific exceptions instead.",
                    idx,
                    line.strip()[:80],
                )
            )

    if language.lower() == "python":
        in_func = False
        func_name = ""
        func_start = 0

        for idx, line in enumerate(lines, start=1):
            def_match = re.search(r"^\s*def\s+([a-zA-Z_]\w*)\(", line)
            if def_match:
                in_func = True
                func_name = def_match.group(1)
                func_start = idx
                continue

            if in_func and line.strip() and not line.strip().startswith("#"):
                if line[0] not in " \t" or (idx - func_start > 3 and not line.strip()):
                    if idx - func_start > 3:
                        if not any(
                            re.match(r'^\s+(""".*?""\'|\'\'\'.*?\'\'\')', l_item)
                            for l_item in lines[func_start:idx]
                            if l_item.strip()
                        ):
                            issues.append(
                                build_issue(
                                    thresholds,
                                    "documentation",
                                    "Missing docstring",
                                    f"Function '{func_name}' on line {func_start} has no docstring.",
                                    35,
                                    "Add a docstring explaining the function's purpose.",
                                    func_start,
                                    line.strip()[:80] if line.strip() else None,
                                )
                            )
                        in_func = False

    tab_lines = []
    space_indent = None
    for idx, line in enumerate(lines, start=1):
        if line.startswith("\t") and space_indent is False:
            tab_lines.append(idx)
        elif line.startswith(" ") and not line.startswith("\t"):
            space_indent = True
        elif line.startswith("\t"):
            space_indent = False

    if tab_lines:
        issues.append(
            build_issue(
                thresholds,
                "style",
                "Inconsistent indentation",
                f"File mixes tabs and spaces. Found tabs on lines: {', '.join(map(str, tab_lines[:5]))}.",
                44,
                "Use consistent indentation (spaces recommended).",
                code_snippet=f"Mix at lines: {', '.join(map(str, tab_lines[:3]))}",
            )
        )

    lang = language.lower()

    if lang in ("python", "py"):
        issues.extend(_detect_python_issues(lines, thresholds))
    elif lang in ("javascript", "js", "typescript", "ts"):
        issues.extend(_detect_javascript_issues(lines, thresholds))
    elif lang == "java":
        issues.extend(_detect_java_issues(lines, thresholds))
    elif lang == "go":
        issues.extend(_detect_go_issues(lines, thresholds))

    return issues[:25]


def _detect_python_issues(
    lines: list[str], thresholds: SeverityThresholds
) -> list[Issue]:
    issues: list[Issue] = []
    for idx, line in enumerate(lines, start=1):
        line_lower = line.lower()
        _check_py_sql_injection(issues, idx, line, line_lower, thresholds)
        _check_py_command_injection(issues, idx, line, thresholds)
        _check_py_path_traversal(issues, idx, line, line_lower, thresholds)
        _check_py_weak_crypto(issues, idx, line, line_lower, thresholds)
        _check_py_insecure_random(issues, idx, line, line_lower, thresholds)
        _check_py_insecure_deserialization(issues, idx, line, thresholds)
        _check_py_blocking_sleep(issues, idx, line, line_lower, thresholds)
        _check_py_line_complexity(issues, idx, line, thresholds)

    return issues


def _check_py_sql_injection(
    issues: list[Issue],
    idx: int,
    line: str,
    line_lower: str,
    thresholds: SeverityThresholds,
):
    if re.search(
        r'["\']\s*%\s*.*(?:select|insert|update|delete|drop|create)',
        line_lower,
        re.IGNORECASE,
    ):
        if "%" in line and ("sql" in line_lower or "query" in line_lower):
            issues.append(
                build_issue(
                    thresholds,
                    "security",
                    ISSUE_SQL_INJECTION,
                    f"Potential SQL injection on line {idx} - string formatting in SQL query.",
                    95,
                    "Use parameterized queries or ORM.",
                    idx,
                    line.strip(),
                    confidence=0.92,
                )
            )


def _check_py_command_injection(
    issues: list[Issue], idx: int, line: str, thresholds: SeverityThresholds
):
    if re.search(
        r"os\.system\(|subprocess\.call\(|subprocess\.run\(.*shell\s*=\s*True", line
    ):
        issues.append(
            build_issue(
                thresholds,
                "security",
                ISSUE_COMMAND_INJECTION,
                f"Command injection risk on line {idx}.",
                90,
                "Avoid shell=True or sanitize input.",
                idx,
                line.strip(),
                confidence=0.89,
            )
        )


def _check_py_path_traversal(
    issues: list[Issue],
    idx: int,
    line: str,
    line_lower: str,
    thresholds: SeverityThresholds,
):
    if re.search(r"open\([^,)]+\s*\+", line) or re.search(r"open\([^,)]*\%", line):
        if "path" in line_lower or "file" in line_lower or "dir" in line_lower:
            issues.append(
                build_issue(
                    thresholds,
                    "security",
                    ISSUE_PATH_TRAVERSAL,
                    f"Potential path traversal on line {idx}.",
                    88,
                    "Validate and sanitize file paths.",
                    idx,
                    line.strip(),
                    confidence=0.85,
                )
            )


def _check_py_weak_crypto(
    issues: list[Issue],
    idx: int,
    line: str,
    line_lower: str,
    thresholds: SeverityThresholds,
):
    if re.search(r"hashlib\.(md5|sha1)\(", line) and (
        "password" in line_lower or "secret" in line_lower
    ):
        issues.append(
            build_issue(
                thresholds,
                "security",
                ISSUE_WEAK_CRYPTO,
                f"Weak hash algorithm on line {idx}.",
                85,
                "Use bcrypt or argon2 for passwords.",
                idx,
                line.strip(),
                confidence=0.91,
            )
        )


def _check_py_insecure_random(
    issues: list[Issue],
    idx: int,
    line: str,
    line_lower: str,
    thresholds: SeverityThresholds,
):
    if re.search(r"random\.(random|randint)\(", line) and (
        "token" in line_lower or "password" in line_lower or "session" in line_lower
    ):
        issues.append(
            build_issue(
                thresholds,
                "security",
                ISSUE_INSECURE_RANDOM,
                f"Random module for security-sensitive purpose on line {idx}.",
                82,
                "Use secrets module for cryptographic randomness.",
                idx,
                line.strip(),
                confidence=0.88,
            )
        )


def _check_py_insecure_deserialization(
    issues: list[Issue], idx: int, line: str, thresholds: SeverityThresholds
):
    if re.search(r"pickle\.loads\(|pickle\.load\(", line):
        issues.append(
            build_issue(
                thresholds,
                "security",
                ISSUE_INSECURE_DESERIAL,
                f"Pickle deserialization on line {idx} is risky.",
                90,
                "Use JSON for untrusted data.",
                idx,
                line.strip(),
                confidence=0.93,
            )
        )


def _check_py_blocking_sleep(
    issues: list[Issue],
    idx: int,
    line: str,
    line_lower: str,
    thresholds: SeverityThresholds,
):
    if re.search(r"sleep\([^)]+\)\s*\)", line) and "time" not in line_lower:
        issues.append(
            build_issue(
                thresholds,
                "performance",
                "Blocking Sleep Call",
                f"Blocking sleep on line {idx}.",
                65,
                "Use async/await or threading.",
                idx,
                line.strip(),
                confidence=0.75,
            )
        )


def _check_py_line_complexity(
    issues: list[Issue], idx: int, line: str, thresholds: SeverityThresholds
):
    if line.count("=") >= 6 and len(line) > 80:
        issues.append(
            build_issue(
                thresholds,
                "maintenance",
                "Complex Line",
                f"Line {idx} is overly complex with multiple assignments.",
                58,
                "Break into separate statements.",
                idx,
                line.strip(),
                confidence=0.72,
            )
        )


def _detect_javascript_issues(
    lines: list[str], thresholds: SeverityThresholds
) -> list[Issue]:
    issues: list[Issue] = []
    for idx, line in enumerate(lines, start=1):
        line_lower = line.lower()

        if re.search(r"innerhtml\s*=|dangerouslysetinnerhtml", line, re.IGNORECASE):
            issues.append(
                build_issue(
                    thresholds,
                    "security",
                    "XSS Vulnerability",
                    f"Potential XSS on line {idx} - direct HTML insertion.",
                    93,
                    "Sanitize input or use textContent.",
                    idx,
                    line.strip(),
                    confidence=0.94,
                )
            )

        if re.search(r"eval\s*\(|new\s+function\s*\(", line):
            issues.append(
                build_issue(
                    thresholds,
                    "security",
                    "Code Injection Risk",
                    f"Dynamic code execution on line {idx}.",
                    91,
                    "Avoid eval, use safer alternatives.",
                    idx,
                    line.strip(),
                    confidence=0.92,
                )
            )

        if re.search(r"`.*\$\{.*\}.*`", line) and (
            "sql" in line_lower or "query" in line_lower
        ):
            issues.append(
                build_issue(
                    thresholds,
                    "security",
                    ISSUE_SQL_INJECTION,
                    f"Template literal SQL on line {idx}.",
                    94,
                    "Use parameterized queries.",
                    idx,
                    line.strip(),
                    confidence=0.90,
                )
            )

        if re.search(r"child_process\.(exec|spawn)\(.*\+", line):
            issues.append(
                build_issue(
                    thresholds,
                    "security",
                    ISSUE_COMMAND_INJECTION,
                    f"Command injection risk on line {idx}.",
                    92,
                    "Sanitize or use safe spawn.",
                    idx,
                    line.strip(),
                    confidence=0.91,
                )
            )

        if re.search(r'crypto\.createhash\([\'"](md5|sha1)[\'"]\)', line):
            issues.append(
                build_issue(
                    thresholds,
                    "security",
                    ISSUE_WEAK_CRYPTO,
                    f"Weak hash on line {idx}.",
                    84,
                    "Use SHA-256 or stronger.",
                    idx,
                    line.strip(),
                    confidence=0.89,
                )
            )

        if re.search(r"math\.random\(\)", line) and (
            "token" in line_lower or "id" in line_lower or "session" in line_lower
        ):
            issues.append(
                build_issue(
                    thresholds,
                    "security",
                    "Insecure Randomness",
                    f"Math.random for security on line {idx}.",
                    81,
                    "Use crypto.randomBytes().",
                    idx,
                    line.strip(),
                    confidence=0.87,
                )
            )

        if re.search(r"===.*==|==.*===", line):
            issues.append(
                build_issue(
                    thresholds,
                    "best_practices",
                    "Type Coercion Risk",
                    f"Mixed equality operators on line {idx}.",
                    55,
                    "Use === exclusively.",
                    idx,
                    line.strip(),
                    confidence=0.78,
                )
            )

        if re.search(
            r"console\.(log|warn|error)\(.*password|secret|token|api_key",
            line,
            re.IGNORECASE,
        ):
            issues.append(
                build_issue(
                    thresholds,
                    "security",
                    "Sensitive Data in Logs",
                    f"Potential secret logged on line {idx}.",
                    88,
                    "Remove or mask sensitive data.",
                    idx,
                    line.strip(),
                    confidence=0.95,
                )
            )

        if re.search(r"process\.env\[.*\+", line):
            issues.append(
                build_issue(
                    thresholds,
                    "security",
                    "Environment Variable Concatenation",
                    f"Env var concatenation on line {idx}.",
                    72,
                    "Use full env var names.",
                    idx,
                    line.strip(),
                    confidence=0.76,
                )
            )

        if line.count(".then(") >= 3:
            issues.append(
                build_issue(
                    thresholds,
                    "maintenance",
                    "Callback Hell",
                    f"Nested promises on line {idx}.",
                    62,
                    "Use async/await.",
                    idx,
                    line.strip(),
                    confidence=0.80,
                )
            )

    return issues


def _detect_java_issues(
    lines: list[str], thresholds: SeverityThresholds
) -> list[Issue]:
    """Analyze Java code for common security and style issues."""
    issues: list[Issue] = []
    for idx, line in enumerate(lines, start=1):
        line_lower = line.lower()
        _check_java_sql_injection(issues, idx, line, thresholds)
        _check_java_command_injection(issues, idx, line, thresholds)
        _check_java_deserialization(issues, idx, line, thresholds)
        _check_java_weak_crypto(issues, idx, line, thresholds)
        _check_java_exception_handling(issues, idx, line, thresholds)
        _check_java_redundancies(issues, idx, line, thresholds)
        _check_java_sensitive_logging(issues, idx, line, line_lower, thresholds)
    return issues


def _check_java_sql_injection(issues, idx, line, thresholds):
    if re.search(r'statement\.executequery\s*\(\s*["\'].*\+', line) or re.search(
        r'preparedstatement.*\+\s*["\']', line
    ):
        issues.append(
            build_issue(
                thresholds,
                "security",
                ISSUE_SQL_INJECTION,
                f"Potential SQL injection on line {idx}.",
                94,
                "Use PreparedStatement.",
                idx,
                line.strip(),
                confidence=0.93,
            )
        )


def _check_java_command_injection(issues, idx, line, thresholds):
    if re.search(r"runtime\.getruntime\(\)\.exec\(", line):
        issues.append(
            build_issue(
                thresholds,
                "security",
                ISSUE_COMMAND_INJECTION,
                f"Command execution on line {idx}.",
                91,
                "Validate input thoroughly.",
                idx,
                line.strip(),
                confidence=0.90,
            )
        )


def _check_java_deserialization(issues, idx, line, thresholds):
    if re.search(r"serialization\.readobject\(|objectinputstream", line):
        issues.append(
            build_issue(
                thresholds,
                "security",
                ISSUE_INSECURE_DESERIAL,
                f"Deserialization on line {idx}.",
                92,
                "Validate input or use a safe deserialization strategy.",
                idx,
                line.strip(),
                confidence=0.91,
            )
        )


def _check_java_weak_crypto(issues, idx, line, thresholds):
    if re.search(r'messagedigest\.getinstance\([\'"](md5|sha1)[\'"]\)', line):
        issues.append(
            build_issue(
                thresholds,
                "security",
                ISSUE_WEAK_CRYPTO,
                f"Weak hash on line {idx}.",
                84,
                "Use SHA-256 or stronger.",
                idx,
                line.strip(),
                confidence=0.88,
            )
        )


def _check_java_exception_handling(issues, idx, line, thresholds):
    if re.search(r"catch\s*\(\s*exception\s+\w+\s*\)", line):
        issues.append(
            build_issue(
                thresholds,
                "error-handling",
                "Broad Exception Catch",
                f"Catching all exceptions on line {idx}.",
                68,
                "Catch specific exceptions.",
                idx,
                line.strip(),
                confidence=0.82,
            )
        )
    if re.search(r"throws\s+exception", line):
        issues.append(
            build_issue(
                thresholds,
                "documentation",
                "Generic Exception Declaration",
                f"Throws generic Exception on line {idx}.",
                45,
                "Declare specific exceptions.",
                idx,
                line.strip(),
                confidence=0.75,
            )
        )


def _check_java_redundancies(issues, idx, line, thresholds):
    if re.search(r"string\s+\w+\s*=\s*new\s+string\(", line):
        issues.append(
            build_issue(
                thresholds,
                "performance",
                "Unnecessary String Creation",
                f"Unnecessary String on line {idx}.",
                55,
                "Remove unnecessary conversion.",
                idx,
                line.strip(),
                confidence=0.73,
            )
        )


def _check_java_sensitive_logging(issues, idx, line, line_lower, thresholds):
    if re.search(r"system\.out\.print\(", line) and (
        "password" in line_lower or "secret" in line_lower or "token" in line_lower
    ):
        issues.append(
            build_issue(
                thresholds,
                "security",
                "Sensitive Data Logging",
                f"Potential secret logged on line {idx}.",
                87,
                SUGGESTION_MASK_DATA,
                idx,
                line.strip(),
                confidence=0.94,
            )
        )


def _detect_go_issues(lines: list[str], thresholds: SeverityThresholds) -> list[Issue]:
    """Analyze Go code for common security and style issues."""
    issues: list[Issue] = []
    for idx, line in enumerate(lines, start=1):
        line_lower = line.lower()
        _check_go_command_injection(issues, idx, line, thresholds)
        _check_go_error_handling(issues, idx, line, thresholds)
        _check_go_sensitive_logging(issues, idx, line, thresholds)
        _check_go_json_unmarshal(issues, idx, line, thresholds)
        _check_go_concurrency(issues, idx, line, line_lower, thresholds)
        _check_go_panic_usage(issues, idx, line, line_lower, thresholds)
        _check_go_map_init(issues, idx, line, thresholds)
    return issues


def _check_go_command_injection(issues, idx, line, thresholds):
    if re.search(r"exec\.command\([^)]*\+", line):
        issues.append(
            build_issue(
                thresholds,
                "security",
                ISSUE_COMMAND_INJECTION,
                f"Command injection risk on line {idx}.",
                91,
                "Validate or sanitize input.",
                idx,
                line.strip(),
                confidence=0.90,
            )
        )


def _check_go_error_handling(issues, idx, line, thresholds):
    if (
        re.search(r"strconv\.atoi\(|strconv\.parsefloat\(", line)
        and "error" not in line
    ):
        issues.append(
            build_issue(
                thresholds,
                "error-handling",
                "Ignoring Parse Error",
                f"Ignoring parse error on line {idx}.",
                75,
                "Handle error return value.",
                idx,
                line.strip(),
                confidence=0.83,
            )
        )


def _check_go_sensitive_logging(issues, idx, line, thresholds):
    if re.search(r"fmt\.printf\(.*password|secret|token", line, re.IGNORECASE):
        issues.append(
            build_issue(
                thresholds,
                "security",
                "Sensitive Data Logging",
                f"Potential secret logged on line {idx}.",
                88,
                SUGGESTION_MASK_DATA,
                idx,
                line.strip(),
                confidence=0.94,
            )
        )


def _check_go_json_unmarshal(issues, idx, line, thresholds):
    if re.search(r"json\.unmarshal\(.*\[\]byte", line) and "error" not in line:
        issues.append(
            build_issue(
                thresholds,
                "error-handling",
                "Ignoring Unmarshal Error",
                f"Ignoring JSON decode error on line {idx}.",
                72,
                "Handle error return value.",
                idx,
                line.strip(),
                confidence=0.80,
            )
        )


def _check_go_concurrency(issues, idx, line, line_lower, thresholds):
    if (
        re.search(r"go\s+func\(\)\s*\{", line)
        and "waitgroup" not in line
        and "channel" not in line
    ):
        issues.append(
            build_issue(
                thresholds,
                "performance",
                "Goroutine Leak Risk",
                f"Uncontrolled goroutine on line {idx}.",
                68,
                "Ensure goroutine is properly managed.",
                idx,
                line.strip(),
                confidence=0.77,
            )
        )


def _check_go_panic_usage(issues, idx, line, line_lower, thresholds):
    if re.search(r"panic\(", line) and "test" not in line_lower:
        issues.append(
            build_issue(
                thresholds,
                "error-handling",
                "Panic Usage",
                f"Panic on line {idx} - not for production.",
                76,
                "Return error instead.",
                idx,
                line.strip(),
                confidence=0.85,
            )
        )




def _check_go_map_init(issues, idx, line, thresholds):
    if re.search(r"make\(map\[", line) and "len(" not in line:
        issues.append(
            build_issue(
                thresholds,
                "performance",
                "Uninitialized Map",
                f"Map created without size hint on line {idx}.",
                48,
                "Provide size hint if known.",
                idx,
                line.strip(),
                confidence=0.70,
            )
        )


def _check_go_crypto(issues, idx, line, thresholds):
    if re.search(r"crypto/md5|crypto/sha1", line):
        issues.append(
            build_issue(
                thresholds,
                "security",
                ISSUE_WEAK_CRYPTO,
                f"Weak hash on line {idx}.",
                83,
                "Use sha256 or stronger.",
                idx,
                line.strip(),
                confidence=0.87,
            )
        )


def generate_summary(issues: list[Issue]) -> str:
    if not issues:
        return "No major slop detected. Code appears clean with minor improvements possible."
    critical = sum(1 for issue in issues if issue.severity == "critical")
    high = sum(1 for issue in issues if issue.severity == "high")
    return f"Detected {len(issues)} issues ({critical} critical, {high} high). Prioritize security and complexity fixes first."


def generate_documentation(code: str, language: str) -> str:
    lines = code.splitlines()
    function_docs: list[str] = []
    if language.lower() == "python":
        for line in lines:
            match = re.search(r"^\s*def\s+(\w+)\((.*?)\):", line)
            if match:
                function_docs.append(f"- `{match.group(1)}`({match.group(2)})")
    else:
        for line in lines:
            match = re.search(r"^\s*function\s+(\w+)\((.*?)\)", line)
            arrow_match = re.search(r"^\s*const\s+(\w+)\s*=\s*\((.*?)\)\s*=>", line)
            if match:
                function_docs.append(f"- `{match.group(1)}`({match.group(2)})")
            elif arrow_match:
                function_docs.append(
                    f"- `{arrow_match.group(1)}`({arrow_match.group(2)})"
                )

    documentation = [
        "# Generated Documentation",
        "",
        "## Purpose",
        "This file was analyzed by Slop and Code Doctor to improve maintainability and clarity.",
        "",
        "## Main Functions",
    ]
    if function_docs:
        documentation.extend(function_docs)
    else:
        documentation.append("- No explicit function signatures were detected.")

    documentation.extend(
        [
            "",
            "## Suggested Next Docs Steps",
            "- Add module-level overview and architecture notes.",
            "- Add argument/return type descriptions for public functions.",
            "- Include examples for edge cases and failure behavior.",
        ]
    )

    return "\n".join(documentation)


def parse_json_from_text(text: str) -> dict[str, Any] | None:
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{[\s\S]*\}", text)
        if not match:
            return None
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            return None


def get_encryption_cipher() -> Fernet:
    # Use standardized MONGO_URL constant for consistency
    base_secret = (
        f"{MONGO_URL}:{os.environ.get('DB_NAME', 'drcode')}:slop-code-doctor".encode(
            "utf-8"
        )
    )
    digest = hashlib.sha256(base_secret).digest()
    return Fernet(base64.urlsafe_b64encode(digest))


def encrypt_value(value: str) -> str:
    if not value:
        return ""
    cipher = get_encryption_cipher()
    return cipher.encrypt(value.encode("utf-8")).decode("utf-8")


def decrypt_value(value: str | None) -> str | None:
    if not value:
        return None
    cipher = get_encryption_cipher()
    try:
        return cipher.decrypt(value.encode("utf-8")).decode("utf-8")
    except (InvalidToken, ValueError):
        return None


def mask_key(value: str) -> str:
    if len(value) <= 8:
        return "*" * len(value)
    return f"{value[:4]}...{value[-4:]}"


def build_default_provider_config(provider: str) -> dict[str, Any]:
    return {
        "enabled": False,
        "base_url": DEFAULT_BASE_URLS[provider],
        "model": DEFAULT_MODELS[provider],
        "api_key_encrypted": None,
        "api_key_masked": None,
        "key_configured": False,
    }


def build_default_settings_doc() -> dict[str, Any]:
    providers = {
        provider: build_default_provider_config(provider) for provider in PROVIDER_KEYS
    }

    # v2: Unified multi-provider bootstrap from environment
    active_provider = os.environ.get("ACTIVE_PROVIDER", "ollama").lower()
    ai_model_name = os.environ.get("AI_MODEL_NAME")

    # Enable chosen provider and set model/key if present
    if active_provider in providers:
        providers[active_provider]["enabled"] = True
        if ai_model_name:
            providers[active_provider]["model"] = ai_model_name

        # Automatically pick up API keys from env if they follow the pattern (e.g. OPENAI_API_KEY)
        env_key = f"{active_provider.upper()}_API_KEY"
        if os.environ.get(env_key):
            val = os.environ[env_key]
            providers[active_provider]["api_key_encrypted"] = encrypt_value(val)
            providers[active_provider]["api_key_masked"] = mask_key(val)
            providers[active_provider]["key_configured"] = True

    # Ollama special handling for backward compatibility and auto-discovery
    if active_provider == "ollama":
        ollama_base_url, ollama_model = discover_ollama_url()
        providers["ollama"]["base_url"] = os.environ.get(
            "OLLAMA_BASE_URL", ollama_base_url
        )
        providers["ollama"]["model"] = os.environ.get("OLLAMA_MODEL", ollama_model)
        providers["ollama"]["enabled"] = True
    else:
        # If not using Ollama as primary, still try to detect if it's there but keep it disabled by default
        # unless it was specifically chosen.
        pass
    # v2: GitHub integration block — token stored encrypted, same pattern as AI provider keys
    github_token_env = os.environ.get("GITHUB_TOKEN")
    github_webhook_secret_env = os.environ.get("GITHUB_WEBHOOK_SECRET")
    github_block: dict[str, Any] = {
        "token_encrypted": (
            encrypt_value(github_token_env) if github_token_env else None
        ),
        "token_masked": mask_key(github_token_env) if github_token_env else None,
        "token_configured": bool(github_token_env),
        "webhook_secret_encrypted": (
            encrypt_value(github_webhook_secret_env)
            if github_webhook_secret_env
            else None
        ),
        "webhook_secret_configured": bool(github_webhook_secret_env),
    }

    return {
        "id": "default",
        "severity": SeverityThresholds().model_dump(),
        "providers": providers,
        "routing": {
            "primary_provider": "ollama",
            "fallback_enabled": True,
            "fallback_provider": "openai_compatible",
        },
        "github": github_block,
    }


def normalize_settings_doc(raw: dict[str, Any]) -> dict[str, Any]:
    normalized = build_default_settings_doc()
    normalized["severity"] = SeverityThresholds(
        **raw.get("severity", normalized["severity"])
    ).model_dump()

    providers_payload = raw.get("providers")
    if isinstance(providers_payload, dict):
        for provider in PROVIDER_KEYS:
            merged = {
                **normalized["providers"][provider],
                **providers_payload.get(provider, {}),
            }
            normalized["providers"][provider] = merged
    else:
        normalized["providers"]["ollama"]["enabled"] = bool(
            raw.get("use_ollama", normalized["providers"]["ollama"]["enabled"])
        )
        if raw.get("ollama_base_url"):
            normalized["providers"]["ollama"]["base_url"] = raw["ollama_base_url"]
        if raw.get("ollama_model"):
            normalized["providers"]["ollama"]["model"] = raw["ollama_model"]

    routing_payload = raw.get("routing")
    if isinstance(routing_payload, dict):
        normalized["routing"] = {
            "primary_provider": routing_payload.get(
                "primary_provider", normalized["routing"]["primary_provider"]
            ),
            "fallback_enabled": bool(
                routing_payload.get(
                    "fallback_enabled", normalized["routing"]["fallback_enabled"]
                )
            ),
            "fallback_provider": routing_payload.get(
                "fallback_provider", normalized["routing"]["fallback_provider"]
            ),
        }

    if normalized["routing"]["primary_provider"] not in PROVIDER_KEYS:
        normalized["routing"]["primary_provider"] = "ollama"
    fallback_provider = normalized["routing"].get("fallback_provider")
    if fallback_provider not in PROVIDER_KEYS:
        normalized["routing"]["fallback_provider"] = "openai_compatible"

    # Preserve github integration config across normalizations
    if "github" in raw and isinstance(raw["github"], dict):
        normalized["github"] = raw["github"]

    return normalized


def to_public_settings(raw: dict[str, Any]) -> AnalyzerSettings:
    normalized = normalize_settings_doc(raw)
    ollama_conf = normalized["providers"]["ollama"]
    return AnalyzerSettings(
        id=normalized["id"],
        use_ollama=bool(ollama_conf.get("enabled")),
        ollama_base_url=ollama_conf.get("base_url"),
        ollama_model=ollama_conf.get("model"),
        severity=SeverityThresholds(**normalized["severity"]),
        providers={
            provider: {
                "enabled": bool(config.get("enabled")),
                "base_url": config.get("base_url"),
                "model": config.get("model"),
                "key_configured": bool(config.get("key_configured")),
                "api_key_masked": config.get("api_key_masked"),
            }
            for provider, config in normalized["providers"].items()
        },
        routing=normalized["routing"],
    )


ANALYSIS_SYSTEM_PROMPT = """You are DR.CODE, a strict code quality analyzer. Analyze code and return ONLY valid JSON.

CATEGORIES:
- security: vulnerabilities, secrets, injection risks
- performance: inefficient code, memory issues
- maintainability: complexity, duplication, coupling
- best_practices: error handling, type safety, documentation
- slop: AI-generated low-quality patterns, bad practices
- documentation: missing docs, unclear comments

SEVERITY SCALE:
- critical (90-100): security vulnerabilities, data exposure, system break
- high (70-89): serious bugs, performance issues, major risks
- medium (45-69): code smells, maintainability concerns
- low (0-44): style, minor improvements

OUTPUT JSON STRICT FORMAT:
{
  "issues": [
    {
      "category": "security|performance|maintenance|best_practices|slop|documentation",
      "severity": "critical|high|medium|low",
      "title": "Brief issue name",
      "detail": "Description of the issue",
      "line": number or null,
      "confidence": 0.0-1.0,
      "fix_suggestion": "How to fix this issue"
    }
  ],
  "summary": "1-2 sentence overall assessment"
}

RULES:
- Return ONLY valid JSON, no markdown, no explanation
- Always include all required keys in each issue
- confidence must be a number between 0.0 and 1.0
- severity must be exactly: critical, high, medium, or low
- category must be exactly one of the allowed categories
- If no issues found, return empty issues array
- Analyze ALL lines of code, not just a sample
- Be thorough - missing issues is worse than false positives"""


def build_analysis_prompt(code: str, language: str) -> str:
    return (
        f"{ANALYSIS_SYSTEM_PROMPT}\n\nLanguage: {language}\n\nCode to analyze:\n{code}"
    )


def call_provider_ollama(prompt: str, config: dict[str, Any]) -> str | None:
    response = requests.post(
        f"{config['base_url'].rstrip('/')}/api/generate",
        json={"model": config["model"], "prompt": prompt, "stream": False},
        timeout=25,
    )
    if response.status_code != 200:
        return None
    return response.json().get("response")


def call_provider_openai_compatible(
    prompt: str, config: dict[str, Any], api_key: str
) -> str | None:
    response = requests.post(
        f"{config['base_url'].rstrip('/')}/chat/completions",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        json={
            "model": config["model"],
            "temperature": 0.1,
            "messages": [
                {"role": "system", "content": "You return strict JSON only."},
                {"role": "user", "content": prompt},
            ],
        },
        timeout=30,
    )
    if response.status_code != 200:
        return None
    choices = response.json().get("choices", [])
    if not choices:
        return None
    return choices[0].get("message", {}).get("content")


def call_provider_gemini(
    prompt: str, config: dict[str, Any], api_key: str
) -> str | None:
    response = requests.post(
        f"{config['base_url'].rstrip('/')}/models/{config['model']}:generateContent?key={api_key}",
        headers={"Content-Type": "application/json"},
        json={"contents": [{"parts": [{"text": prompt}]}]},
        timeout=30,
    )
    if response.status_code != 200:
        return None
    candidates = response.json().get("candidates", [])
    if not candidates:
        return None
    parts = candidates[0].get("content", {}).get("parts", [])
    if not parts:
        return None
    return parts[0].get("text")


def call_provider_anthropic(
    prompt: str, config: dict[str, Any], api_key: str
) -> str | None:
    response = requests.post(
        f"{config['base_url'].rstrip('/')}/messages",
        headers={
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json",
        },
        json={
            "model": config["model"],
            "max_tokens": 800,
            "messages": [{"role": "user", "content": prompt}],
        },
        timeout=30,
    )
    if response.status_code != 200:
        return None
    content = response.json().get("content", [])
    if not content:
        return None
    return content[0].get("text")


def call_llm_sync(
    code: str, language: str, settings_doc: dict[str, Any]
) -> dict[str, Any] | None:
    prompt = build_analysis_prompt(code, language)
    providers = settings_doc.get("providers", {})
    routing = settings_doc.get("routing", {})
    primary = routing.get("primary_provider", "ollama")
    order = [primary]
    if routing.get("fallback_enabled"):
        fallback = routing.get("fallback_provider")
        if fallback and fallback not in order:
            order.append(fallback)

    for provider_name in order:
        config = providers.get(provider_name) or {}
        if not config.get("enabled"):
            continue
        try:
            raw_response = _dispatch_provider_call(provider_name, prompt, config)
            if not raw_response:
                continue
            parsed = parse_json_from_text(raw_response)
            if parsed:
                parsed["provider_used"] = provider_name
                return parsed
        except requests.RequestException:
            continue

    return None


def _dispatch_provider_call(
    provider_name: str, prompt: str, config: dict[str, Any]
) -> str | None:
    """Internal dispatcher for different AI providers."""
    if provider_name == "ollama":
        return call_provider_ollama(prompt, config)
    if provider_name == "local" and call_provider_local is not None:
        return call_provider_local(prompt, config)

    # Providers requiring API keys
    api_key = decrypt_value(config.get("api_key_encrypted"))
    if not api_key:
        return None

    if provider_name == "openai_compatible":
        return call_provider_openai_compatible(prompt, config, api_key)
    if provider_name == "gemini":
        return call_provider_gemini(prompt, config, api_key)
    if provider_name == "anthropic":
        return call_provider_anthropic(prompt, config, api_key)
    return None


async def call_llm_analysis(
    code: str, language: str, settings_doc: dict[str, Any]
) -> dict[str, Any] | None:
    return await asyncio.to_thread(call_llm_sync, code, language, settings_doc)


def _ping_ollama(base_url: str) -> bool:
    try:
        ping = requests.get(f"{base_url.rstrip('/')}/api/tags", timeout=3)
        return ping.status_code == 200
    except requests.RequestException:
        return False


async def check_ollama_ready(base_url: str | None) -> bool:
    if not base_url:
        return False
    return await asyncio.to_thread(_ping_ollama, base_url)


def get_file_extension(file_path: str) -> str:
    return Path(file_path).suffix.lower()


def detect_language_from_path(file_path: str) -> str:
    extension = get_file_extension(file_path)
    if extension == ".py":
        return "python"
    if extension in {".js", ".jsx"}:
        return "javascript"
    if extension in {".ts", ".tsx"}:
        return "typescript"
    return "text"


def is_supported_repo_file(file_path: str) -> bool:
    return get_file_extension(file_path) in SUPPORTED_REPO_EXTENSIONS


def to_env_name(variable_name: str) -> str:
    return (
        re.sub(r"[^A-Za-z0-9]+", "_", variable_name).upper().strip("_")
        or "SECRET_VALUE"
    )


def build_repository_summary(fixes: list[FixProposal], file_count: int) -> str:
    if not fixes:
        return f"Scanned {file_count} files. No auto-applicable fixes found."
    critical_count = sum(1 for fix in fixes if fix.severity == "critical")
    high_count = sum(1 for fix in fixes if fix.severity == "high")
    return (
        f"Scanned {file_count} files and found {len(fixes)} fix candidates "
        f"({critical_count} critical, {high_count} high)."
    )


def generate_repository_fix_proposals(
    files: list[RepositoryFile], thresholds: SeverityThresholds
) -> list[FixProposal]:
    proposals: list[FixProposal] = []

    for repo_file in files:
        extension = get_file_extension(repo_file.path)
        if extension not in {".py", ".js", ".jsx"}:
            continue

        lines = repo_file.content.splitlines()
        for idx, line in enumerate(lines, start=1):
            if extension == ".py":
                secret_match = re.match(
                    r"^(\s*)([A-Za-z_]\w*)\s*=\s*['\"][^'\"]+['\"]\s*$", line
                )
                if secret_match:
                    indent, var_name = secret_match.group(1), secret_match.group(2)
                    if re.search(
                        r"(password|secret|token|api_key)", var_name, re.IGNORECASE
                    ):
                        env_name = to_env_name(var_name)
                        replacement_line = (
                            f'{indent}{var_name} = os.environ.get("{env_name}")'
                        )
                        proposals.append(
                            FixProposal(
                                file_path=repo_file.path,
                                line_number=idx,
                                title="Replace hardcoded secret",
                                detail="Use environment variable lookup instead of hardcoded credential.",
                                severity=score_to_severity(92, thresholds),
                                score=92,
                                original_line=line,
                                replacement_line=replacement_line,
                            )
                        )

                eval_assign_match = re.match(
                    r"^(\s*)([A-Za-z_]\w*)\s*=\s*eval\((.+)\)\s*$", line
                )
                if eval_assign_match:
                    indent, lhs, expression = (
                        eval_assign_match.group(1),
                        eval_assign_match.group(2),
                        eval_assign_match.group(3).strip(),
                    )
                    replacement_line = f"{indent}{lhs} = ast.literal_eval({expression})"
                    proposals.append(
                        FixProposal(
                            file_path=repo_file.path,
                            line_number=idx,
                            title="Safer evaluation method",
                            detail="Replace eval() with ast.literal_eval() for safer parsing.",
                            severity=score_to_severity(86, thresholds),
                            score=86,
                            original_line=line,
                            replacement_line=replacement_line,
                        )
                    )

            if extension in {".js", ".jsx"}:
                js_secret_match = re.match(
                    r"^(\s*)(?:(const|let|var)\s+)?([A-Za-z_$][A-Za-z0-9_$]*)\s*=\s*['\"][^'\"]+['\"]\s*;?\s*$",
                    line,
                )
                if js_secret_match:
                    indent, declaration, var_name = (
                        js_secret_match.group(1),
                        js_secret_match.group(2),
                        js_secret_match.group(3),
                    )
                    if re.search(
                        r"(password|secret|token|api_key)", var_name, re.IGNORECASE
                    ):
                        env_name = to_env_name(var_name)
                        declaration_prefix = f"{declaration} " if declaration else ""
                        replacement_line = f"{indent}{declaration_prefix}{var_name} = process.env.{env_name};"
                        proposals.append(
                            FixProposal(
                                file_path=repo_file.path,
                                line_number=idx,
                                title="Replace hardcoded secret",
                                detail="Use process.env to avoid committed credentials.",
                                severity=score_to_severity(90, thresholds),
                                score=90,
                                original_line=line,
                                replacement_line=replacement_line,
                            )
                        )

    return proposals[:500]


def ensure_python_import_statement(content: str, module_name: str) -> str:
    lines = content.splitlines()
    import_regex = re.compile(rf"^\s*(import\s+{module_name}\b|from\s+{module_name}\b)")
    if any(import_regex.search(line) for line in lines):
        return content

    insert_at = 0
    if lines and lines[0].startswith("#!"):
        insert_at = 1
    if len(lines) > insert_at and re.search(r"coding[:=]", lines[insert_at]):
        insert_at += 1

    while insert_at < len(lines) and re.match(
        r"^\s*from\s+__future__\s+import\b", lines[insert_at]
    ):
        insert_at += 1

    while insert_at < len(lines) and re.match(
        r"^\s*(import\s+\w+|from\s+\w+\s+import\b)", lines[insert_at]
    ):
        insert_at += 1

    lines.insert(insert_at, f"import {module_name}")
    updated = "\n".join(lines)
    if content.endswith("\n"):
        updated += "\n"
    return updated


def apply_fix_to_content(content: str, fix: dict[str, Any]) -> tuple[str, bool]:
    lines = content.splitlines()
    line_number = fix.get("line_number", 0)
    if line_number < 1 or line_number > len(lines):
        return content, False

    original_line = fix.get("original_line", "")
    if lines[line_number - 1].strip() != original_line.strip():
        return content, False

    lines[line_number - 1] = fix.get("replacement_line", lines[line_number - 1])
    updated = "\n".join(lines)
    if content.endswith("\n"):
        updated += "\n"
    return updated, True


def validate_python_syntax(file_path: str, content: str) -> str | None:
    try:
        compile(content, file_path, "exec")
        return None
    except SyntaxError as error:
        return f"{file_path}: Python syntax error on line {error.lineno}: {error.msg}"


def validate_javascript_syntax(file_path: str, content: str) -> str | None:
    temp_path = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            suffix=get_file_extension(file_path),
            delete=False,
            encoding="utf-8",
        ) as temp_file:
            temp_file.write(content)
            temp_path = temp_file.name

        result = subprocess.run(
            ["node", "--check", temp_path],
            capture_output=True,
            text=True,
            timeout=12,
            check=False,
        )
        if result.returncode != 0:
            stderr = result.stderr.strip() or "unknown syntax error"
            return f"{file_path}: JavaScript syntax check failed: {stderr}"
        return None
    except FileNotFoundError:
        return None
    except subprocess.TimeoutExpired:
        return f"{file_path}: JavaScript syntax check timed out"
    finally:
        if temp_path and os.path.exists(temp_path):
            os.remove(temp_path)


def validate_updated_repository_files(
    updated_files: dict[str, str], changed_paths: list[str]
) -> str | None:
    for file_path in changed_paths:
        extension = get_file_extension(file_path)
        content = updated_files[file_path]
        if extension == ".py":
            syntax_error = validate_python_syntax(file_path, content)
            if syntax_error:
                return syntax_error
        if extension in {".js", ".jsx"}:
            syntax_error = validate_javascript_syntax(file_path, content)
            if syntax_error:
                return syntax_error
    return None


async def get_or_create_settings_doc() -> dict[str, Any]:
    existing = await db.app_settings.find_one({"id": "default"}, {"_id": 0})
    if existing:
        normalized = normalize_settings_doc(existing)
        if normalized != existing:
            await db.app_settings.update_one(
                {"id": "default"}, {"$set": normalized}, upsert=True
            )
        return normalized

    initial = build_default_settings_doc()
    await db.app_settings.insert_one(initial)
    return initial


@api_router.get("/")
async def api_root():
    return {"name": "DR.CODE-II API", "version": "2.0.0", "status": "running"}


@api_router.get("/health")
async def health():
    settings_doc = await get_or_create_settings_doc()
    ollama_config = settings_doc.get("providers", {}).get("ollama", {})
    ollama_ready = (
        await check_ollama_ready(ollama_config.get("base_url"))
        if ollama_config.get("enabled")
        else False
    )
    active_provider = settings_doc.get("routing", {}).get("primary_provider", "ollama")
    return {
        "status": "ok",
        "ollama_configured": bool(
            ollama_config.get("enabled")
            and ollama_config.get("base_url")
            and ollama_config.get("model")
        ),
        "ollama_ready": ollama_ready,
        "active_provider": active_provider,
    }


@api_router.post(
    "/analyze",
    response_model=AnalysisReport,
    responses={
        400: {"description": "Invalid source code or configuration"},
        401: {"description": "Unauthorized access or missing credentials"},
        404: {"description": "Specified AI provider or model not found"},
    },
)
async def analyze_endpoint(
    payload: AnalyzeRequest,
    x_actor_id: Annotated[str | None, Header()] = None,
    x_user_role: Annotated[str | None, Header()] = None,
):
    started_at = perf_counter()
    actor = resolve_actor_context(x_actor_id, x_user_role)
    settings_doc = await get_or_create_settings_doc()
    thresholds = SeverityThresholds(**settings_doc["severity"])
    policy = await get_or_create_governance_policy()
    cleaned_code = payload.code.strip()
    if not cleaned_code:
        raise HTTPException(status_code=400, detail="Code input cannot be empty")

    quality_checks = run_data_validation_checks(cleaned_code, payload.language, policy)
    ensure_checks_pass(quality_checks)

    issues = rule_based_slop_detection(cleaned_code, payload.language, thresholds)
    routing = settings_doc.get("routing", {})
    selected_provider = routing.get("primary_provider", "ollama")
    provider_allowed = selected_provider in policy.allowed_providers
    ai_payload = None
    if provider_allowed:
        ai_payload = await call_llm_analysis(
            cleaned_code, payload.language, settings_doc
        )
    else:
        await record_security_event(
            severity="medium",
            event_type="provider-blocked-by-policy",
            actor=actor,
            details={"provider": selected_provider, "policy_version": policy.version},
        )

    if ai_payload:
        mode = "hybrid"
        _merge_ai_results(issues, ai_payload, thresholds)

    report = _build_analysis_report(
        payload,
        cleaned_code,
        issues,
        ai_payload,
        mode,
        quality_checks,
        started_at,
        policy,
        selected_provider,
        provider_allowed,
    )

    await _persist_analysis_report(report, actor, mode, selected_provider, started_at)
    return report


async def _persist_analysis_report(
    report: AnalysisReport,
    actor: ActorContext,
    mode: str,
    provider: str,
    started_at: float,
):
    """Save report and metrics to database and record governance event."""
    await db.reports.insert_one(report.model_dump())

    analysis_ms = round((perf_counter() - started_at) * 1000, 2)
    critical_count = sum(1 for issue in report.issues if issue.severity == "critical")

    await db.quality_metrics.insert_one(
        {
            "metric_id": str(uuid.uuid4()),
            "created_at": datetime.now(timezone.utc).isoformat(),
            "report_id": report.report_id,
            "analysis_ms": analysis_ms,
            "issue_count": len(report.issues),
            "critical_count": critical_count,
            "mode": mode,
        }
    )

    await record_governance_event(
        actor=actor,
        action="analysis-run",
        status=STATUS_SUCCESS,
        details={
            "report_id": report.report_id,
            "mode": mode,
            "provider": provider,
            "critical_count": critical_count,
        },
    )


def _build_analysis_report(
    payload: AnalyzeRequest,
    code: str,
    issues: list[Issue],
    ai_payload: dict[str, Any] | None,
    mode: str,
    quality_checks: list[dict[str, Any]],
    started_at: float,
    policy: GovernancePolicy,
    provider: str,
    provider_allowed: bool,
) -> AnalysisReport:
    """Consolidate all analysis data into a structured report."""
    redacted_issues = [redact_issue(issue) for issue in issues]
    critical_count = sum(1 for issue in redacted_issues if issue.severity == "critical")

    ai_notes = None
    documentation = generate_documentation(code, payload.language)
    if ai_payload:
        ai_notes = ai_payload.get("summary") or ai_payload.get("ai_notes")
        if ai_payload.get("documentation"):
            documentation = ai_payload["documentation"]

    return AnalysisReport(
        filename=payload.filename or "untitled",
        language=payload.language,
        source_code=code,
        summary=generate_summary(redacted_issues),
        issues=redacted_issues,
        documentation=documentation,
        ai_notes=ai_notes,
        mode=mode,
        governance={
            "policy_version": policy.version,
            "provider_allowed": provider_allowed,
            "primary_provider": provider,
            "requires_reviewer_approval": bool(
                policy.require_reviewer_for_high_risk and critical_count > 0
            ),
            "transparency_mode": "detailed",
        },
        quality_checks=quality_checks,
        monitoring={
            "analysis_ms": round((perf_counter() - started_at) * 1000, 2),
            "issue_count": len(redacted_issues),
            "critical_count": critical_count,
        },
    )


def _merge_ai_results(
    issues: list[Issue], ai_payload: dict[str, Any], thresholds: SeverityThresholds
):
    """Normalize and inject AI-detected issues and suggestions into the results list."""
    provider_used = ai_payload.get("provider_used", "llm")
    severity_map = {"critical": 95, "high": 75, "medium": 55, "low": 25}

    for llm_issue in ai_payload.get("issues", []):
        severity_score = severity_map.get(
            llm_issue.get("severity", "medium").lower(), 55
        )
        issues.append(
            build_issue(
                thresholds,
                llm_issue.get("category", "maintenance"),
                llm_issue.get("title", "AI Detected Issue"),
                llm_issue.get("detail", ""),
                severity_score,
                llm_issue.get("fix_suggestion", "Review and fix as needed."),
                llm_issue.get("line"),
                source=provider_used,
                confidence=llm_issue.get("confidence", 0.7),
                risk_tags=["ai-detected", llm_issue.get("category", "unknown")],
                decision_trace=[
                    f"LLM provider '{provider_used}' detected issue",
                    f"Category: {llm_issue.get('category')}",
                    f"Severity: {llm_issue.get('severity')}",
                ],
            )
        )

    for suggestion in ai_payload.get("extra_suggestions", [])[:4]:
        issues.append(
            build_issue(
                thresholds,
                "ai-suggestion",
                "AI Refactor Opportunity",
                suggestion,
                49,
                "Apply the suggestion and rerun analysis to confirm improvement.",
                source=provider_used,
                confidence=0.61,
                risk_tags=["ai-suggestion", "refactor"],
                decision_trace=[f"LLM provider '{provider_used}' returned suggestion"],
            )
        )


@api_router.post(
    "/generate/tests",
    response_model=GenerateTestsResponse,
    responses={400: {"description": "Invalid code or test framework specified"}},
)
async def generate_tests_endpoint(payload: GenerateTestsRequest):

    sanitizer_flag = getattr(payload, "sanitizer", True)
    result = generate_tests(
        code=payload.code,
        language=payload.language,
        framework=payload.framework,
        include_edge_cases=payload.include_edge_cases,
        sanitizer_enabled=sanitizer_flag,
    )
    return GenerateTestsResponse(**result)


@api_router.post(
    "/generate/docstrings",
    response_model=GenerateDocstringsResponse,
    responses={400: {"description": "Invalid code or docstring style specified"}},
)
async def generate_docstrings_endpoint(payload: GenerateDocstringsRequest):

    sanitizer_flag = getattr(payload, "sanitizer", True)
    result = generate_docstrings(
        code=payload.code,
        language=payload.language,
        style=payload.style,
        sanitizer_enabled=sanitizer_flag,
    )
    return GenerateDocstringsResponse(**result)


@api_router.post(
    "/generate/diagram",
    response_model=GenerateDiagramResponse,
    responses={400: {"description": "Invalid code or diagram type specified"}},
)
async def generate_diagram_endpoint(payload: GenerateDiagramRequest):

    sanitizer_flag = getattr(payload, "sanitizer", True)
    result = generate_diagram(
        code=payload.code,
        language=payload.language,
        diagram_type=payload.diagram_type,
        sanitizer_enabled=sanitizer_flag,
    )
    return GenerateDiagramResponse(**result)


@api_router.get("/reports", response_model=list[ReportSummary])
async def list_reports():
    docs = (
        await db.reports.find(
            {}, {"_id": 0, "source_code": 0, "documentation": 0, "ai_notes": 0}
        )
        .sort("created_at", -1)
        .to_list(200)
    )
    summaries: list[ReportSummary] = []
    for doc in docs:
        issues = doc.get("issues", [])
        summaries.append(
            ReportSummary(
                report_id=doc["report_id"],
                created_at=doc["created_at"],
                filename=doc.get("filename", "untitled"),
                language=doc.get("language", "unknown"),
                summary=doc.get("summary", ""),
                mode=doc.get("mode", "rule-based"),
                issue_count=len(issues),
                critical_count=sum(
                    1 for issue in issues if issue.get("severity") == "critical"
                ),
            )
        )
    return summaries


@api_router.get(
    "/reports/{report_id}",
    response_model=AnalysisReport,
    responses={404: {"description": "Analysis report not found"}},
)
async def get_report(report_id: str):
    doc = await db.reports.find_one({"report_id": report_id}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail="Report not found")
    return AnalysisReport(**doc)


@api_router.post(
    "/repository/analyze",
    response_model=RepositoryAnalysisResult,
    responses={
        400: {"description": "No supported files found or payload size exceeded"}
    },
)
async def analyze_repository(payload: RepositoryAnalyzeRequest):
    """Scan a repository payload, generate fix proposals, and persist as a session."""
    settings_doc = await get_or_create_settings_doc()
    thresholds = SeverityThresholds(**settings_doc["severity"])
    supported_files = [
        RepositoryFile(path=file.path, content=file.content)
        for file in payload.files
        if is_supported_repo_file(file.path)
    ]

    if not supported_files:
        raise HTTPException(
            status_code=400, detail="No supported files found in repository payload"
        )

    proposals = generate_repository_fix_proposals(supported_files, thresholds)
    return await _build_analysis_session(
        payload.repository_name, supported_files, proposals
    )


async def _build_analysis_session(
    repo_name: str, files: list[RepositoryFile], proposals: list[FixProposal]
) -> RepositoryAnalysisResult:
    """Internal helper to persist analysis results and return the session metadata."""
    created_at = datetime.now(timezone.utc).isoformat()
    session_id = str(uuid.uuid4())

    session_doc = {
        "session_id": session_id,
        "repository_name": repo_name,
        "created_at": created_at,
        "status": MSG_REPO_ANALYZED,
        "summary": build_repository_summary(proposals, len(files)),
        "file_count": len(files),
        "files": [f.model_dump() for f in files],
        "fixes": [p.model_dump() for p in proposals],
        "applied_fix_count": 0,
    }
    await db.repository_sessions.insert_one(session_doc)

    return RepositoryAnalysisResult(
        session_id=session_id,
        repository_name=repo_name,
        created_at=created_at,
        file_count=len(files),
        status=MSG_REPO_ANALYZED,
        summary=str(session_doc["summary"]),
        fixes=proposals,
        applied_fix_count=0,
    )


@api_router.get(
    "/repository/sessions/{session_id}",
    response_model=RepositoryAnalysisResult,
    responses={404: {"description": ERROR_SESSION_NOT_FOUND}},
)
async def get_repository_session(session_id: str):
    session = await db.repository_sessions.find_one(
        {"session_id": session_id}, {"_id": 0}
    )
    if not session:
        raise HTTPException(status_code=404, detail="Repository session not found")

    return RepositoryAnalysisResult(
        session_id=session["session_id"],
        repository_name=session["repository_name"],
        created_at=session["created_at"],
        file_count=session["file_count"],
        status=session["status"],
        summary=session["summary"],
        fixes=[FixProposal(**fix) for fix in session.get("fixes", [])],
        applied_fix_count=session.get("applied_fix_count", 0),
    )


@api_router.post(
    "/repository/apply-fixes",
    response_model=ApplyRepositoryFixesResponse,
    responses={
        400: {"description": "Invalid fix selection or non-auto-applicable fixes"},
        404: {"description": ERROR_SESSION_NOT_FOUND},
    },
)
async def apply_repository_fixes(payload: ApplyRepositoryFixesRequest):
    session = await db.repository_sessions.find_one(
        {"session_id": payload.session_id}, {"_id": 0}
    )
    if not session:
        raise HTTPException(status_code=404, detail="Repository session not found")

    all_fixes = session.get("fixes", [])
    selected_ids = (
        {fix["fix_id"] for fix in all_fixes}
        if payload.approve_all
        else set(payload.approved_fix_ids)
    )
    if not selected_ids:
        raise HTTPException(
            status_code=400, detail="Select at least one fix or use approve_all"
        )

    file_map: dict[str, str] = {
        file["path"]: file["content"] for file in session.get("files", [])
    }
    fixes_by_file: dict[str, list[dict[str, Any]]] = {}
    for fix in all_fixes:
        if fix["fix_id"] in selected_ids and fix.get("auto_applicable", True):
            fixes_by_file.setdefault(fix["file_path"], []).append(fix)

    if not fixes_by_file:
        raise HTTPException(
            status_code=400, detail="No auto-applicable fixes were selected"
        )

    applied_ids, changed_paths = _apply_fixes_to_files(file_map, fixes_by_file)

    if not changed_paths:
        raise HTTPException(
            status_code=400, detail="No fixes could be applied due to line mismatches"
        )

    syntax_error = validate_updated_repository_files(file_map, changed_paths)
    if syntax_error:
        raise HTTPException(
            status_code=400,
            detail=(
                "Fix application blocked because validation failed. " f"{syntax_error}"
            ),
        )

    now = datetime.now(timezone.utc).isoformat()
    updated_fixes: list[dict[str, Any]] = []
    for fix in all_fixes:
        if fix["fix_id"] in selected_ids:
            fix["approved"] = True
        if fix["fix_id"] in applied_ids:
            fix["applied_at"] = now
        updated_fixes.append(fix)

    patched_files = [
        {"path": path, "content": content} for path, content in file_map.items()
    ]
    await db.repository_sessions.update_one(
        {"session_id": payload.session_id},
        {
            "$set": {
                "status": "applied",
                "updated_at": now,
                "fixes": updated_fixes,
                "applied_fix_count": len(applied_ids),
                "patched_files": patched_files,
            }
        },
    )

    return ApplyRepositoryFixesResponse(
        session_id=payload.session_id,
        status="applied",
        applied_fix_count=len(applied_ids),
        updated_file_count=len(changed_paths),
        message="Selected fixes were applied and validated successfully.",
    )


@api_router.get(
    "/repository/sessions/{session_id}/download",
    responses={
        404: {"description": ERROR_SESSION_NOT_FOUND},
        400: {"description": "Session contains no patched files"},
    },
)
async def download_patched_repository(session_id: str):
    session = await db.repository_sessions.find_one(
        {"session_id": session_id},
        {"_id": 0, "repository_name": 1, "patched_files": 1},
    )
    if not session:
        raise HTTPException(status_code=404, detail="Repository session not found")

    patched_files = session.get("patched_files")
    if not patched_files:
        raise HTTPException(
            status_code=400, detail="No patched repository is available for download"
        )

    buffer = io.BytesIO()
    with zipfile.ZipFile(
        buffer, mode="w", compression=zipfile.ZIP_DEFLATED
    ) as zip_stream:
        for file in patched_files:
            zip_stream.writestr(file["path"], file["content"])
    buffer.seek(0)

    repository_name = re.sub(
        r"[^a-zA-Z0-9_-]", "-", session.get("repository_name", "repository")
    )
    headers = {
        "Content-Disposition": f'attachment; filename="{repository_name}-patched.zip"'
    }
    return StreamingResponse(buffer, media_type="application/zip", headers=headers)


def _apply_fixes_to_files(
    file_map: dict[str, str], fixes_by_file: dict[str, list[dict[str, Any]]]
) -> tuple[list[str], list[str]]:
    """Helper to iterate through files and apply their respective fixes."""
    applied_ids = []
    changed_paths = []

    for file_path, file_fixes in fixes_by_file.items():
        original_content = file_map.get(file_path)
        if original_content is None:
            continue

        updated_content = original_content
        # Sort fixes in reverse line order to prevent offset corruption
        for fix in sorted(
            file_fixes, key=lambda item: item.get("line_number", 0), reverse=True
        ):
            updated_content, applied = apply_fix_to_content(updated_content, fix)
            if applied:
                applied_ids.append(fix["fix_id"])

        if updated_content != original_content:
            updated_content = _ensure_required_imports(file_path, updated_content)
            file_map[file_path] = updated_content
            changed_paths.append(file_path)

    return applied_ids, changed_paths


def _ensure_required_imports(file_path: str, content: str) -> str:
    """Add missing imports if specific patterns are found in the modified content."""
    if get_file_extension(file_path) == ".py":
        if "os.environ.get(" in content:
            content = ensure_python_import_statement(content, "os")
        if "ast.literal_eval(" in content:
            content = ensure_python_import_statement(content, "ast")
    return content


@api_router.get("/governance/policy", response_model=GovernancePolicy)
async def get_governance_policy():
    return await get_or_create_governance_policy()


@api_router.put(
    "/governance/policy",
    response_model=GovernancePolicy,
    responses={
        400: {"description": "Invalid providers"},
        403: {"description": "Admin required"},
    },
)
async def update_governance_policy(
    payload: GovernancePolicyUpdate,
    x_actor_id: Annotated[str | None, Header()] = None,
    x_user_role: Annotated[str | None, Header()] = None,
):
    actor = resolve_actor_context(x_actor_id, x_user_role)
    require_admin(actor)

    invalid = [
        provider
        for provider in payload.allowed_providers
        if provider not in PROVIDER_KEYS
    ]
    if invalid:
        raise HTTPException(
            status_code=400, detail=f"Invalid providers in policy: {invalid}"
        )

    current = await get_or_create_governance_policy()
    updated = GovernancePolicy(
        id="default",
        version=current.version + 1,
        allowed_providers=payload.allowed_providers,
        blocked_patterns=payload.blocked_patterns,
        max_code_length=payload.max_code_length,
        require_reviewer_for_high_risk=payload.require_reviewer_for_high_risk,
        min_transparency_confidence=payload.min_transparency_confidence,
        updated_at=datetime.now(timezone.utc).isoformat(),
        updated_by=actor.actor_id,
    )
    await db.governance_policies.update_one(
        {"id": "default"}, {"$set": updated.model_dump()}, upsert=True
    )
    await record_governance_event(
        actor=actor,
        action="governance-policy-update",
        status="success",
        details={
            "version": updated.version,
            "allowed_providers": payload.allowed_providers,
        },
    )
    return updated


@api_router.get("/governance/audit-logs", response_model=list[GovernanceAuditEvent])
async def get_governance_audit_logs(limit: int = 50):
    bounded_limit = max(1, min(limit, 200))
    rows = (
        await db.governance_audit_logs.find({}, {"_id": 0})
        .sort("created_at", -1)
        .to_list(bounded_limit)
    )
    return [GovernanceAuditEvent(**row) for row in rows]


@api_router.get("/security/events", response_model=list[SecurityEvent])
async def get_security_events(limit: int = 50):
    bounded_limit = max(1, min(limit, 200))
    rows = (
        await db.security_events.find({}, {"_id": 0})
        .sort("created_at", -1)
        .to_list(bounded_limit)
    )
    return [SecurityEvent(**row) for row in rows]


@api_router.get("/quality/metrics")
async def get_quality_metrics(limit: int = 50):
    bounded_limit = max(1, min(limit, 200))
    rows = (
        await db.quality_metrics.find({}, {"_id": 0})
        .sort("created_at", -1)
        .to_list(bounded_limit)
    )
    return rows


@api_router.get("/settings", response_model=AnalyzerSettings)
async def get_settings():
    settings_doc = await get_or_create_settings_doc()
    return to_public_settings(settings_doc)


@api_router.put("/settings", response_model=AnalyzerSettings)
async def update_settings(payload: AnalyzerSettingsUpdate):
    """Update global analyzer settings, severity thresholds, and provider configurations."""
    current_doc = await get_or_create_settings_doc()
    updated_doc = normalize_settings_doc(current_doc)
    updated_doc["severity"] = payload.severity.model_dump()

    # Update AI Provider configurations
    incoming_providers = payload.providers or {}
    for provider in PROVIDER_KEYS:
        updated_doc["providers"][provider] = _update_provider_config(
            updated_doc["providers"].get(provider, {}),
            incoming_providers.get(provider, {}),
            payload,
            provider,
        )

    # Update Routing logic
    updated_doc["routing"] = _update_routing_config(
        updated_doc.get("routing", {}), payload.routing or {}
    )

    await db.app_settings.update_one(
        {"id": "default"},
        {"$set": updated_doc},
        upsert=True,
    )
    return to_public_settings(updated_doc)


def _update_provider_config(
    current: dict[str, Any],
    incoming: dict[str, Any],
    payload: AnalyzerSettingsUpdate,
    provider: str,
) -> dict[str, Any]:
    """Merge incoming provider settings with existing configuration."""
    # Handle legacy top-level Ollama fields if providers dict wasn't provided
    if payload.providers is None and provider == "ollama":
        if payload.use_ollama is not None:
            incoming["enabled"] = payload.use_ollama
        if payload.ollama_base_url is not None:
            incoming["base_url"] = payload.ollama_base_url
        if payload.ollama_model is not None:
            incoming["model"] = payload.ollama_model

    merged = {
        **current,
        "enabled": bool(incoming.get("enabled", current.get("enabled", False))),
        "base_url": incoming.get("base_url", current.get("base_url")),
        "model": incoming.get("model", current.get("model")),
    }

    if incoming.get("clear_api_key"):
        merged.update(
            {"api_key_encrypted": None, "key_configured": False, "api_key_masked": None}
        )
    else:
        provided_key = incoming.get("api_key")
        if isinstance(provided_key, str) and provided_key.strip():
            merged.update(
                {
                    "api_key_encrypted": encrypt_value(provided_key.strip()),
                    "key_configured": True,
                    "api_key_masked": mask_key(provided_key.strip()),
                }
            )

    # Ensure persistence of existing keys if not modified
    merged.setdefault("api_key_encrypted", current.get("api_key_encrypted"))
    merged.setdefault("key_configured", current.get("key_configured", False))
    merged.setdefault("api_key_masked", current.get("api_key_masked"))
    return merged


def _update_routing_config(
    current: dict[str, Any], incoming: dict[str, Any]
) -> dict[str, Any]:
    """Update and validate primary/fallback provider routing."""
    routing = {
        "primary_provider": incoming.get(
            "primary_provider", current.get("primary_provider", "ollama")
        ),
        "fallback_enabled": bool(
            incoming.get("fallback_enabled", current.get("fallback_enabled", True))
        ),
        "fallback_provider": incoming.get(
            "fallback_provider", current.get("fallback_provider", "openai_compatible")
        ),
    }
    if routing["primary_provider"] not in PROVIDER_KEYS:
        raise HTTPException(status_code=400, detail="Invalid primary provider")
    if routing["fallback_provider"] not in PROVIDER_KEYS:
        raise HTTPException(status_code=400, detail="Invalid fallback provider")
    return routing


# ---------------------------------------------------------------------------
# v2: GitHub Client — all GitHub REST API calls isolated here.
# All methods are synchronous and must be called via asyncio.to_thread().
# ---------------------------------------------------------------------------

# Maps severity levels to short text labels used in GitHub PR comment headers.
# Plain text only — no emoji in logic code.
SEVERITY_LABELS: dict[str, str] = {
    "critical": "[CRITICAL]",
    "high": "[HIGH]",
    "medium": "[MEDIUM]",
    "low": "[LOW]",
}


class GithubClient:
    """Thin wrapper around the GitHub REST API. Uses the requests library only."""

    BASE = "https://api.github.com"

    def __init__(self, token: str):
        self._headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }

    def _request_with_retry(
        self, method: str, url: str, **kwargs
    ) -> tuple[requests.Response | None, dict[str, Any]]:
        """Make HTTP request with retry logic for transient failures (429, 502, 503)."""

        max_retries = 2
        retry_delay = 1

        for attempt in range(max_retries + 1):
            try:
                resp = requests.request(
                    method, url, headers=self._headers, timeout=15, **kwargs
                )

                # Check for retryable status codes
                if resp.status_code in {429, 502, 503} and attempt < max_retries:
                    logger.warning(
                        "GitHub request %s %s returned %s, retrying in %ss...",
                        method,
                        url,
                        resp.status_code,
                        retry_delay,
                    )
                    time.sleep(retry_delay)
                    retry_delay *= 2
                    continue

                return resp, {"status": "success", "code": resp.status_code}

            except requests.exceptions.Timeout:
                return None, {"status": "error", "reason": "timeout"}
            except requests.exceptions.ConnectionError:
                return None, {"status": "error", "reason": "connection_error"}
            except requests.exceptions.RequestException:
                return None, {"status": "error", "reason": "request_exception"}

        # All retries exhausted
        return None, {"status": "error", "reason": "max_retries_exceeded"}

    def fetch_pr_files(
        self, owner: str, repo: str, pr_number: int, head_sha: str
    ) -> list[RepositoryFile]:
        """Return file content for all changed files in a PR that are in SUPPORTED_REPO_EXTENSIONS."""
        logger.info(
            "GithubClient.fetch_pr_files called",
            extra={"owner": owner, "repo": repo, "pr_number": pr_number},
        )

        url = f"{self.BASE}/repos/{owner}/{repo}/pulls/{pr_number}/files"
        resp, status = self._request_with_retry("GET", url)

        if resp is None:
            logger.error("GitHub fetch_pr_files failed: %s", status.get("reason"))
            return []
        if resp.status_code != 200:
            logger.warning(
                "GitHub PR files fetch failed: %s %s", resp.status_code, resp.text[:200]
            )
            return []

        result: list[RepositoryFile] = []
        for file_meta in resp.json():
            filename: str = file_meta.get("filename", "")
            status_meta: str = file_meta.get("status", "")
            if status_meta == "removed":
                continue
            if Path(filename).suffix.lower() not in SUPPORTED_REPO_EXTENSIONS:
                continue
            content = self._fetch_file_content(owner, repo, filename, head_sha)
            if content is not None:
                result.append(RepositoryFile(path=filename, content=content))
        logger.info(
            "GithubClient.fetch_pr_files completed",
            extra={"files_found": len(result)},
        )
        return result

    def _fetch_file_content(
        self, owner: str, repo: str, path: str, ref: str
    ) -> str | None:
        url = f"{self.BASE}/repos/{owner}/{repo}/contents/{path}"
        resp, status = self._request_with_retry("GET", url, params={"ref": ref})

        if resp is None:
            logger.error(
                "GithubClient._fetch_file_content failed: %s",
                status.get("reason"),
                extra={"path": path},
            )
            return None
        if resp.status_code != 200:
            logger.warning(
                "GitHub content fetch failed for %s: %s %s",
                path,
                resp.status_code,
                resp.text[:100],
            )
            return None

        data = resp.json()
        encoded = data.get("content", "")
        try:
            return base64.b64decode(encoded).decode("utf-8", errors="replace")
        except (binascii.Error, UnicodeDecodeError) as exc:
            logger.error(
                "Failed to decode content for %s: %s", path, exc, exc_info=True
            )
            return None

    def post_pr_inline_comment(
        self, owner: str, repo: str, pr_number: int, fix: FixProposal, head_sha: str
    ) -> dict[str, Any]:
        """Post a single inline review comment on the PR for a given fix proposal."""
        logger.info(
            "GithubClient.post_pr_inline_comment called",
            extra={
                "owner": owner,
                "repo": repo,
                "pr_number": pr_number,
                "file_path": fix.file_path,
                "line_number": fix.line_number,
            },
        )

        severity_label = SEVERITY_LABELS.get(fix.severity, f"[{fix.severity.upper()}]")
        body = (
            f"**DR.CODE {severity_label} — {fix.title}**\n\n"
            f"{fix.detail}\n\n"
            f"**Suggested fix:**\n```\n{fix.replacement_line.strip()}\n```"
        )
        url = f"{self.BASE}/repos/{owner}/{repo}/pulls/{pr_number}/comments"
        payload = {
            "body": body,
            "commit_id": head_sha,
            "path": fix.file_path,
            "line": fix.line_number,
            "side": "RIGHT",
        }
        resp, status = self._request_with_retry("POST", url, json=payload)

        if resp is None:
            logger.error(
                "GitHub inline comment failed: %s",
                status.get("reason"),
                extra={"fix": fix.title},
            )
            return {
                "success": False,
                "status": status.get("status"),
                "reason": status.get("reason"),
            }

        if resp.status_code not in {200, 201}:
            logger.warning(
                "GitHub inline comment failed: %s %s",
                resp.status_code,
                resp.text[:100],
            )
            return {
                "success": False,
                "status": resp.status_code,
                "reason": "non_2xx_response",
            }

        logger.info(
            "GithubClient.post_pr_inline_comment completed successfully",
            extra={"fix": fix.title},
        )
        return {"success": True, "status": "created"}

    def post_pr_summary_comment(
        self,
        owner: str,
        repo: str,
        pr_number: int,
        summary: str,
        fix_count: int,
        critical_count: int,
    ) -> dict[str, Any]:
        """Post a summary comment on the PR issue thread (not inline)."""
        logger.info(
            "GithubClient.post_pr_summary_comment called",
            extra={
                "owner": owner,
                "repo": repo,
                "pr_number": pr_number,
                "fix_count": fix_count,
            },
        )

        body = (
            f"## DR.CODE Analysis Complete\n\n"
            f"{summary}\n\n"
            f"| Metric | Value |\n|---|---|\n"
            f"| Total fixes proposed | {fix_count} |\n"
            f"| Critical issues | {critical_count} |\n\n"
            f"*Inline comments have been added to the changed lines above.*"
        )
        url = f"{self.BASE}/repos/{owner}/{repo}/issues/{pr_number}/comments"
        resp, status = self._request_with_retry("POST", url, json={"body": body})

        if resp is None:
            logger.error("GitHub summary comment failed: %s", status.get("reason"))
            return {
                "success": False,
                "status": status.get("status"),
                "reason": status.get("reason"),
            }

        if resp.status_code not in {200, 201}:
            logger.warning(
                "GitHub summary comment failed: %s %s",
                resp.status_code,
                resp.text[:100],
            )
            return {
                "success": False,
                "status": resp.status_code,
                "reason": "non_2xx_response",
            }

        logger.info("GithubClient.post_pr_summary_comment completed successfully")
        return {"success": True, "status": "created"}


def verify_github_signature(
    raw_body: bytes, secret: str, signature_header: str | None
) -> bool:
    """Return True if the X-Hub-Signature-256 header matches the HMAC of the payload."""
    # Graceful bypass: if no secret configured, accept all requests (for dev/testing)
    if not secret or not secret.strip():
        logger.warning("No webhook_secret configured — skipping HMAC verification")
        return True
    if not signature_header or not signature_header.startswith("sha256="):
        logger.warning("Missing or malformed X-Hub-Signature-256 header")
        return False
    expected = hmac.new(secret.encode("utf-8"), raw_body, hashlib.sha256).hexdigest()
    received = signature_header.removeprefix("sha256=")
    return hmac.compare_digest(expected, received)


def _run_github_pr_pipeline_sync(
    pr_payload: GitHubPRWebhookPayload,
    token: str,
    settings_doc: dict[str, Any],
) -> dict[str, Any]:
    """Synchronous core of the GitHub PR pipeline — called via asyncio.to_thread."""
    pull_request = pr_payload.pull_request
    repository = pr_payload.repository
    pr_number: int = pull_request["number"]
    head_sha: str = pull_request["head"]["sha"]
    repo_full_name: str = repository["full_name"]  # e.g. "owner/repo"
    if "/" not in repo_full_name:
        logger.error("GitHub repo full_name has no slash: %s", repo_full_name)
        return {
            "status": "error",
            "reason": "invalid-repo-name",
            "comment_count": 0,
            "fix_count": 0,
        }
    owner, repo = repo_full_name.split("/", 1)

    github = GithubClient(token)
    files = github.fetch_pr_files(owner, repo, pr_number, head_sha)
    if not files:
        return {"status": "no-supported-files", "comment_count": 0, "fix_count": 0}

    thresholds = SeverityThresholds(**settings_doc["severity"])
    fixes = generate_repository_fix_proposals(files, thresholds)
    critical_count = sum(1 for f in fixes if f.severity == "critical")
    summary = build_repository_summary(fixes, len(files))

    comment_count = 0
    for fix in fixes:
        result = github.post_pr_inline_comment(owner, repo, pr_number, fix, head_sha)
        if result.get("success"):
            comment_count += 1

    github.post_pr_summary_comment(
        owner, repo, pr_number, summary, len(fixes), critical_count
    )
    return {
        "status": "analyzed",
        "pr_number": pr_number,
        "head_sha": head_sha,
        "file_count": len(files),
        "fix_count": len(fixes),
        "critical_count": critical_count,
        "comment_count": comment_count,
        "summary": summary,
    }


async def run_github_pr_pipeline(
    pr_payload: GitHubPRWebhookPayload,
    settings_doc: dict[str, Any],
) -> IntegrationEvent:
    """Orchestrate the full PR analysis pipeline and return the logged IntegrationEvent."""
    github_conf = settings_doc.get("github", {})
    token = decrypt_value(github_conf.get("token_encrypted"))

    if not token:
        logger.warning(
            "GitHub PR webhook received but no token configured — skipping analysis."
        )
        event = IntegrationEvent(
            source="github",
            event_type="pull_request",
            status="skipped-no-token",
            details={
                "action": pr_payload.action,
                "repo": pr_payload.repository.get("full_name", ""),
            },
        )
        await db.integration_events.insert_one(event.model_dump())
        return event

    try:
        result = await asyncio.to_thread(
            _run_github_pr_pipeline_sync,
            pr_payload,
            token,
            settings_doc,
        )
    except (requests.RequestException, json.JSONDecodeError, ValueError) as exc:
        logger.exception("GitHub PR pipeline error: %s", exc)
        result = {"status": STATUS_ERROR, "error": str(exc)}

    event = IntegrationEvent(
        source="github",
        event_type="pull_request",
        status=result.get("status", "error"),
        details=result,
    )
    await db.integration_events.insert_one(event.model_dump())

    # Governance audit trail — same pattern as /analyze
    actor = ActorContext(actor_id="github-webhook", role="reviewer")
    await record_governance_event(
        actor=actor,
        action="github-pr-analysis",
        status=result.get("status", "error"),
        details=result,
    )
    return event


# ---------------------------------------------------------------------------
# Upgraded webhook endpoint — backward-compatible.
# Old stub payload (GitWebhookEvent shape) -> logs as before.
# Real GitHub PR payload (has "pull_request" key) -> runs full pipeline.
# ---------------------------------------------------------------------------


@api_router.post(
    "/integrations/git/webhook",
    response_model=IntegrationEvent,
    responses={401: {"description": "Invalid webhook signature"}},
)
async def git_webhook(
    request: Request,
    x_hub_signature_256: Annotated[str | None, Header()] = None,
    x_github_event: Annotated[str | None, Header()] = None,
):
    raw_body = await request.body()
    try:
        body = json.loads(raw_body)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON payload")

    # --- Detect real GitHub PR webhook ---
    if "pull_request" in body and "repository" in body:
        settings_doc = await get_or_create_settings_doc()
        github_conf = settings_doc.get("github", {})

        # HMAC signature check (only if webhook_secret is configured)
        webhook_secret = decrypt_value(github_conf.get("webhook_secret_encrypted"))
        if webhook_secret:
            if not verify_github_signature(
                raw_body, webhook_secret, x_hub_signature_256
            ):
                logger.warning("GitHub webhook signature mismatch — request rejected.")
                raise HTTPException(status_code=401, detail="Invalid webhook signature")
        else:
            logger.warning("No webhook_secret configured — skipping HMAC verification.")

        action = body.get("action", "")
        if action not in {"opened", "synchronize", "reopened", None}:
            # Acknowledge non-analysis events without doing work
            event = IntegrationEvent(
                source="github",
                event_type="pull_request",
                status=f"ignored-action:{action}",
                details={
                    "action": action,
                    "repo": body.get("repository", {}).get("full_name", ""),
                },
            )
            await db.integration_events.insert_one(event.model_dump())
            return event

        pr_payload = GitHubPRWebhookPayload(
            action=action,
            pull_request=body["pull_request"],
            repository=body["repository"],
        )
        return await run_github_pr_pipeline(pr_payload, settings_doc)

    # --- Backward-compat: old stub payload (GitWebhookEvent shape) ---
    event = IntegrationEvent(
        source="git",
        event_type=body.get("event_type", "push"),
        status="received",
        details=body,
    )
    await db.integration_events.insert_one(event.model_dump())
    return event


@api_router.post(
    "/integrations/ci/event",
    response_model=IntegrationEvent,
    responses={400: {"description": "Invalid CI event payload"}},
)
async def ci_event(payload: CIEvent):
    event = IntegrationEvent(
        source="ci",
        event_type="pipeline-status",
        status=payload.status,
        details=payload.model_dump(),
    )
    await db.integration_events.insert_one(event.model_dump())
    return event


@api_router.get("/integrations/events", response_model=list[IntegrationEvent])
async def list_integration_events():
    events = (
        await db.integration_events.find({}, {"_id": 0})
        .sort("created_at", -1)
        .to_list(50)
    )
    return [IntegrationEvent(**event) for event in events]


@api_router.put(
    "/settings/github",
    response_model=GitHubSettingsPublic,
    responses={400: {"description": "Invalid settings payload"}},
)
async def update_github_settings(payload: GitHubSettingsUpdate):
    """Store GitHub PAT and webhook secret (encrypted). Never returns the raw token."""
    settings_doc = await get_or_create_settings_doc()
    github_conf = settings_doc.get("github", {})

    if payload.clear_token:
        github_conf["token_encrypted"] = None
        github_conf["token_masked"] = None
        github_conf["token_configured"] = False
    elif payload.token and payload.token.strip():
        cleaned = payload.token.strip()
        github_conf["token_encrypted"] = encrypt_value(cleaned)
        github_conf["token_masked"] = mask_key(cleaned)
        github_conf["token_configured"] = True

    if payload.webhook_secret is not None:
        stripped = payload.webhook_secret.strip()
        if stripped:
            github_conf["webhook_secret_encrypted"] = encrypt_value(stripped)
            github_conf["webhook_secret_configured"] = True
        else:
            github_conf["webhook_secret_encrypted"] = None
            github_conf["webhook_secret_configured"] = False

    await db.app_settings.update_one(
        {"id": "default"},
        {"$set": {"github": github_conf}},
        upsert=True,
    )
    return GitHubSettingsPublic(
        token_configured=bool(github_conf.get("token_configured")),
        token_masked=github_conf.get("token_masked"),
        webhook_secret_configured=bool(github_conf.get("webhook_secret_configured")),
    )


@api_router.get(
    "/integrations/github/status",
    response_model=GitHubSettingsPublic,
    responses={404: {"description": "GitHub configuration not found"}},
)
async def get_github_status():
    """Return GitHub integration status (token configured, webhook secret configured)."""
    settings_doc = await get_or_create_settings_doc()
    github_conf = settings_doc.get("github", {})
    return GitHubSettingsPublic(
        token_configured=bool(github_conf.get("token_configured")),
        token_masked=github_conf.get("token_masked"),
        webhook_secret_configured=bool(github_conf.get("webhook_secret_configured")),
    )


# Enable the API router (it already has a /api prefix) BEFORE catch-all logic
app.include_router(api_router)

# --- Final Configuration: Unified Serving ---

# Static files should be in backend/static (the production build of frontend)
STATIC_DIR = ROOT_DIR / "static"

if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

    @app.get("/")
    async def serve_root():
        """Explicitly return index.html for the root path."""
        return FileResponse(str(STATIC_DIR / "index.html"))

    @app.get("/{full_path:path}")
    async def serve_frontend(full_path: str):
        # Serve API routes normally via the router
        if full_path.startswith("api/"):
            raise HTTPException(status_code=404)

        file_path = STATIC_DIR / full_path
        if file_path.is_file():
            return FileResponse(str(file_path))
        return FileResponse(str(STATIC_DIR / "index.html"))


@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)
    # Permissive CSP for Hackathon 'Judge-Ready' mode to support Mermaid, React, and local AI calls
    csp = (
        "default-src 'self'; "
        "script-src 'self' 'unsafe-inline' 'unsafe-eval'; "
        "style-src 'self' 'unsafe-inline'; "
        "img-src 'self' data: blob:; "
        "connect-src 'self' *; "
        "font-src 'self' data:;"
    )
    response.headers["Content-Security-Policy"] = csp
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    return response


app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get("CORS_ORIGINS", "*").split(","),
    allow_methods=["*"],
    allow_headers=["*"],
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


@app.on_event("shutdown")
async def shutdown_db_client():
    pass
