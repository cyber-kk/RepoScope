"""Async GitHub REST API v3 client used by RepoScope."""

from __future__ import annotations

import asyncio
import base64
import os
import time
from typing import Any, Optional

import httpx


GITHUB_API_BASE = "https://api.github.com"
GITHUB_API_VERSION = "2022-11-28"
DEFAULT_TIMEOUT = 20.0
MAX_CONCURRENT = 8


class GitHubAPIError(Exception):
    """Raised when the GitHub API returns an error."""

    def __init__(self, status_code: int, message: str, documentation_url: Optional[str] = None):
        super().__init__(message)
        self.status_code = status_code
        self.message = message
        self.documentation_url = documentation_url

    def __str__(self) -> str:
        return f"GitHub API {self.status_code}: {self.message}"


class RateLimitError(GitHubAPIError):
    """Raised when the GitHub rate limit is exceeded."""

    def __init__(self, reset_at: Optional[int] = None):
        super().__init__(403, "GitHub API rate limit exceeded")
        self.reset_at = reset_at


class GitHubClient:
    """Thin async wrapper around the GitHub REST API."""

    def __init__(
        self,
        token: Optional[str] = None,
        timeout: float = DEFAULT_TIMEOUT,
        max_concurrency: int = MAX_CONCURRENT,
    ) -> None:
        self.token = token or os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
        headers = {
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": GITHUB_API_VERSION,
            "User-Agent": "RepoScope/1.0 (+https://github.com/cyber-kk/RepoScope)",
        }
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"

        self._client = httpx.AsyncClient(
            base_url=GITHUB_API_BASE,
            headers=headers,
            timeout=timeout,
            follow_redirects=True,
        )
        self._semaphore = asyncio.Semaphore(max_concurrency)
        self._rate_limit_remaining: Optional[int] = None
        self._rate_limit_reset: Optional[int] = None

    async def __aenter__(self) -> "GitHubClient":
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        await self.close()

    async def close(self) -> None:
        await self._client.aclose()

    async def _request(self, method: str, url: str, **kwargs: Any) -> httpx.Response:
        async with self._semaphore:
            response = await self._client.request(method, url, **kwargs)

        # Track rate-limit info
        remaining = response.headers.get("X-RateLimit-Remaining")
        reset = response.headers.get("X-RateLimit-Reset")
        if remaining is not None:
            try:
                self._rate_limit_remaining = int(remaining)
            except ValueError:
                pass
        if reset is not None:
            try:
                self._rate_limit_reset = int(reset)
            except ValueError:
                pass

        if response.status_code == 403:
            remaining_header = response.headers.get("X-RateLimit-Remaining", "")
            if remaining_header == "0":
                reset_at = self._rate_limit_reset
                raise RateLimitError(reset_at=reset_at)
            data = self._safe_json(response)
            raise GitHubAPIError(
                403,
                data.get("message", "Forbidden"),
                data.get("documentation_url"),
            )

        if response.status_code == 404:
            data = self._safe_json(response)
            raise GitHubAPIError(
                404,
                data.get("message", "Not Found"),
                data.get("documentation_url"),
            )

        if response.status_code >= 400:
            data = self._safe_json(response)
            raise GitHubAPIError(
                response.status_code,
                data.get("message", f"HTTP {response.status_code}"),
                data.get("documentation_url"),
            )

        return response

    @staticmethod
    def _safe_json(response: httpx.Response) -> dict[str, Any]:
        try:
            return response.json()
        except Exception:
            return {}

    async def get_json(self, path: str, params: Optional[dict[str, Any]] = None) -> Any:
        response = await self._request("GET", path, params=params)
        if not response.content:
            return None
        return response.json()

    async def get_repo(self, owner: str, repo: str) -> dict[str, Any]:
        return await self.get_json(f"/repos/{owner}/{repo}")

    async def get_languages(self, owner: str, repo: str) -> dict[str, Any]:
        return await self.get_json(f"/repos/{owner}/{repo}/languages")

    async def get_contributors(self, owner: str, repo: str, limit: int = 25) -> list[dict[str, Any]]:
        params = {"per_page": min(max(limit, 1), 100), "anon": "false"}
        return await self.get_json(f"/repos/{owner}/{repo}/contributors", params=params)

    async def get_commit_activity(self, owner: str, repo: str) -> list[dict[str, Any]]:
        return await self.get_json(f"/repos/{owner}/{repo}/stats/commit_activity")

    async def get_recent_commits(self, owner: str, repo: str, limit: int = 15) -> list[dict[str, Any]]:
        params = {"per_page": min(max(limit, 1), 100)}
        return await self.get_json(f"/repos/{owner}/{repo}/commits", params=params)

    async def get_issues(self, owner: str, repo: str, state: str, limit: int = 10) -> list[dict[str, Any]]:
        params = {"state": state, "per_page": min(max(limit, 1), 100)}
        return await self.get_json(f"/repos/{owner}/{repo}/issues", params=params)

    async def get_pulls(self, owner: str, repo: str, state: str, limit: int = 10) -> list[dict[str, Any]]:
        params = {"state": state, "per_page": min(max(limit, 1), 100)}
        return await self.get_json(f"/repos/{owner}/{repo}/pulls", params=params)

    async def get_releases(self, owner: str, repo: str, limit: int = 10) -> list[dict[str, Any]]:
        params = {"per_page": min(max(limit, 1), 100)}
        return await self.get_json(f"/repos/{owner}/{repo}/releases", params=params)

    async def get_contents(self, owner: str, repo: str, path: str = "", ref: Optional[str] = None) -> Any:
        params = {"ref": ref} if ref else None
        path_part = f"/repos/{owner}/{repo}/contents/{path}" if path else f"/repos/{owner}/{repo}/contents"
        return await self.get_json(path_part, params=params)

    async def get_readme(self, owner: str, repo: str) -> dict[str, Any]:
        return await self.get_json(f"/repos/{owner}/{repo}/readme")

    async def get_rate_limit(self) -> dict[str, Any]:
        return await self.get_json("/rate_limit")

    def rate_limit_status(self) -> dict[str, Any]:
        return {
            "remaining": self._rate_limit_remaining,
            "reset_at": self._rate_limit_reset,
            "token_configured": bool(self.token),
        }


def decode_base64_content(content: str, encoding: str = "base64") -> str:
    """Decode GitHub-encoded file content (handles newlines)."""
    if encoding != "base64":
        return content
    cleaned = "".join(content.split())
    try:
        return base64.b64decode(cleaned).decode("utf-8", errors="replace")
    except Exception:
        return ""
