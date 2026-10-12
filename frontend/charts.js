/* RepoScope — chart rendering helpers (Chart.js v4). */

const RepoScopeCharts = (() => {
  const languagePalette = [
    "#7c5cff", "#4ee3a3", "#ff8a8a", "#ffc45e", "#5cc8ff",
    "#c5b4ff", "#ff5fa2", "#5ee0c2", "#ffaa5e", "#a3ff5e",
    "#5e8eff", "#ff5e5e", "#b3b3b3", "#9aff5e", "#5effd1",
  ];

  let charts = {
    commits: null,
    languages: null,
    contributors: null,
  };

  function destroy() {
    Object.values(charts).forEach((c) => c && c.destroy());
    charts = { commits: null, languages: null, contributors: null };
  }

  function renderCommits(weekly) {
    const ctx = document.getElementById("chart-commits");
    if (!ctx) return;
    if (charts.commits) charts.commits.destroy();

    const labels = weekly.map((w) => w.week || "");
    const data = weekly.map((w) => w.commits);

    charts.commits = new Chart(ctx, {
      type: "line",
      data: {
        labels,
        datasets: [
          {
            label: "Commits / week",
            data,
            borderColor: "#7c5cff",
            backgroundColor: (ctx) => {
              const chart = ctx.chart;
              const { ctx: c, chartArea } = chart;
              if (!chartArea) return "rgba(124, 92, 255, 0.2)";
              const g = c.createLinearGradient(0, chartArea.top, 0, chartArea.bottom);
              g.addColorStop(0, "rgba(124, 92, 255, 0.45)");
              g.addColorStop(1, "rgba(124, 92, 255, 0)");
              return g;
            },
            fill: true,
            tension: 0.35,
            pointRadius: 0,
            pointHoverRadius: 5,
            pointHoverBackgroundColor: "#fff",
            pointHoverBorderColor: "#7c5cff",
            borderWidth: 2,
          },
        ],
      },
      options: chartOptions({
        scales: {
          x: {
            grid: { display: false },
            ticks: {
              color: "#5e6878",
              maxTicksLimit: 8,
              maxRotation: 0,
            },
          },
          y: {
            beginAtZero: true,
            grid: { color: "rgba(255,255,255,0.04)" },
            ticks: { color: "#5e6878", precision: 0 },
          },
        },
      }),
    });
  }

  function renderLanguages(languages) {
    const ctx = document.getElementById("chart-languages");
    if (!ctx) return;
    if (charts.languages) charts.languages.destroy();

    const top = languages.slice(0, 8);
    const labels = top.map((l) => l.name);
    const data = top.map((l) => l.percentage);
    const colors = top.map((_, i) => languagePalette[i % languagePalette.length]);

    charts.languages = new Chart(ctx, {
      type: "doughnut",
      data: {
        labels,
        datasets: [
          {
            data,
            backgroundColor: colors,
            borderColor: "#0b0e14",
            borderWidth: 2,
            hoverOffset: 6,
          },
        ],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        cutout: "62%",
        plugins: {
          legend: { display: false },
          tooltip: tooltipConfig((ctx) => `${ctx.label}: ${ctx.raw.toFixed(1)}%`),
        },
      },
    });

    const legendEl = document.getElementById("lang-legend");
    if (legendEl) {
      legendEl.innerHTML = "";
      top.forEach((l, i) => {
        const span = document.createElement("span");
        span.className = "lang-legend-item";
        span.innerHTML = `<span class="lang-legend-dot" style="background:${colors[i]}"></span>${escapeHtml(l.name)} <span class="muted">${l.percentage.toFixed(1)}%</span>`;
        legendEl.appendChild(span);
      });
    }
  }

  function renderContributors(contributors) {
    const ctx = document.getElementById("chart-contributors");
    if (!ctx) return;
    if (charts.contributors) charts.contributors.destroy();

    const top = contributors.slice(0, 12);
    const labels = top.map((c) => c.login);
    const data = top.map((c) => c.contributions);

    charts.contributors = new Chart(ctx, {
      type: "bar",
      data: {
        labels,
        datasets: [
          {
            label: "Commits",
            data,
            backgroundColor: "rgba(124, 92, 255, 0.55)",
            borderColor: "#7c5cff",
            borderWidth: 1,
            borderRadius: 4,
            hoverBackgroundColor: "#7c5cff",
          },
        ],
      },
      options: chartOptions({
        indexAxis: "y",
        scales: {
          x: {
            beginAtZero: true,
            grid: { color: "rgba(255,255,255,0.04)" },
            ticks: { color: "#5e6878", precision: 0 },
          },
          y: {
            grid: { display: false },
            ticks: { color: "#9aa3b2", font: { family: "'JetBrains Mono', monospace", size: 11 } },
          },
        },
      }),
    });
  }

  function chartOptions(overrides = {}) {
    return Object.assign(
      {
        responsive: true,
        maintainAspectRatio: false,
        interaction: { mode: "index", intersect: false },
        plugins: {
          legend: { display: false },
          tooltip: tooltipConfig(),
        },
        animation: { duration: 350 },
      },
      overrides
    );
  }

  function tooltipConfig(labelFn) {
    return {
      backgroundColor: "#1a1f2e",
      borderColor: "#2f3a55",
      borderWidth: 1,
      titleColor: "#e6e8ee",
      bodyColor: "#9aa3b2",
      titleFont: { family: "Inter", weight: "600" },
      bodyFont: { family: "JetBrains Mono" },
      padding: 10,
      displayColors: true,
      boxPadding: 4,
      callbacks: labelFn ? { label: labelFn } : undefined,
    };
  }

  function escapeHtml(s) {
    return String(s).replace(/[&<>"']/g, (c) => ({
      "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
    })[c]);
  }

  return { renderCommits, renderLanguages, renderContributors, destroy };
})();
