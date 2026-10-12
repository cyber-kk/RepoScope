"""High-level analyzer that orchestrates multiple GitHub API calls."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any, Optional

from github_client import GitHubAPIError, GitHubClient, RateLimitError, decode_base64_content
from models import (
    AnalysisResult,
    CommitActivity,
    Contributor,
    FileEntry,
    IssuesStats,
    LanguageBreakdown,
    PullRequestStats,
    ReadmeInfo,
    RecentCommit,
    Release,
    RepoBasicInfo,
)


def _safe_get(data: dict[str, Any], *keys: str, default: Any = None) -> Any:
    cur: Any = data
    for k in keys:
        if not isinstance(cur, dict):
            return default
        cur = cur.get(k)
        if cur is None:
            return default
    return cur


def _parse_repo(raw: dict[str, Any]) -> RepoBasicInfo:
    license_obj = raw.get("license") or {}
    owner_obj = raw.get("owner") or {}
    return RepoBasicInfo(
        name=raw.get("name", ""),
        full_name=raw.get("full_name", ""),
        description=raw.get("description"),
        owner=owner_obj.get("login", ""),
        owner_avatar=owner_obj.get("avatar_url", ""),
        owner_url=owner_obj.get("html_url", ""),
        homepage=raw.get("homepage"),
        html_url=raw.get("html_url", ""),
        created_at=raw.get("created_at", ""),
        updated_at=raw.get("updated_at", ""),
        pushed_at=raw.get("pushed_at"),
        default_branch=raw.get("default_branch", "main"),
        size_kb=raw.get("size", 0),
        stars=raw.get("stargazers_count", 0),
        forks=raw.get("forks_count", 0),
        watchers=raw.get("watchers_count", 0),
        open_issues=raw.get("open_issues_count", 0),
        subscribers=raw.get("subscribers_count", 0),
        topics=raw.get("topics", []) or [],
        license_name=license_obj.get("name"),
        license_spdx=license_obj.get("spdx_id"),
        license_url=license_obj.get("url"),
        archived=bool(raw.get("archived")),
        disabled=bool(raw.get("disabled")),
        fork=bool(raw.get("fork")),
        visibility=raw.get("visibility", "public"),
    )


def _parse_languages(raw: dict[str, Any]) -> LanguageBreakdown:
    total = sum(raw.values()) or 1
    languages = [
        {
            "name": name,
            "bytes": bytes_,
            "percentage": round(bytes_ / total * 100, 2),
        }
        for name, bytes_ in sorted(raw.items(), key=lambda kv: kv[1], reverse=True)
    ]
    return LanguageBreakdown(total_bytes=sum(raw.values()), languages=languages)


def _parse_contributors(raw: list[dict[str, Any]]) -> list[Contributor]:
    out: list[Contributor] = []
    for c in raw:
        out.append(
            Contributor(
                login=c.get("login", "unknown"),
                avatar_url=c.get("avatar_url", ""),
                html_url=c.get("html_url", ""),
                contributions=c.get("contributions", 0),
                type=c.get("type", "User"),
            )
        )
    return out


def _parse_commit_activity(raw: list[dict[str, Any]]) -> CommitActivity:
    weekly: list[dict[str, Any]] = []
    total_commits = 0
    busiest_day: Optional[dict[str, Any]] = None

    for week in raw:
        ts = week.get("week")
        days = week.get("days", [])
        week_total = week.get("total", 0) or sum(days)
        if week_total <= 0:
            continue
        total_commits += week_total
        iso_week = ""
        try:
            if ts:
                iso_week = datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-W%V")
        except Exception:
            iso_week = ""

        day_names = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"]
        peak_idx = max(range(len(days)), key=lambda i: days[i]) if days else -1
        weekly.append(
            {
                "week": iso_week,
                "timestamp": ts,
                "commits": week_total,
                "days": [{"name": day_names[i], "commits": c} for i, c in enumerate(days)],
            }
        )

        if peak_idx >= 0 and (busiest_day is None or days[peak_idx] > busiest_day.get("commits", 0)):
            busiest_day = {"name": day_names[peak_idx], "commits": days[peak_idx], "week": iso_week}

    return CommitActivity(weekly=weekly, total_commits=total_commits, busiest_day=busiest_day)


def _parse_recent_commits(raw: list[dict[str, Any]]) -> list[RecentCommit]:
    out: list[RecentCommit] = []
    for c in raw:
        commit_obj = c.get("commit") or {}
        author_obj = commit_obj.get("author") or {}
        message = commit_obj.get("message", "")
        first_line = message.split("\n\n", 1)[0] if message else ""
        out.append(
            RecentCommit(
                sha=c.get("sha", ""),
                message=first_line,
                author=author_obj.get("name") or _safe_get(c, "author", "login", default=""),
                author_avatar=_safe_get(c, "author", "avatar_url", default=""),
                author_url=_safe_get(c, "author", "html_url", default=""),
                date=author_obj.get("date"),
                html_url=c.get("html_url", ""),
            )
        )
    return out


def _parse_issue(item: dict[str, Any]) -> dict[str, Any]:
    user = item.get("user") or {}
    labels = [l.get("name") for l in (item.get("labels") or []) if l.get("name")]
    return {
        "number": item.get("number"),
        "title": item.get("title", ""),
        "state": item.get("state", ""),
        "html_url": item.get("html_url", ""),
        "created_at": item.get("created_at"),
        "updated_at": item.get("updated_at"),
        "author": user.get("login", ""),
        "author_avatar": user.get("avatar_url", ""),
        "comments": item.get("comments", 0),
        "labels": labels,
        "is_pr": "pull_request" in item,
    }


def _parse_issues(open_raw: list[dict[str, Any]], closed_raw: list[dict[str, Any]], open_count: int) -> IssuesStats:
    closed_count = len(closed_raw)
    total = open_count + closed_count
    close_rate = round(closed_count / total * 100, 2) if total > 0 else 0.0
    recent_open = [_parse_issue(i) for i in open_raw[:5] if not ("pull_request" in i)]
    return IssuesStats(
        open_count=open_count,
        closed_count=closed_count,
        total=total,
        close_rate=close_rate,
        recent_open=recent_open,
    )


def _parse_pulls(
    open_raw: list[dict[str, Any]], closed_raw: list[dict[str, Any]], open_count: int
) -> PullRequestStats:
    merged_count = sum(1 for p in closed_raw if p.get("merged_at"))
    closed_count = len(closed_raw)
    total = open_count + closed_count
    merge_rate = round(merged_count / total * 100, 2) if total > 0 else 0.0
    recent_open = [_parse_issue(p) for p in open_raw[:5]]
    return PullRequestStats(
        open_count=open_count,
        closed_count=closed_count,
        merged_count=merged_count,
        total=total,
        merge_rate=merge_rate,
        recent_open=recent_open,
    )


def _parse_releases(raw: list[dict[str, Any]]) -> list[Release]:
    out: list[Release] = []
    for r in raw:
        author = r.get("author") or {}
        out.append(
            Release(
                tag_name=r.get("tag_name", ""),
                name=r.get("name"),
                body=r.get("body"),
                draft=bool(r.get("draft")),
                prerelease=bool(r.get("prerelease")),
                created_at=r.get("created_at"),
                published_at=r.get("published_at"),
                html_url=r.get("html_url", ""),
                author=author.get("login"),
                author_avatar=author.get("avatar_url"),
            )
        )
    return out


def _parse_files(raw: Any) -> list[FileEntry]:
    if not isinstance(raw, list):
        return []
    out: list[FileEntry] = []
    for f in raw:
        out.append(
            FileEntry(
                name=f.get("name", ""),
                path=f.get("path", ""),
                type=f.get("type", "file"),
                size=f.get("size", 0),
                html_url=f.get("html_url", ""),
            )
        )
    return sorted(out, key=lambda x: (x.type != "dir", x.name.lower()))


def _parse_readme(raw: dict[str, Any]) -> Optional[ReadmeInfo]:
    if not raw:
        return None
    content = raw.get("content", "")
    encoding = raw.get("encoding", "base64")
    decoded = decode_base64_content(content, encoding)
    return ReadmeInfo(
        name=raw.get("name", "README"),
        path=raw.get("path", ""),
        html_url=raw.get("html_url", ""),
        download_url=raw.get("download_url", ""),
        encoding=encoding,
        content=content,
        decoded=decoded,
    )


class RepoAnalyzer:
    """Fetches and aggregates GitHub repository metrics."""

    def __init__(self, client: GitHubClient) -> None:
        self.client = client

    async def analyze(self, owner: str, repo: str) -> AnalysisResult:
        owner = owner.strip()
        repo = repo.strip()
        if not owner or not repo:
            raise GitHubAPIError(400, "owner and repo are required")

        # Fetch repo metadata first (we need it to know open_issues etc.)
        repo_raw = await self.client.get_repo(owner, repo)

        # Kick off all secondary calls concurrently.
        languages_task = self.client.get_languages(owner, repo)
        contributors_task = self.client.get_contributors(owner, repo, limit=25)
        commit_activity_task = self.client.get_commit_activity(owner, repo)
        recent_commits_task = self.client.get_recent_commits(owner, repo, limit=15)
        open_issues_task = self.client.get_issues(owner, repo, "open", limit=100)
        closed_issues_task = self.client.get_issues(owner, repo, "closed", limit=100)
        open_pulls_task = self.client.get_pulls(owner, repo, "open", limit=100)
        closed_pulls_task = self.client.get_pulls(owner, repo, "closed", limit=100)
        releases_task = self.client.get_releases(owner, repo, limit=10)
        contents_task = self.client.get_contents(owner, repo)
        readme_task = self.client.get_readme(owner, repo)

        results = await asyncio.gather(
            languages_task,
            contributors_task,
            commit_activity_task,
            recent_commits_task,
            open_issues_task,
            closed_issues_task,
            open_pulls_task,
            closed_pulls_task,
            releases_task,
            contents_task,
            readme_task,
            return_exceptions=True,
        )

        (
            languages_raw,
            contributors_raw,
            commit_activity_raw,
            recent_commits_raw,
            open_issues_raw,
            closed_issues_raw,
            open_pulls_raw,
            closed_pulls_raw,
            releases_raw,
            contents_raw,
            readme_raw,
        ) = results

        open_issues_count = repo_raw.get("open_issues_count", 0)

        # Some endpoints can return 409 (empty repo) or 204 (no data); tolerate.
        # Also soft-fail on rate-limit / network errors so partial data is returned.
        def _or_default(val: Any, default: Any) -> Any:
            if isinstance(val, RateLimitError):
                return default
            if isinstance(val, GitHubAPIError):
                if val.status_code in (403, 404, 409, 422, 204):
                    return default
                raise val
            if isinstance(val, Exception):
                # Network blip / timeout - degrade gracefully.
                return default
            return val if val is not None else default

        languages_raw = _or_default(languages_raw, {})
        contributors_raw = _or_default(contributors_raw, [])
        commit_activity_raw = _or_default(commit_activity_raw, [])
        recent_commits_raw = _or_default(recent_commits_raw, [])
        open_issues_raw = _or_default(open_issues_raw, [])
        closed_issues_raw = _or_default(closed_issues_raw, [])
        open_pulls_raw = _or_default(open_pulls_raw, [])
        closed_pulls_raw = _or_default(closed_pulls_raw, [])
        releases_raw = _or_default(releases_raw, [])
        contents_raw = _or_default(contents_raw, [])
        readme_raw = _or_default(readme_raw, {})

        return AnalysisResult(
            repo=_parse_repo(repo_raw),
            languages=_parse_languages(languages_raw or {}),
            contributors=_parse_contributors(contributors_raw or []),
            commit_activity=_parse_commit_activity(commit_activity_raw or []),
            recent_commits=_parse_recent_commits(recent_commits_raw or []),
            issues=_parse_issues(open_issues_raw or [], closed_issues_raw or [], open_issues_count),
            pull_requests=_parse_pulls(open_pulls_raw or [], closed_pulls_raw or [], len(open_pulls_raw or [])),
            releases=_parse_releases(releases_raw or []),
            files=_parse_files(contents_raw),
            readme=_parse_readme(readme_raw or {}),
            fetched_at=datetime.now(timezone.utc).isoformat(),
        )
