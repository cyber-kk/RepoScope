/* RepoScope — main application logic. */

const App = (() => {
  const els = {
    form: document.getElementById("search-form"),
    input: document.getElementById("search-input"),
    button: document.getElementById("search-button"),
    stateSection: document.getElementById("state-section"),
    loadingCard: document.getElementById("loading-card"),
    errorCard: document.getElementById("error-card"),
    errorMessage: document.getElementById("error-message"),
    errorDetail: document.getElementById("error-detail"),
    results: document.getElementById("results"),
    chips: document.querySelectorAll(".chip"),
    tabs: document.querySelectorAll(".tab"),
  };

  let currentResult = null;

  // ---------- State helpers ----------

  function showLoading() {
    els.results.hidden = true;
    els.errorCard.hidden = true;
    els.loadingCard.hidden = false;
    els.stateSection.hidden = false;
    els.button.disabled = true;
    els.button.textContent = "Analyzing…";
  }

  function showError(message, detail = "") {
    els.results.hidden = true;
    els.loadingCard.hidden = true;
    els.errorCard.hidden = false;
    els.stateSection.hidden = false;
    els.errorMessage.textContent = message || "Something went wrong.";
    els.errorDetail.textContent = detail;
    els.button.disabled = false;
    els.button.textContent = "Analyze";
  }

  function showResults() {
    els.loadingCard.hidden = true;
    els.errorCard.hidden = true;
    els.stateSection.hidden = true;
    els.results.hidden = false;
    els.button.disabled = false;
    els.button.textContent = "Analyze";
  }

  // ---------- API ----------

  async function fetchAnalysis(repoSpec) {
    const url = `/api/analyze?repo=${encodeURIComponent(repoSpec)}`;
    const resp = await fetch(url, { headers: { Accept: "application/json" } });
    let body;
    try {
      body = await resp.json();
    } catch (e) {
      throw new Error("Server returned an invalid response.");
    }
    if (!resp.ok) {
      const err = new Error(body && body.message ? body.message : `HTTP ${resp.status}`);
      err.status = resp.status;
      err.body = body;
      throw err;
    }
    return body;
  }

  // ---------- Render ----------

  function formatNumber(n) {
    if (n == null) return "—";
    if (n >= 1_000_000) return (n / 1_000_000).toFixed(2) + "M";
    if (n >= 1_000) return (n / 1_000).toFixed(1) + "k";
    return String(n);
  }

  function formatSize(kb) {
    if (kb == null) return "—";
    if (kb >= 1_024 * 1024) return (kb / (1024 * 1024)).toFixed(2) + " GB";
    if (kb >= 1024) return (kb / 1024).toFixed(1) + " MB";
    return kb + " KB";
  }

  function formatDate(iso) {
    if (!iso) return "—";
    const d = new Date(iso);
    if (isNaN(d.getTime())) return iso;
    return d.toLocaleDateString(undefined, { year: "numeric", month: "short", day: "numeric" });
  }

  function escapeHtml(s) {
    return String(s ?? "").replace(/[&<>"']/g, (c) => ({
      "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
    })[c]);
  }

  function render(result) {
    currentResult = result;
    renderRepoHeader(result.repo);
    renderMetrics(result.repo, result.pull_requests);
    renderOverview(result);
    renderContributors(result.contributors);
    renderCommits(result.recent_commits);
    renderIssuesAndPRs(result.issues, result.pull_requests);
    renderReleases(result.releases);
    renderReadme(result.readme);
    renderFiles(result.files);

    RepoScopeCharts.renderCommits(result.commit_activity.weekly);
    RepoScopeCharts.renderLanguages(result.languages.languages);
    RepoScopeCharts.renderContributors(result.contributors);

    showResults();
  }

  function renderRepoHeader(repo) {
    document.getElementById("repo-avatar").src = repo.owner_avatar || "";
    document.getElementById("repo-avatar").alt = repo.owner + " avatar";

    const titleEl = document.getElementById("repo-title");
    titleEl.innerHTML = `<a href="${escapeHtml(repo.html_url)}" target="_blank" rel="noreferrer">${escapeHtml(repo.full_name)}</a>`;

    const descEl = document.getElementById("repo-description");
    descEl.textContent = repo.description || "No description provided.";

    const topicsEl = document.getElementById("repo-topics");
    topicsEl.innerHTML = (repo.topics || [])
      .map((t) => `<span class="topic">${escapeHtml(t)}</span>`)
      .join("");

    const link = document.getElementById("repo-link");
    link.href = repo.html_url;

    const licEl = document.getElementById("repo-license");
    if (repo.license_spdx && repo.license_spdx !== "NOASSERTION") {
      licEl.textContent = `⚖ ${repo.license_spdx}`;
    } else if (repo.license_name) {
      licEl.textContent = `⚖ ${repo.license_name}`;
    } else {
      licEl.textContent = "⚖ No license";
    }
  }

  function renderMetrics(repo, prs) {
    set("m-stars", formatNumber(repo.stars));
    set("m-forks", formatNumber(repo.forks));
    set("m-watchers", formatNumber(repo.watchers));
    set("m-issues", formatNumber(repo.open_issues - prs.open_count));
    set("m-prs", formatNumber(prs.open_count));
    set("m-size", formatSize(repo.size_kb));
  }

  function set(id, value) {
    const el = document.getElementById(id);
    if (el) el.textContent = value;
  }

  function dl(entries) {
    return entries
      .map(([k, v]) => `<dt>${escapeHtml(k)}</dt><dd>${escapeHtml(String(v))}</dd>`)
      .join("");
  }

  function renderOverview(result) {
    const r = result.repo;
    document.getElementById("repo-meta-list").innerHTML = dl([
      ["Full name", r.full_name],
      ["Owner", r.owner],
      ["Default branch", r.default_branch],
      ["Created", formatDate(r.created_at)],
      ["Updated", formatDate(r.updated_at)],
      ["Last push", formatDate(r.pushed_at)],
      ["Visibility", r.visibility],
      ["Archived", r.archived ? "yes" : "no"],
    ]);

    const ca = result.commit_activity;
    const busiest = ca.busiest_day
      ? `${ca.busiest_day.name} (${ca.busiest_day.commits} commits in ${ca.busiest_day.week})`
      : "—";
    document.getElementById("activity-meta-list").innerHTML = dl([
      ["Total commits (52w)", formatNumber(ca.total_commits)],
      ["Busiest day", busiest],
      ["Contributors", formatNumber(result.contributors.length)],
      ["Releases", formatNumber(result.releases.length)],
      ["Files (root)", formatNumber(result.files.length)],
      ["Fetched", formatDate(result.fetched_at)],
    ]);

    document.getElementById("engagement-meta-list").innerHTML = dl([
      ["Subscribers", formatNumber(r.subscribers)],
      ["Stars", formatNumber(r.stars)],
      ["Forks", formatNumber(r.forks)],
      ["Open issues", formatNumber(result.issues.open_count)],
      ["Closed issues", formatNumber(result.issues.closed_count)],
      ["Close rate", result.issues.close_rate + "%"],
      ["Merged PRs", formatNumber(result.pull_requests.merged_count)],
      ["Merge rate", result.pull_requests.merge_rate + "%"],
    ]);
  }

  function renderContributors(contributors) {
    const el = document.getElementById("contributors-list");
    if (!contributors.length) {
      el.innerHTML = `<p class="muted">No contributor data available.</p>`;
      return;
    }
    el.innerHTML = contributors
      .map(
        (c) => `
      <a class="contributor-card" href="${escapeHtml(c.html_url)}" target="_blank" rel="noreferrer">
        <img src="${escapeHtml(c.avatar_url)}" alt="${escapeHtml(c.login)}" loading="lazy" />
        <div>
          <div class="contributor-name">${escapeHtml(c.login)}</div>
          <div class="contributor-commits">${formatNumber(c.contributions)} commits · ${escapeHtml(c.type)}</div>
        </div>
      </a>`
      )
      .join("");
  }

  function renderCommits(commits) {
    const el = document.getElementById("commits-list");
    if (!commits.length) {
      el.innerHTML = `<p class="muted">No commits returned (the repo may be empty).</p>`;
      return;
    }
    el.innerHTML = commits
      .map(
        (c) => `
      <div class="commit-row">
        ${c.author_avatar ? `<img src="${escapeHtml(c.author_avatar)}" alt="${escapeHtml(c.author || "author")}" loading="lazy"/>` : ""}
        <div style="flex:1; min-width:0">
          <span class="commit-sha">${escapeHtml(c.sha.slice(0, 7))}</span>
          <p class="commit-message">${escapeHtml(c.message)}</p>
          <div class="commit-meta">${escapeHtml(c.author || "unknown")} · ${formatDate(c.date)} · <a href="${escapeHtml(c.html_url)}" target="_blank" rel="noreferrer">view ↗</a></div>
        </div>
      </div>`
      )
      .join("");
  }

  function renderIssuesAndPRs(issues, prs) {
    document.getElementById("issues-stats-list").innerHTML = dl([
      ["Open", formatNumber(issues.open_count)],
      ["Closed (recent)", formatNumber(issues.closed_count)],
      ["Total (recent)", formatNumber(issues.total)],
      ["Close rate", issues.close_rate + "%"],
    ]);
    document.getElementById("prs-stats-list").innerHTML = dl([
      ["Open", formatNumber(prs.open_count)],
      ["Closed (recent)", formatNumber(prs.closed_count)],
      ["Merged (recent)", formatNumber(prs.merged_count)],
      ["Merge rate", prs.merge_rate + "%"],
    ]);

    document.getElementById("recent-issues-list").innerHTML = (issues.recent_open || [])
      .map(
        (i) => `
        <li>
          ${i.author_avatar ? `<img src="${escapeHtml(i.author_avatar)}" alt="${escapeHtml(i.author)}" loading="lazy"/>` : ""}
          <div>
            <a href="${escapeHtml(i.html_url)}" target="_blank" rel="noreferrer">#${i.number} ${escapeHtml(i.title)}</a>
            <div class="item-meta">${escapeHtml(i.author || "unknown")} · ${formatDate(i.created_at)} · ${i.comments} comments</div>
          </div>
        </li>`
      )
      .join("") || `<li class="muted">No recent open issues.</li>`;

    document.getElementById("recent-prs-list").innerHTML = (prs.recent_open || [])
      .map(
        (i) => `
        <li>
          ${i.author_avatar ? `<img src="${escapeHtml(i.author_avatar)}" alt="${escapeHtml(i.author)}" loading="lazy"/>` : ""}
          <div>
            <a href="${escapeHtml(i.html_url)}" target="_blank" rel="noreferrer">#${i.number} ${escapeHtml(i.title)}</a>
            <div class="item-meta">${escapeHtml(i.author || "unknown")} · ${formatDate(i.created_at)} · ${i.comments} comments</div>
          </div>
        </li>`
      )
      .join("") || `<li class="muted">No recent open PRs.</li>`;
  }

  function renderReleases(releases) {
    const el = document.getElementById("releases-list");
    if (!releases.length) {
      el.innerHTML = `<p class="muted">No releases published.</p>`;
      return;
    }
    el.innerHTML = releases
      .map(
        (r) => `
      <div class="release-card ${r.prerelease ? "prerelease" : ""}">
        <h5>
          ${escapeHtml(r.name || r.tag_name)}
          <span class="release-tag">${escapeHtml(r.tag_name)}</span>
          ${r.prerelease ? '<span class="meta-pill" style="margin-left:6px">pre-release</span>' : ""}
        </h5>
        <div class="commit-meta">${escapeHtml(r.author || "unknown")} · published ${formatDate(r.published_at)} · <a href="${escapeHtml(r.html_url)}" target="_blank" rel="noreferrer">view ↗</a></div>
        ${r.body ? `<pre class="release-body">${escapeHtml(truncate(r.body, 1200))}</pre>` : ""}
      </div>`
      )
      .join("");
  }

  function truncate(s, n) {
    if (!s) return "";
    if (s.length <= n) return s;
    return s.slice(0, n) + "…";
  }

  function renderReadme(readme) {
    const el = document.getElementById("readme-content");
    if (!readme || !readme.decoded) {
      el.textContent = "No README available for this repository.";
      return;
    }
    try {
      const html = marked.parse(readme.decoded);
      el.innerHTML = DOMPurify.sanitize(html, {
        ADD_ATTR: ["target", "rel"],
      });
      // Make links open in a new tab
      el.querySelectorAll("a[href]").forEach((a) => {
        a.setAttribute("target", "_blank");
        a.setAttribute("rel", "noreferrer");
      });
    } catch (e) {
      el.textContent = readme.decoded;
    }
  }

  function renderFiles(files) {
    const el = document.getElementById("files-list");
    if (!files.length) {
      el.innerHTML = `<li class="muted">Repository is empty.</li>`;
      return;
    }
    el.innerHTML = files
      .map(
        (f) => `
        <li>
          <svg class="file-icon ${f.type === "dir" ? "file-icon--dir" : "file-icon--file"}" viewBox="0 0 24 24" width="18" height="18">
            ${
              f.type === "dir"
                ? '<path fill="currentColor" d="M10 4H4a2 2 0 0 0-2 2v12a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2V8a2 2 0 0 0-2-2h-8l-2-2Z"/>'
                : '<path fill="currentColor" d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8l-6-6Zm-1 7V3.5L18.5 9H13Z"/>'
            }
          </svg>
          <a href="${escapeHtml(f.html_url)}" target="_blank" rel="noreferrer">${escapeHtml(f.name)}</a>
          ${f.type === "file" ? `<span class="file-size">${formatSize(Math.max(1, Math.round(f.size / 1024)))}</span>` : ""}
        </li>`
      )
      .join("");
  }

  // ---------- Tabs ----------

  function activateTab(name) {
    els.tabs.forEach((t) => t.classList.toggle("tab-active", t.dataset.tab === name));
    document.querySelectorAll(".tab-panel").forEach((p) => {
      p.classList.toggle("tab-panel--active", p.id === `panel-${name}`);
    });
  }

  // ---------- Init ----------

  async function analyze(repoSpec) {
    if (!repoSpec) return;
    showLoading();
    try {
      const result = await fetchAnalysis(repoSpec);
      render(result);
      // Reflect query param without scrolling
      const url = new URL(window.location.href);
      url.searchParams.set("repo", repoSpec);
      window.history.replaceState(null, "", url);
    } catch (err) {
      console.error(err);
      let detail = "";
      if (err.body && err.body.documentation_url) {
        detail = err.body.documentation_url;
      } else if (err.status === 429) {
        detail = "GitHub API rate limit exceeded. Set a GITHUB_TOKEN to raise the limit.";
      }
      showError(err.message || "Analysis failed.", detail);
    }
  }

  function init() {
    els.form.addEventListener("submit", (e) => {
      e.preventDefault();
      const val = els.input.value.trim();
      if (!val) return;
      analyze(val);
    });

    els.chips.forEach((chip) => {
      chip.addEventListener("click", () => {
        const repo = chip.dataset.repo;
        els.input.value = repo;
        analyze(repo);
      });
    });

    els.tabs.forEach((t) =>
      t.addEventListener("click", () => activateTab(t.dataset.tab))
    );

    // Pre-fill from ?repo=
    const params = new URLSearchParams(window.location.search);
    const preRepo = params.get("repo");
    if (preRepo) {
      els.input.value = preRepo;
      analyze(preRepo);
    }
  }

  return { init };
})();

document.addEventListener("DOMContentLoaded", () => App.init());
