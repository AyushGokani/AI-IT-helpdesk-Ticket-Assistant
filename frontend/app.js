// AI Helpdesk Ticket Assistant — vanilla JS frontend.
// AI calls are triggered ONLY when the user clicks "Generate AI triage".

const NO_CACHE = { cache: "no-store", headers: { "cache-control": "no-cache" } };
const jsonPost = (body) => ({
  method: "POST",
  cache: "no-store",
  headers: { "content-type": "application/json", "cache-control": "no-cache" },
  body: JSON.stringify(body),
});

const api = {
  async health()              { return (await fetch("/api/health", NO_CACHE)).json(); },
  async list()                { return (await fetch("/api/tickets", NO_CACHE)).json(); },
  async get(id)               { return (await fetch(`/api/tickets/${id}`, NO_CACHE)).json(); },
  async create(payload)       { return (await fetch("/api/tickets", jsonPost(payload))).json(); },
  async upload(file)          { const fd = new FormData(); fd.append("file", file); return (await fetch("/api/tickets/upload", { method: "POST", cache: "no-store", body: fd })).json(); },
  async analyze(id, offline)  { return (await fetch(`/api/tickets/${id}/analyze`, jsonPost({ offline: !!offline }))).json(); },
  async setStatus(id, status) { return (await fetch(`/api/tickets/${id}/status`, jsonPost({ status }))).json(); },
  async remove(id)            { return (await fetch(`/api/tickets/${id}`, { method: "DELETE", cache: "no-store" })).json(); },
  async clear()               { return (await fetch("/api/tickets/clear", { method: "POST", cache: "no-store" })).json(); },
  async stats()               { return (await fetch("/api/stats", NO_CACHE)).json(); },
};

const CATEGORY_STYLES = {
  network:  "bg-sky-100 text-sky-800",
  login:    "bg-amber-100 text-amber-800",
  hardware: "bg-rose-100 text-rose-800",
  software: "bg-violet-100 text-violet-800",
  email:    "bg-emerald-100 text-emerald-800",
  access:   "bg-indigo-100 text-indigo-800",
  billing:  "bg-yellow-100 text-yellow-800",
  other:    "bg-slate-100 text-slate-700",
};

const PRIORITY_STYLES = {
  urgent: "bg-rose-600 text-white",
  high:   "bg-orange-500 text-white",
  medium: "bg-sky-500 text-white",
  low:    "bg-slate-400 text-white",
};

const STATUS_STYLES = {
  open:        "bg-emerald-100 text-emerald-800",
  in_progress: "bg-amber-100 text-amber-800",
  resolved:    "bg-slate-200 text-slate-700",
};

const state = {
  tickets: [],
  selectedId: null,
  aiConfigured: false,
};

// ---------------------------------------------------------------------------
// Bootstrapping
// ---------------------------------------------------------------------------

document.addEventListener("DOMContentLoaded", async () => {
  bindUi();
  const health = await api.health();
  state.aiConfigured = !!health.ai_configured;
  renderAiBadge(health);
  await refresh();
});

function bindUi() {
  document.getElementById("new-ticket-btn").addEventListener("click", () => toggleModal(true));
  document.querySelectorAll("[data-close]").forEach((el) => el.addEventListener("click", () => toggleModal(false)));

  document.getElementById("new-ticket-form").addEventListener("submit", async (e) => {
    e.preventDefault();
    const fd = new FormData(e.currentTarget);
    const created = await api.create(Object.fromEntries(fd.entries()));
    if (created && created.id) {
      toast("Ticket created");
      e.currentTarget.reset();
      toggleModal(false);
      state.selectedId = created.id;
      await refresh();
    } else {
      toast(created.error || "Could not create ticket", true);
    }
  });

  const input = document.getElementById("csv-input");
  input.addEventListener("change", async () => {
    const file = input.files && input.files[0];
    if (!file) return;
    document.getElementById("upload-status").textContent = `Uploading ${file.name}…`;
    const result = await api.upload(file);
    if (result && result.created) {
      document.getElementById("upload-status").textContent = `Imported ${result.created} ticket(s) from ${file.name}`;
      toast(`Imported ${result.created} tickets`);
      await refresh();
    } else {
      document.getElementById("upload-status").textContent = result.error || "Upload failed";
      toast(result.error || "Upload failed", true);
    }
    input.value = "";
  });

  document.getElementById("clear-btn").addEventListener("click", async () => {
    if (!confirm("Delete ALL tickets? This cannot be undone.")) return;
    await api.clear();
    state.selectedId = null;
    await refresh();
  });
}

// ---------------------------------------------------------------------------
// Render
// ---------------------------------------------------------------------------

async function refresh() {
  const [tickets, stats] = await Promise.all([api.list(), api.stats()]);
  state.tickets = tickets;
  renderStats(stats);
  renderList(tickets);
  if (state.selectedId && tickets.find((t) => t.id === state.selectedId)) {
    renderDetail(tickets.find((t) => t.id === state.selectedId));
  } else if (tickets.length) {
    state.selectedId = tickets[0].id;
    renderDetail(tickets[0]);
  } else {
    state.selectedId = null;
    document.getElementById("detail").innerHTML =
      `<div class="p-10 text-center text-sm text-slate-500">No tickets yet — create one or import a CSV.</div>`;
  }
}

function renderAiBadge(health) {
  const el = document.getElementById("ai-badge");
  if (health.ai_configured) {
    el.className = "hidden sm:inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-medium bg-emerald-100 text-emerald-800";
    el.textContent = `AI: ${health.model}`;
  } else {
    el.className = "hidden sm:inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-medium bg-slate-100 text-slate-700";
    el.textContent = "AI: heuristic mode (no key)";
  }
}

function renderStats(stats) {
  const cards = [
    { label: "Total tickets", value: stats.total },
    { label: "Open",          value: stats.open },
    { label: "Triaged by AI", value: stats.analyzed },
    { label: "Resolved",      value: stats.resolved },
  ];
  document.getElementById("stats").innerHTML = cards.map((c) => `
    <div class="rounded-xl border border-slate-200 bg-white px-4 py-3 shadow-sm">
      <div class="text-xs text-slate-500">${c.label}</div>
      <div class="text-2xl font-semibold tracking-tight">${c.value}</div>
    </div>
  `).join("");
}

function renderList(tickets) {
  const ul = document.getElementById("ticket-list");
  if (!tickets.length) {
    ul.innerHTML = `<li class="p-6 text-sm text-slate-500 text-center">No tickets yet.</li>`;
    return;
  }
  ul.innerHTML = tickets.map((t) => {
    const ai = t.ai || {};
    const cat = ai.category;
    const pri = ai.priority;
    const isSel = t.id === state.selectedId;
    return `
      <li data-id="${t.id}" class="cursor-pointer p-4 ${isSel ? "bg-indigo-50/60" : "hover:bg-slate-50"}">
        <div class="flex items-start justify-between gap-3">
          <div class="min-w-0 flex-1">
            <div class="flex items-center gap-2">
              <span class="text-xs font-mono text-slate-400">#${t.id.slice(0, 6)}</span>
              <span class="truncate text-sm font-medium">${escapeHtml(t.subject)}</span>
            </div>
            <p class="mt-1 line-clamp-2 text-xs text-slate-500">${escapeHtml(t.body || "(no description)")}</p>
            <div class="mt-2 flex flex-wrap items-center gap-1.5">
              ${cat ? badge(cat, CATEGORY_STYLES[cat] || CATEGORY_STYLES.other) : ""}
              ${pri ? badge(pri, PRIORITY_STYLES[pri] || PRIORITY_STYLES.medium) : ""}
              ${badge(t.status.replace("_", " "), STATUS_STYLES[t.status] || STATUS_STYLES.open)}
              ${ai.source ? `<span class="text-[10px] text-slate-400">${ai.source}</span>` : ""}
            </div>
          </div>
        </div>
      </li>
    `;
  }).join("");

  ul.querySelectorAll("li[data-id]").forEach((li) => {
    li.addEventListener("click", () => {
      state.selectedId = li.dataset.id;
      const t = state.tickets.find((x) => x.id === state.selectedId);
      renderDetail(t);
      renderList(state.tickets);
    });
  });
}

function renderDetail(t) {
  if (!t) return;
  const ai = t.ai;
  const detail = document.getElementById("detail");

  const aiBlock = ai
    ? `
      <div class="mt-6 grid grid-cols-1 sm:grid-cols-3 gap-3">
        <div class="rounded-lg border border-slate-200 p-3">
          <div class="text-[10px] uppercase tracking-wide text-slate-500">Category</div>
          <div class="mt-1">${badge(ai.category, CATEGORY_STYLES[ai.category] || CATEGORY_STYLES.other)}</div>
        </div>
        <div class="rounded-lg border border-slate-200 p-3">
          <div class="text-[10px] uppercase tracking-wide text-slate-500">Priority</div>
          <div class="mt-1">${badge(ai.priority, PRIORITY_STYLES[ai.priority] || PRIORITY_STYLES.medium)}</div>
        </div>
        <div class="rounded-lg border border-slate-200 p-3">
          <div class="text-[10px] uppercase tracking-wide text-slate-500">Confidence</div>
          <div class="mt-1 text-sm font-semibold">${Math.round((ai.confidence || 0) * 100)}%</div>
        </div>
      </div>

      ${ai.summary ? `
        <div class="mt-4 rounded-lg bg-slate-50 border border-slate-200 p-3">
          <div class="text-[10px] uppercase tracking-wide text-slate-500">AI summary</div>
          <p class="mt-1 text-sm text-slate-800">${escapeHtml(ai.summary)}</p>
        </div>` : ""
      }

      <div class="mt-4">
        <div class="text-[10px] uppercase tracking-wide text-slate-500">Suggested resolution</div>
        <ol class="mt-2 list-decimal pl-5 space-y-1 text-sm text-slate-800">
          ${(ai.resolution_steps || []).map((s) => `<li>${escapeHtml(s)}</li>`).join("")}
        </ol>
      </div>

      <div class="mt-5">
        <div class="flex items-center justify-between">
          <div class="text-[10px] uppercase tracking-wide text-slate-500">Reply draft</div>
          <button id="copy-reply" class="text-xs font-medium text-indigo-600 hover:underline">Copy</button>
        </div>
        <pre id="reply-pre" class="reply-pre mt-2 rounded-lg border border-slate-200 bg-white p-3">${escapeHtml(ai.reply_draft || "")}</pre>
      </div>

      <div class="mt-4 text-[11px] text-slate-400">Generated by ${escapeHtml(ai.source || "")}${t.analyzed_at ? ` · ${new Date(t.analyzed_at).toLocaleString()}` : ""}</div>
    `
    : `
      <div class="mt-6 rounded-lg border-2 border-dashed border-slate-300 p-6 text-center">
        <p class="text-sm text-slate-600">No AI triage yet for this ticket.</p>
        <p class="mt-1 text-xs text-slate-500">Click <strong>Generate AI triage</strong> to classify, suggest steps, and draft a reply.</p>
      </div>
    `;

  detail.innerHTML = `
    <div class="p-6 fade-in">
      <div class="flex items-start justify-between gap-4">
        <div class="min-w-0">
          <div class="flex items-center gap-2 text-xs text-slate-500">
            <span class="font-mono">#${t.id}</span>
            <span>·</span>
            <span>${new Date(t.created_at).toLocaleString()}</span>
          </div>
          <h2 class="mt-1 text-xl font-semibold tracking-tight">${escapeHtml(t.subject)}</h2>
          <div class="mt-1 text-xs text-slate-500">From <span class="font-medium text-slate-700">${escapeHtml(t.requester)}</span></div>
        </div>
        <div class="flex items-center gap-2">
          <select id="status-select" class="rounded-md border border-slate-300 px-2 py-1.5 text-xs">
            <option value="open"        ${t.status === "open" ? "selected" : ""}>open</option>
            <option value="in_progress" ${t.status === "in_progress" ? "selected" : ""}>in progress</option>
            <option value="resolved"    ${t.status === "resolved" ? "selected" : ""}>resolved</option>
          </select>
          <button id="delete-btn" class="rounded-md border border-slate-300 px-2 py-1.5 text-xs text-slate-700 hover:bg-rose-50 hover:text-rose-700 hover:border-rose-300">Delete</button>
        </div>
      </div>

      <div class="mt-5 rounded-lg bg-slate-50 border border-slate-200 p-4">
        <div class="text-[10px] uppercase tracking-wide text-slate-500">Original message</div>
        <p class="mt-2 whitespace-pre-wrap text-sm text-slate-800">${escapeHtml(t.body || "(no description)")}</p>
      </div>

      <div class="mt-5 flex flex-wrap items-center gap-2">
        <button id="generate-btn"
          class="inline-flex items-center gap-2 rounded-md bg-gradient-to-r from-indigo-600 to-violet-600 px-4 py-2 text-sm font-semibold text-white shadow-sm hover:from-indigo-500 hover:to-violet-500 disabled:opacity-60">
          <span id="generate-label">Generate AI triage</span>
        </button>
        ${state.aiConfigured ? `
          <label class="inline-flex items-center gap-1.5 text-xs text-slate-600">
            <input id="offline-toggle" type="checkbox" class="rounded border-slate-300" />
            Use offline heuristic (no API call)
          </label>
        ` : `<span class="text-xs text-slate-500">No OpenAI key — running in heuristic mode.</span>`}
      </div>

      ${aiBlock}
    </div>
  `;

  document.getElementById("generate-btn").addEventListener("click", onGenerate);
  document.getElementById("delete-btn").addEventListener("click", async () => {
    if (!confirm("Delete this ticket?")) return;
    await api.remove(t.id);
    state.selectedId = null;
    await refresh();
  });
  document.getElementById("status-select").addEventListener("change", async (e) => {
    await api.setStatus(t.id, e.target.value);
    await refresh();
  });
  const copyBtn = document.getElementById("copy-reply");
  if (copyBtn) {
    copyBtn.addEventListener("click", async () => {
      const text = document.getElementById("reply-pre").textContent;
      await navigator.clipboard.writeText(text);
      toast("Reply copied to clipboard");
    });
  }
}

async function onGenerate() {
  const btn = document.getElementById("generate-btn");
  const label = document.getElementById("generate-label");
  const offline = document.getElementById("offline-toggle")?.checked || false;
  btn.disabled = true;
  label.textContent = offline ? "Running heuristic…" : "Calling AI…";
  try {
    const updated = await api.analyze(state.selectedId, offline);
    if (updated && updated.id) {
      // Update local cache & re-render
      const idx = state.tickets.findIndex((x) => x.id === updated.id);
      if (idx >= 0) state.tickets[idx] = updated;
      renderDetail(updated);
      renderList(state.tickets);
      const stats = await api.stats();
      renderStats(stats);
      toast("AI triage ready");
    } else {
      toast(updated.error || "AI call failed", true);
    }
  } catch (e) {
    toast("AI call failed", true);
  } finally {
    btn.disabled = false;
    label.textContent = "Re-run AI triage";
  }
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function badge(text, classes) {
  return `<span class="inline-flex items-center rounded-full px-2 py-0.5 text-[11px] font-medium ${classes}">${escapeHtml(text)}</span>`;
}

function escapeHtml(str) {
  return String(str ?? "").replace(/[&<>"']/g, (c) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  }[c]));
}

function toggleModal(open) {
  document.getElementById("modal").classList.toggle("hidden", !open);
}

let toastTimer = null;
function toast(message, isError = false) {
  const el = document.getElementById("toast");
  el.textContent = message;
  el.classList.remove("hidden");
  el.classList.toggle("bg-rose-600", isError);
  el.classList.toggle("bg-slate-900", !isError);
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => el.classList.add("hidden"), 2400);
}
