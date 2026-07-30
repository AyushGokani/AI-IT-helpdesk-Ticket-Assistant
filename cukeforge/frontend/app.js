const state = {
  tickets: [],
  selected: null,
  mode: { jira: "demo", ai: "heuristic" },
};

const els = {
  ticketList: document.getElementById("ticketList"),
  ticketPanel: document.getElementById("ticketPanel"),
  ticketMeta: document.getElementById("ticketMeta"),
  runPanel: document.getElementById("runPanel"),
  runMeta: document.getElementById("runMeta"),
  btnForge: document.getElementById("btnForge"),
  useAi: document.getElementById("useAi"),
  jiraMode: document.getElementById("jiraMode"),
  aiMode: document.getElementById("aiMode"),
  artifacts: document.getElementById("artifacts"),
  featureOut: document.getElementById("featureOut"),
  stepsOut: document.getElementById("stepsOut"),
  logOut: document.getElementById("logOut"),
};

async function api(path, options) {
  const res = await fetch(path, {
    headers: { "Content-Type": "application/json", ...(options?.headers || {}) },
    ...options,
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.error || `Request failed (${res.status})`);
  return data;
}

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

function selectTicket(key) {
  state.selected = state.tickets.find((t) => t.key === key) || null;
  els.btnForge.disabled = !state.selected;
  renderTickets();
  renderTicketDetail();
}

function renderTickets() {
  els.ticketList.innerHTML = "";
  if (!state.tickets.length) {
    els.ticketList.innerHTML = `<li class="empty">No tickets available.</li>`;
    return;
  }
  for (const t of state.tickets) {
    const li = document.createElement("li");
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = "ticket" + (state.selected?.key === t.key ? " active" : "");
    btn.innerHTML = `
      <span class="key">${escapeHtml(t.key)}</span>
      <span class="summary">${escapeHtml(t.summary)}</span>
      <span class="meta">${escapeHtml(t.issue_type || "Story")} · ${escapeHtml(t.status || "")} · ${escapeHtml(t.priority || "")}</span>
    `;
    btn.addEventListener("click", () => selectTicket(t.key));
    li.appendChild(btn);
    els.ticketList.appendChild(li);
  }
}

function renderTicketDetail() {
  const t = state.selected;
  if (!t) {
    els.ticketMeta.textContent = "Pick a ticket to inspect criteria.";
    els.ticketPanel.innerHTML = `<p class="empty">No ticket selected.</p>`;
    return;
  }
  els.ticketMeta.textContent = `${t.key} · source: ${t.source || state.mode.jira}`;
  const ac = (t.acceptance_criteria || [])
    .map((c) => `<li>${escapeHtml(c)}</li>`)
    .join("");
  els.ticketPanel.innerHTML = `
    <h3 style="margin:0 0 .4rem;font-family:var(--font-display);font-weight:400;font-size:1.35rem;">${escapeHtml(t.summary)}</h3>
    <p style="margin:0;color:var(--ink-soft);line-height:1.5;">${escapeHtml(t.description || "")}</p>
    <p style="margin:1rem 0 0;font-size:.78rem;font-weight:700;letter-spacing:.05em;text-transform:uppercase;color:var(--ink-soft);">Acceptance criteria</p>
    <ul class="ac-list">${ac || "<li>None listed — CukeForge will synthesize scenarios.</li>"}</ul>
  `;
}

function renderRun(run) {
  const badge = run.status || "running";
  const result = run.result || {};
  els.runMeta.textContent = `Run ${run.id} · engine ${run.engine || "—"}`;
  const iterations = (run.iterations || [])
    .map((it) => {
      const r = it.result || {};
      const label = it.passed ? "passed" : "failed";
      return `<li>Attempt ${it.attempt}: ${label} · ${r.scenarios_passed || 0}/${r.scenarios_total || 0} scenarios${it.fixed ? " · steps rewritten" : ""}</li>`;
    })
    .join("");

  els.runPanel.innerHTML = `
    <span class="status-badge ${escapeHtml(badge)}">${escapeHtml(badge)}</span>
    <p style="margin:0;color:var(--ink-soft);">
      ${result.scenarios_passed || 0} passed · ${result.scenarios_failed || 0} failed
      ${run.error ? `<br/><strong>Error:</strong> ${escapeHtml(run.error)}` : ""}
    </p>
    <ul class="iter-list">${iterations || "<li>No iterations recorded.</li>"}</ul>
  `;

  els.artifacts.hidden = false;
  els.featureOut.textContent = run.feature || "";
  els.stepsOut.textContent = run.steps || "";
  const last = (run.iterations || []).at(-1);
  const log = last?.result
    ? `${last.result.stdout || ""}\n${last.result.stderr || ""}`.trim()
    : "";
  els.logOut.textContent = log || "(no log)";
}

async function loadHealth() {
  const data = await api("/api/health");
  state.mode.jira = data.jira_mode;
  state.mode.ai = data.ai_mode;
  els.jiraMode.textContent = `Jira: ${data.jira_mode}`;
  els.aiMode.textContent = `AI: ${data.ai_mode}`;
}

async function loadTickets() {
  const data = await api("/api/tickets");
  state.tickets = data.tickets || [];
  if (data.mode) state.mode.jira = data.mode;
  els.jiraMode.textContent = `Jira: ${state.mode.jira}`;
  renderTickets();
  if (state.tickets[0]) selectTicket(state.tickets[0].key);
}

els.btnForge.addEventListener("click", async () => {
  if (!state.selected) return;
  els.btnForge.disabled = true;
  els.btnForge.textContent = "Forging…";
  els.runPanel.innerHTML = `<span class="status-badge running">running</span><p class="empty">Generating feature, steps, and executing Behave…</p>`;
  try {
    const run = await api("/api/runs", {
      method: "POST",
      body: JSON.stringify({
        ticket_key: state.selected.key,
        use_ai: els.useAi.checked,
        max_iterations: 3,
      }),
    });
    renderRun(run);
  } catch (err) {
    els.runPanel.innerHTML = `<span class="status-badge failed">failed</span><p>${escapeHtml(err.message)}</p>`;
  } finally {
    els.btnForge.disabled = !state.selected;
    els.btnForge.textContent = "Forge & pass tests";
  }
});

(async function init() {
  try {
    await loadHealth();
    await loadTickets();
  } catch (err) {
    els.ticketList.innerHTML = `<li class="empty">${escapeHtml(err.message)}</li>`;
  }
})();
