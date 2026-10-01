const state = {
  daily: null,
  pendingJob: null,
  blurb: "",
};

async function api(path, options) {
  const res = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(text || res.statusText);
  }
  return res.json();
}

function escapeHtml(str) {
  return String(str || "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

function renderKpis(kpis) {
  const el = document.getElementById("kpis");
  if (!kpis) {
    el.innerHTML = "";
    return;
  }
  el.innerHTML = `
    <div class="kpi"><div class="n">${kpis.appliedToday}</div><div class="l">Applied today</div></div>
    <div class="kpi"><div class="n">${kpis.appliedTotal}</div><div class="l">Applied total / ${kpis.targetTotal} target</div></div>
    <div class="kpi"><div class="n">${kpis.interviewing}</div><div class="l">Interviewing</div></div>
    <div class="kpi"><div class="n">${kpis.dailyBatchSize}</div><div class="l">Roles in daily batch</div></div>
  `;
}

function renderBoards(boards) {
  const el = document.getElementById("boardLinks");
  el.innerHTML = (boards || [])
    .map(
      (b) =>
        `<a class="board-chip" href="${escapeHtml(b.url)}" target="_blank" rel="noopener">${escapeHtml(b.label)}</a>`
    )
    .join("");
}

function renderJobs(jobs) {
  const el = document.getElementById("jobList");
  if (!jobs || !jobs.length) {
    el.innerHTML = `<div class="empty">No verified live remote BA roles in today’s pool. Hit Refresh pool or open the board chips above.</div>`;
    return;
  }
  el.innerHTML = jobs
    .map((job) => {
      const done = job.applicationStatus === "applied" || job.applicationStatus === "skipped";
      const board = job.board || job.source || "Other";
      const reasons = (job.reasons || []).map((r) => `<span class="pill">${escapeHtml(r)}</span>`).join("");
      const verified = job.linkStatus === "verified"
        ? `<span class="pill ok-pill">Link verified</span>`
        : job.linkStatus === "unverified"
          ? `<span class="pill">Link unchecked</span>`
          : "";
      return `
      <article class="job ${done ? "done" : ""}" data-id="${escapeHtml(job.id)}">
        <div class="job-top">
          <div>
            <div class="board-line">
              <span class="board-badge" title="Job board / ATS">${escapeHtml(board)}</span>
              ${verified}
            </div>
            <h3>${escapeHtml(job.title)}</h3>
            <div class="meta">${escapeHtml(job.company)} · ${escapeHtml(job.location)}${job.salary ? " · " + escapeHtml(job.salary) : ""}${job.posted ? " · posted " + escapeHtml(job.posted) : ""}</div>
          </div>
          <div class="score"><b>${job.score ?? "—"}</b><span>fit</span></div>
        </div>
        <div class="reasons">${reasons}</div>
        <p class="desc">${escapeHtml(job.description || "No description preview.")}</p>
        <div class="job-actions">
          <button type="button" class="btn small ok" data-action="apply" ${done ? "disabled" : ""}>Apply on ${escapeHtml(board)}</button>
          <button type="button" class="btn small warn" data-action="skip" ${done ? "disabled" : ""}>Skip</button>
          <a class="btn small ghost" style="color:var(--accent-2);border:1px solid var(--line);text-decoration:none" href="${escapeHtml(job.url)}" target="_blank" rel="noopener">Open on ${escapeHtml(board)}</a>
          ${job.applicationStatus ? `<span class="pill">Status: ${escapeHtml(job.applicationStatus)}</span>` : ""}
        </div>
      </article>`;
    })
    .join("");
}

async function renderHistory() {
  const data = await api("/api/applications");
  const el = document.getElementById("historyList");
  const apps = data.applications || [];
  if (!apps.length) {
    el.innerHTML = `<div class="empty">No applications logged yet.</div>`;
    return;
  }
  el.innerHTML = apps
    .slice(0, 20)
    .map((a) => {
      const when = (a.at || "").slice(0, 10);
      return `
      <div class="hist">
        <span class="badge ${escapeHtml(a.status)}">${escapeHtml(a.status)}</span>
        <div>
          <strong>${escapeHtml(a.title)}</strong>
          <div class="meta">${escapeHtml(a.company)} · ${escapeHtml(when)}</div>
        </div>
        <a href="${escapeHtml(a.url)}" target="_blank" rel="noopener">Link</a>
      </div>`;
    })
    .join("");
}

async function copyBlurb() {
  const text = state.blurb || (await api("/api/cover-blurb")).blurb;
  state.blurb = text;
  await navigator.clipboard.writeText(text);
  const btn = document.getElementById("btnCopyBlurb");
  const prev = btn.textContent;
  btn.textContent = "Copied";
  setTimeout(() => (btn.textContent = prev), 1200);
}

async function loadDaily(force = false) {
  document.getElementById("jobList").innerHTML = `<div class="loading">Loading today’s roles…</div>`;
  const path = force ? "/api/jobs/daily?force=1" : "/api/jobs/daily";
  const data = await api(path);
  state.daily = data;
  state.blurb = data.coverBlurb || "";
  if (data.candidate) {
    document.getElementById("candidateName").textContent = data.candidate.name;
    document.getElementById("candidateHeadline").textContent =
      data.candidate.headline || "Business Analyst · Fully remote";
  }
  document.getElementById("batchMeta").textContent =
    `· ${data.date} · pool ${data.poolSize} · remaining ${data.remaining}`;
  renderKpis(data.kpis);
  renderBoards(data.boards);
  renderJobs(data.jobs);
  await renderHistory();
}

async function markStatus(job, status) {
  await api("/api/applications", {
    method: "POST",
    body: JSON.stringify({
      jobId: job.id,
      status,
      title: job.title,
      company: job.company,
      url: job.url,
      source: job.source,
    }),
  });
  await loadDaily(false);
}

function findJob(id) {
  return (state.daily?.jobs || []).find((j) => j.id === id);
}

document.getElementById("jobList").addEventListener("click", async (e) => {
  const btn = e.target.closest("[data-action]");
  if (!btn) return;
  const card = btn.closest(".job");
  const job = findJob(card?.dataset.id);
  if (!job) return;

  if (btn.dataset.action === "skip") {
    await markStatus(job, "skipped");
    return;
  }

  if (btn.dataset.action === "apply") {
    state.pendingJob = job;
    try {
      await navigator.clipboard.writeText(state.blurb || "");
    } catch (_) {
      /* clipboard may be blocked */
    }
    window.open(job.url, "_blank", "noopener");
    document.getElementById("applyJobTitle").textContent = `${job.title} · ${job.company}`;
    document.getElementById("applyDialog").showModal();
  }
});

document.getElementById("applyForm").addEventListener("close", async () => {
  const dialog = document.getElementById("applyDialog");
  const value = dialog.returnValue;
  const job = state.pendingJob;
  state.pendingJob = null;
  if (value === "applied" && job) {
    await markStatus(job, "applied");
  }
});

document.getElementById("btnCopyBlurb").addEventListener("click", () => copyBlurb());
document.getElementById("btnRefresh").addEventListener("click", async () => {
  const btn = document.getElementById("btnRefresh");
  btn.disabled = true;
  btn.textContent = "Refreshing…";
  try {
    await api("/api/jobs/refresh", { method: "POST", body: "{}" });
    await loadDaily(false);
  } finally {
    btn.disabled = false;
    btn.textContent = "Refresh pool";
  }
});

loadDaily(false).catch((err) => {
  document.getElementById("jobList").innerHTML =
    `<div class="empty">Failed to load: ${escapeHtml(err.message)}</div>`;
});
