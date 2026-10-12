"""RepoScope FastAPI application.

Serves both the JSON analysis API and the static frontend.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from analyzer import RepoAnalyzer
from github_client import GitHubAPIError, GitHubClient, RateLimitError
from models import AnalysisResult, ErrorResponse, HealthResponse


APP_VERSION = "1.0.0"

BASE_DIR = Path(__file__).resolve().parent
FRONTEND_DIR = BASE_DIR.parent / "frontend"

app = FastAPI(
    title="RepoScope",
    description="Analyze any public GitHub repository: stars, languages, contributors, commits, issues, PRs, releases, and more.",
    version=APP_VERSION,
    docs_url="/api/docs",
    openapi_url="/api/openapi.json",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET", "OPTIONS"],
    allow_headers=["*"],
)


def _client_from_query(token: Optional[str]) -> GitHubClient:
    """Build a GitHubClient, optionally overriding the token via query param."""
    effective_token = token or os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    return GitHubClient(token=effective_token)


def _github_error_to_response(exc: GitHubAPIError) -> JSONResponse:
    status = exc.status_code
    body = ErrorResponse(
        error="github_api_error",
        message=exc.message,
        status_code=status,
        documentation_url=exc.documentation_url,
    )
    return JSONResponse(status_code=status, content=body.model_dump())


def _split_owner_repo(spec: str) -> tuple[str, str]:
    """Parse 'owner/repo', 'https://github.com/owner/repo', or 'github.com/owner/repo'."""
    spec = spec.strip()
    if not spec:
        raise HTTPException(status_code=400, detail="Empty repository identifier")
    # Strip protocol + host
    for prefix in ("https://", "http://", "www."):
        if spec.startswith(prefix):
            spec = spec[len(prefix):]
            break
    if "@" in spec:  # SSH URL: git@github.com:owner/repo.git
        spec = spec.split(":", 1)[1] if ":" in spec else spec
    if spec.startswith("github.com/"):
        spec = spec[len("github.com/"):]
    # Strip trailing path parts (e.g., /tree/main/foo)
    parts = [p for p in spec.split("/") if p]
    if len(parts) < 2:
        raise HTTPException(
            status_code=400,
            detail="Could not parse 'owner/repo' from input. Use 'owner/repo' or a full GitHub URL.",
        )
    owner, repo = parts[0], parts[1]
    # Strip .git suffix
    if repo.endswith(".git"):
        repo = repo[:-4]
    return owner, repo


@app.get("/api/health", response_model=HealthResponse, tags=["meta"])
async def health() -> HealthResponse:
    """Check service status and the GitHub rate-limit allowance."""
    async with GitHubClient() as client:
        try:
            rl = await client.get_rate_limit()
            rate_info = _safe_get_nested(rl, "rate")
        except Exception:
            rate_info = None
        return HealthResponse(
            status="ok",
            version=APP_VERSION,
            github_token_configured=bool(client.token),
            rate_limit=rate_info,
        )


@app.get("/api/analyze", response_model=AnalysisResult, tags=["analysis"])
async def analyze(
    repo: str = Query(..., description="Repository as 'owner/repo' or full GitHub URL."),
    token: Optional[str] = Query(None, description="Optional GitHub personal access token (overrides env)."),
) -> AnalysisResult:
    """Fetch aggregated analytics for a GitHub repository."""
    owner, repo_name = _split_owner_repo(repo)
    async with _client_from_query(token) as client:
        analyzer = RepoAnalyzer(client)
        try:
            return await analyzer.analyze(owner, repo_name)
        except RateLimitError as exc:
            body = ErrorResponse(
                error="rate_limited",
                message="GitHub API rate limit exceeded. Set a GITHUB_TOKEN to raise the limit to 5,000 req/hour.",
                status_code=429,
                documentation_url="https://docs.github.com/rest/overview/resources-in-the-rest-api#rate-limiting",
            )
            return JSONResponse(status_code=429, content=body.model_dump())
        except GitHubAPIError as exc:
            return _github_error_to_response(exc)


@app.exception_handler(HTTPException)
async def _http_exception_handler(_request, exc: HTTPException) -> JSONResponse:
    body = ErrorResponse(
        error="http_error",
        message=str(exc.detail),
        status_code=exc.status_code,
    )
    return JSONResponse(status_code=exc.status_code, content=body.model_dump())


def _safe_get_nested(data, *keys, default=None):
    cur = data
    for k in keys:
        if not isinstance(cur, dict):
            return default
        cur = cur.get(k)
        if cur is None:
            return default
    return cur


# Serve the frontend (must be registered AFTER API routes).
if FRONTEND_DIR.exists():
    app.mount("/", StaticFiles(directory=str(FRONTEND_DIR), html=True), name="frontend")


if __name__ == "__main__":
    import uvicorn

    host = os.environ.get("REPOSCOPE_HOST", "0.0.0.0")
    port = int(os.environ.get("REPOSCOPE_PORT", "8000"))
    uvicorn.run("main:app", host=host, port=port, reload=False)
