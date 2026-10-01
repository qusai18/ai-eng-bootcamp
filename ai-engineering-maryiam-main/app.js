const MODELS = [
  {
    id: "m01",
    name: "OT Failure Predictor",
    type: "Predictive",
    owner: "Sarah Chen",
    bu: "Transmission",
    risk: "High",
    status: "Production",
    compliance: "Partial",
    audit: "2026-07-12",
  },
  {
    id: "m02",
    name: "Load Forecasting Engine",
    type: "Forecasting",
    owner: "Marcus Webb",
    bu: "Grid Ops",
    risk: "Medium",
    status: "Production",
    compliance: "Compliant",
    audit: "2026-08-01",
  },
  {
    id: "m03",
    name: "Customer Churn Analyzer",
    type: "Classification",
    owner: "Priya Nair",
    bu: "Customer Ops",
    risk: "Low",
    status: "Production",
    compliance: "Compliant",
    audit: "2026-06-18",
  },
  {
    id: "m04",
    name: "Fraud Detection Model v3",
    type: "Anomaly Detection",
    owner: "James Ortiz",
    bu: "Finance",
    risk: "Critical",
    status: "In Review",
    compliance: "Non-Compliant",
    audit: "2026-08-10",
  },
  {
    id: "m05",
    name: "Demand Response Optimizer",
    type: "Optimization",
    owner: "Elena Vasquez",
    bu: "Grid Ops",
    risk: "High",
    status: "Production",
    compliance: "Partial",
    audit: "2026-05-22",
  },
  {
    id: "m06",
    name: "Sentiment Analysis API",
    type: "NLP",
    owner: "Tom Bradley",
    bu: "Marketing",
    risk: "Low",
    status: "Development",
    compliance: "Not Assessed",
    audit: "2026-08-14",
  },
  {
    id: "m07",
    name: "Vegetation Risk Scout",
    type: "Computer Vision",
    owner: "Aisha Rahman",
    bu: "Transmission",
    risk: "Medium",
    status: "Production",
    compliance: "Compliant",
    audit: "2026-07-28",
  },
  {
    id: "m08",
    name: "Outage Triage Assistant",
    type: "Generative AI",
    owner: "Noah Kim",
    bu: "Customer Ops",
    risk: "High",
    status: "In Review",
    compliance: "Partial",
    audit: "2026-08-08",
  },
  {
    id: "m09",
    name: "Workforce Scheduling AI",
    type: "Optimization",
    owner: "Lena Brooks",
    bu: "Field Ops",
    risk: "Medium",
    status: "Production",
    compliance: "Compliant",
    audit: "2026-04-30",
  },
  {
    id: "m10",
    name: "Cyber Threat Classifier",
    type: "Classification",
    owner: "Derek Holt",
    bu: "Security",
    risk: "Critical",
    status: "In Review",
    compliance: "Non-Compliant",
    audit: "2026-08-12",
  },
  {
    id: "m11",
    name: "Meter Anomaly Detector",
    type: "Anomaly Detection",
    owner: "Sofia Mendes",
    bu: "Metering",
    risk: "Low",
    status: "Production",
    compliance: "Compliant",
    audit: "2026-06-03",
  },
  {
    id: "m12",
    name: "Legacy Tariff Estimator",
    type: "Predictive",
    owner: "Chris Palumbo",
    bu: "Finance",
    risk: "Medium",
    status: "Retired",
    compliance: "Not Assessed",
    audit: "2025-11-19",
  },
];

const AUDIT_EVENTS = [
  {
    time: "2026-08-15 09:42",
    title: "Fraud Detection Model v3 escalated to Critical",
    detail: "Bias testing incomplete · missing human override evidence",
  },
  {
    time: "2026-08-14 16:10",
    title: "Sentiment Analysis API entered Development gate",
    detail: "Owner Tom Bradley · Marketing sandbox only",
  },
  {
    time: "2026-08-12 11:05",
    title: "Cyber Threat Classifier non-compliance recorded",
    detail: "Policy GAP-AI-04 · adversarial robustness pending",
  },
  {
    time: "2026-08-10 13:28",
    title: "Load Forecasting Engine audit closed",
    detail: "Compliant · next review scheduled 2027-02-01",
  },
  {
    time: "2026-08-08 08:55",
    title: "Outage Triage Assistant submitted for governance review",
    detail: "Generative AI use case · hallucination controls required",
  },
];

const POLICIES = [
  { name: "Model Inventory Mandate", coverage: "12 / 12 models", status: "Enforced" },
  { name: "Human-in-the-Loop for Critical Risk", coverage: "2 gaps", status: "At Risk" },
  { name: "Quarterly Bias & Fairness Review", coverage: "9 / 12 complete", status: "Partial" },
  { name: "Production Change Control", coverage: "7 production models", status: "Enforced" },
];

const state = {
  view: "registry",
  statusFilter: "All",
  query: "",
  globalQuery: "",
};

const TITLES = {
  registry: "Model Registry",
  governance: "Governance",
  risk: "Risk Center",
  audit: "Audit Trail",
  settings: "Settings",
};

function slug(value) {
  return String(value).toLowerCase().replace(/\s+/g, "-").replace(/\//g, "-");
}

function matchesQuery(model, q) {
  if (!q) return true;
  const hay = [model.name, model.type, model.owner, model.bu, model.risk, model.status, model.compliance]
    .join(" ")
    .toLowerCase();
  return hay.includes(q.toLowerCase());
}

function filteredModels() {
  return MODELS.filter((m) => {
    const statusOk = state.statusFilter === "All" || m.status === state.statusFilter;
    const localOk = matchesQuery(m, state.query);
    const globalOk = matchesQuery(m, state.globalQuery);
    return statusOk && localOk && globalOk;
  });
}

function kpiCounts(models = MODELS) {
  return {
    total: models.length,
    production: models.filter((m) => m.status === "Production").length,
    inReview: models.filter((m) => m.status === "In Review").length,
    highCritical: models.filter((m) => m.risk === "High" || m.risk === "Critical").length,
  };
}

function statusCounts(models = MODELS) {
  const keys = ["Production", "Development", "In Review", "Retired"];
  return Object.fromEntries(keys.map((k) => [k, models.filter((m) => m.status === k).length]));
}

function formatDate(d = new Date()) {
  return d.toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
  });
}

function showToast(message) {
  const el = document.getElementById("toast");
  el.textContent = message;
  el.hidden = false;
  clearTimeout(showToast._t);
  showToast._t = setTimeout(() => {
    el.hidden = true;
  }, 2200);
}

function renderDonut(counts) {
  const colors = {
    Production: "#3ecf8e",
    Development: "#d4b84a",
    "In Review": "#e8a23a",
    Retired: "#4a5a70",
  };
  const entries = Object.entries(counts);
  const total = entries.reduce((sum, [, n]) => sum + n, 0) || 1;
  const r = 54;
  const c = 2 * Math.PI * r;
  let offset = 0;
  const arcs = entries
    .map(([label, n]) => {
      const len = (n / total) * c;
      const dash = `${len} ${c - len}`;
      const circle = `<circle class="arc" cx="70" cy="70" r="${r}" fill="none" stroke="${colors[label]}" stroke-width="14" stroke-dasharray="${dash}" stroke-dashoffset="${-offset}" stroke-linecap="butt"></circle>`;
      offset += len;
      return circle;
    })
    .join("");

  const legend = entries
    .map(
      ([label, n]) => `
      <div class="legend-item">
        <div class="legend-left">
          <span class="swatch" style="background:${colors[label]}"></span>
          ${label}
        </div>
        <b>${n}</b>
      </div>`
    )
    .join("");

  return `
    <aside class="panel chart-panel">
      <h2>Status Distribution</h2>
      <div class="donut-wrap">
        <svg viewBox="0 0 140 140" aria-hidden="true">
          <circle cx="70" cy="70" r="${r}" fill="none" stroke="#1c2633" stroke-width="14"></circle>
          ${arcs}
        </svg>
        <div class="donut-center">
          <strong>${total}</strong>
          <span>models</span>
        </div>
      </div>
      <div class="legend">${legend}</div>
    </aside>`;
}

function renderRegistry() {
  const models = filteredModels();
  const kpis = kpiCounts(MODELS);
  const counts = statusCounts(MODELS);
  const filters = ["All", "Production", "In Review", "Development", "Retired"];

  const rows = models
    .map(
      (m) => `
      <tr>
        <td class="model-cell">
          <strong>${m.name}</strong>
          <span>${m.type}</span>
        </td>
        <td class="owner">${m.owner}</td>
        <td class="bu">${m.bu}</td>
        <td><span class="pill ${slug(m.risk)}">${m.risk}</span></td>
        <td><span class="pill ${slug(m.status)}">${m.status}</span></td>
        <td><span class="pill ${slug(m.compliance)}">${m.compliance}</span></td>
        <td class="audit">${m.audit}</td>
      </tr>`
    )
    .join("");

  return `
    <div class="kpi-row">
      <article class="kpi">
        <div class="kpi-top">
          <div>
            <div class="label">Total Models</div>
            <div class="value">${kpis.total}</div>
            <div class="hint">Registered in inventory</div>
          </div>
          <div class="kpi-icon orange">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><path d="M3 7h18v12H3z"/><path d="M3 7l3-3h12l3 3"/></svg>
          </div>
        </div>
      </article>
      <article class="kpi">
        <div class="kpi-top">
          <div>
            <div class="label">Production</div>
            <div class="value">${kpis.production}</div>
            <div class="hint">Active in production</div>
          </div>
          <div class="kpi-icon green">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><path d="M20 6L9 17l-5-5"/></svg>
          </div>
        </div>
      </article>
      <article class="kpi">
        <div class="kpi-top">
          <div>
            <div class="label">In Review</div>
            <div class="value">${kpis.inReview}</div>
            <div class="hint">Awaiting governance</div>
          </div>
          <div class="kpi-icon amber">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><circle cx="12" cy="12" r="8"/><path d="M12 8v4l2.5 2.5"/></svg>
          </div>
        </div>
      </article>
      <article class="kpi alert">
        <div class="kpi-top">
          <div>
            <div class="label">High / Critical Risk</div>
            <div class="value">${kpis.highCritical}</div>
            <div class="hint">Require attention</div>
          </div>
          <div class="kpi-icon red">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><circle cx="12" cy="12" r="8"/><path d="M12 8v5M12 16h.01"/></svg>
          </div>
        </div>
      </article>
    </div>

    <div class="registry-layout">
      <section class="panel">
        <div class="panel-toolbar">
          <label class="search">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><circle cx="11" cy="11" r="7"/><path d="M20 20l-3.5-3.5"/></svg>
            <input id="modelSearch" type="search" placeholder="Search models..." value="${state.query.replace(/"/g, "&quot;")}" />
          </label>
          <div class="filters">
            ${filters
              .map(
                (f) =>
                  `<button class="filter-btn${state.statusFilter === f ? " active" : ""}" data-filter="${f}">${f}</button>`
              )
              .join("")}
          </div>
        </div>
        <div class="table-wrap">
          ${
            models.length
              ? `<table>
                  <thead>
                    <tr>
                      <th>Model</th>
                      <th>Owner</th>
                      <th>BU</th>
                      <th>Risk</th>
                      <th>Status</th>
                      <th>Compliance</th>
                      <th>Audit</th>
                    </tr>
                  </thead>
                  <tbody>${rows}</tbody>
                </table>`
              : `<div class="empty">No models match the current filters.</div>`
          }
        </div>
      </section>
      ${renderDonut(counts)}
    </div>`;
}

function renderGovernance() {
  return `
    <div class="stack">
      <div class="card-grid">
        <article class="info-card">
          <h3>Policy Coverage</h3>
          <p>Active AI governance controls across the inventory.</p>
          <div class="stat-line">4 policies</div>
        </article>
        <article class="info-card">
          <h3>Exceptions Open</h3>
          <p>Temporary waivers awaiting CAIO sign-off.</p>
          <div class="stat-line" style="color:var(--amber)">3</div>
        </article>
        <article class="info-card">
          <h3>Next Control Board</h3>
          <p>Monthly model risk committee.</p>
          <div class="stat-line" style="font-size:1.2rem">Aug 28, 2026</div>
        </article>
      </div>
      <section class="list-panel">
        <h2>Policy Status</h2>
        <ul class="list">
          ${POLICIES.map(
            (p) => `
            <li>
              <div>
                <strong>${p.name}</strong>
                <span>${p.coverage}</span>
              </div>
              <span class="pill ${slug(p.status === "At Risk" ? "High" : p.status === "Partial" ? "Partial" : "Compliant")}">${p.status}</span>
            </li>`
          ).join("")}
        </ul>
      </section>
    </div>`;
}

function renderRisk() {
  const critical = MODELS.filter((m) => m.risk === "Critical" || m.risk === "High").sort((a, b) => {
    const rank = { Critical: 0, High: 1, Medium: 2, Low: 3 };
    return rank[a.risk] - rank[b.risk];
  });

  return `
    <div class="stack">
      <div class="card-grid">
        <article class="info-card">
          <h3>Critical Models</h3>
          <p>Immediate containment and evidence required.</p>
          <div class="stat-line" style="color:var(--red)">${MODELS.filter((m) => m.risk === "Critical").length}</div>
        </article>
        <article class="info-card">
          <h3>High Risk</h3>
          <p>Elevated monitoring and quarterly deep review.</p>
          <div class="stat-line" style="color:var(--amber)">${MODELS.filter((m) => m.risk === "High").length}</div>
        </article>
        <article class="info-card">
          <h3>Non-Compliant</h3>
          <p>Blocked from new production releases.</p>
          <div class="stat-line">${MODELS.filter((m) => m.compliance === "Non-Compliant").length}</div>
        </article>
      </div>
      <section class="list-panel">
        <h2>Attention Queue</h2>
        <ul class="list">
          ${critical
            .map(
              (m) => `
            <li>
              <div>
                <strong>${m.name}</strong>
                <span>${m.owner} · ${m.bu} · ${m.status}</span>
              </div>
              <span class="pill ${slug(m.risk)}">${m.risk}</span>
            </li>`
            )
            .join("")}
        </ul>
      </section>
    </div>`;
}

function renderAudit() {
  return `
    <section class="list-panel">
      <h2>Recent Audit Activity</h2>
      <p class="muted">Immutable event stream across model lifecycle gates.</p>
      <ul class="timeline">
        ${AUDIT_EVENTS.map(
          (e) => `
          <li>
            <time>${e.time}</time>
            <strong>${e.title}</strong>
            <div class="muted">${e.detail}</div>
          </li>`
        ).join("")}
      </ul>
    </section>`;
}

function renderSettings() {
  return `
    <section class="list-panel">
      <h2>Workspace Preferences</h2>
      <p class="muted">Local demo settings — nothing is persisted to a server.</p>
      <form class="settings-form" id="settingsForm">
        <div class="field">
          <label for="orgName">Organization</label>
          <input id="orgName" name="orgName" value="Meridian Energy" />
        </div>
        <div class="field">
          <label for="riskAppetite">Risk Appetite</label>
          <select id="riskAppetite" name="riskAppetite">
            <option>Conservative</option>
            <option selected>Balanced</option>
            <option>Aggressive</option>
          </select>
        </div>
        <div class="field">
          <label for="exportFormat">Default Export Format</label>
          <select id="exportFormat" name="exportFormat">
            <option selected>CSV</option>
            <option>JSON</option>
          </select>
        </div>
        <button class="btn" type="submit">Save Preferences</button>
      </form>
    </section>`;
}

function renderView() {
  document.getElementById("pageTitle").textContent = TITLES[state.view];
  document.querySelectorAll(".nav-item[data-view]").forEach((btn) => {
    btn.classList.toggle("active", btn.dataset.view === state.view);
  });

  const map = {
    registry: renderRegistry,
    governance: renderGovernance,
    risk: renderRisk,
    audit: renderAudit,
    settings: renderSettings,
  };

  ["registry", "governance", "risk", "audit", "settings"].forEach((id) => {
    const el = document.getElementById(`view-${id}`);
    const active = id === state.view;
    el.classList.toggle("hidden", !active);
    if (active) el.innerHTML = map[id]();
  });

  wireViewEvents();
}

function wireViewEvents() {
  if (state.view === "registry") {
    const search = document.getElementById("modelSearch");
    if (search) {
      search.addEventListener("input", (e) => {
        state.query = e.target.value;
        renderView();
        const again = document.getElementById("modelSearch");
        if (again) {
          again.focus();
          const len = again.value.length;
          again.setSelectionRange(len, len);
        }
      });
    }
    document.querySelectorAll(".filter-btn").forEach((btn) => {
      btn.addEventListener("click", () => {
        state.statusFilter = btn.dataset.filter;
        renderView();
      });
    });
  }

  if (state.view === "settings") {
    const form = document.getElementById("settingsForm");
    if (form) {
      form.addEventListener("submit", (e) => {
        e.preventDefault();
        showToast("Preferences saved for this session");
      });
    }
  }
}

function exportReport() {
  const header = ["name", "type", "owner", "bu", "risk", "status", "compliance", "audit"];
  const lines = [header.join(",")].concat(
    MODELS.map((m) => header.map((k) => `"${String(m[k]).replace(/"/g, '""')}"`).join(","))
  );
  const blob = new Blob([lines.join("\n")], { type: "text/csv;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `ai-governance-model-registry-${new Date().toISOString().slice(0, 10)}.csv`;
  a.click();
  URL.revokeObjectURL(url);
  showToast("Model registry exported");
}

function init() {
  const dateEl = document.getElementById("todayDate");
  const now = new Date();
  dateEl.textContent = formatDate(now);
  dateEl.dateTime = now.toISOString().slice(0, 10);

  document.querySelectorAll(".nav-item[data-view]").forEach((btn) => {
    btn.addEventListener("click", () => {
      state.view = btn.dataset.view;
      state.query = "";
      renderView();
    });
  });

  document.getElementById("exportBtn").addEventListener("click", exportReport);

  document.getElementById("globalSearch").addEventListener("input", (e) => {
    state.globalQuery = e.target.value;
    if (state.view !== "registry") {
      state.view = "registry";
    }
    renderView();
  });

  renderView();
}

init();
