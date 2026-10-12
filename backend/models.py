"""Pydantic models for RepoScope API responses."""

from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, Field


class ErrorResponse(BaseModel):
    """Standard error response."""

    error: str
    message: str
    status_code: int
    documentation_url: Optional[str] = None


class RepoBasicInfo(BaseModel):
    """Basic repository metadata."""

    name: str
    full_name: str
    description: Optional[str] = None
    owner: str
    owner_avatar: str
    owner_url: str
    homepage: Optional[str] = None
    html_url: str
    created_at: str
    updated_at: str
    pushed_at: Optional[str] = None
    default_branch: str
    size_kb: int
    stars: int
    forks: int
    watchers: int
    open_issues: int
    subscribers: int
    topics: list[str] = Field(default_factory=list)
    license_name: Optional[str] = None
    license_spdx: Optional[str] = None
    license_url: Optional[str] = None
    archived: bool = False
    disabled: bool = False
    fork: bool = False
    visibility: str = "public"


class LanguageBreakdown(BaseModel):
    """Language usage breakdown."""

    total_bytes: int
    languages: list[dict[str, Any]]  # [{"name": "Python", "bytes": 12345, "percentage": 45.2}]


class Contributor(BaseModel):
    """A repository contributor."""

    login: str
    avatar_url: str
    html_url: str
    contributions: int
    type: str


class CommitActivity(BaseModel):
    """Weekly commit activity for the last year."""

    weekly: list[dict[str, Any]]  # [{"week": "2024-W01", "commits": 12, "timestamp": 1704067200}]
    total_commits: int
    busiest_day: Optional[dict[str, Any]] = None


class RecentCommit(BaseModel):
    """A recent commit."""

    sha: str
    message: str
    author: Optional[str] = None
    author_avatar: Optional[str] = None
    author_url: Optional[str] = None
    date: Optional[str] = None
    html_url: str


class IssuesStats(BaseModel):
    """Issue statistics."""

    open_count: int
    closed_count: int
    total: int
    close_rate: float
    recent_open: list[dict[str, Any]] = Field(default_factory=list)


class PullRequestStats(BaseModel):
    """Pull request statistics."""

    open_count: int
    closed_count: int
    merged_count: int
    total: int
    merge_rate: float
    recent_open: list[dict[str, Any]] = Field(default_factory=list)


class Release(BaseModel):
    """A repository release."""

    tag_name: str
    name: Optional[str] = None
    body: Optional[str] = None
    draft: bool = False
    prerelease: bool = False
    created_at: Optional[str] = None
    published_at: Optional[str] = None
    html_url: str
    author: Optional[str] = None
    author_avatar: Optional[str] = None


class FileEntry(BaseModel):
    """A top-level file/directory entry."""

    name: str
    path: str
    type: str  # "file" | "dir" | "symlink" | "submodule"
    size: int
    html_url: str


class ReadmeInfo(BaseModel):
    """README content."""

    name: str
    path: str
    html_url: str
    download_url: str
    encoding: str
    content: str  # base64-encoded
    decoded: str  # decoded markdown


class AnalysisResult(BaseModel):
    """Full repository analysis result."""

    repo: RepoBasicInfo
    languages: LanguageBreakdown
    contributors: list[Contributor]
    commit_activity: CommitActivity
    recent_commits: list[RecentCommit]
    issues: IssuesStats
    pull_requests: PullRequestStats
    releases: list[Release]
    files: list[FileEntry]
    readme: Optional[ReadmeInfo] = None
    fetched_at: str


class HealthResponse(BaseModel):
    """Health check response."""

    status: str
    version: str
    github_token_configured: bool
    rate_limit: Optional[dict[str, Any]] = None
