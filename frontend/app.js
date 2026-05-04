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
  async seed()                { return (await fetch("/api/tickets/seed",  { method: "POST", cache: "no-store" })).json(); },
  async stats()               { return (await fetch("/api/stats", NO_CACHE)).json(); },

  async me()                  { return (await fetch("/api/auth/me", NO_CACHE)).json(); },
  async login(payload)        { const res = await fetch("/api/auth/login",  jsonPost(payload)); return { ok: res.ok, body: await res.json() }; },
  async signup(payload)       { const res = await fetch("/api/auth/signup", jsonPost(payload)); return { ok: res.ok, body: await res.json() }; },
  async logout()              { return (await fetch("/api/auth/logout", { method: "POST", cache: "no-store" })).json(); },
  async updateName(name)      { const res = await fetch("/api/auth/me", { method: "PATCH", cache: "no-store", headers: { "content-type": "application/json" }, body: JSON.stringify({ name }) }); return { ok: res.ok, body: await res.json() }; },
  async changePassword(p)     { const res = await fetch("/api/auth/change-password", jsonPost(p)); return { ok: res.ok, body: await res.json() }; },
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
  user: null,
  authMode: "login",
};

// ---------------------------------------------------------------------------
// Bootstrapping
// ---------------------------------------------------------------------------

document.addEventListener("DOMContentLoaded", async () => {
  bindAuthUi();
  bindUi();
  const health = await api.health();
  state.aiConfigured = !!health.ai_configured;
  renderAiBadge(health);

  const me = await api.me();
  if (me.user) {
    state.user = me.user;
    showApp();
    await refresh();
  } else {
    showAuth();
  }
});

// ---------------------------------------------------------------------------
// Auth UI
// ---------------------------------------------------------------------------

function showAuth() {
  document.getElementById("auth-screen").classList.remove("hidden");
  document.getElementById("account-menu").classList.add("hidden");
  document.getElementById("new-ticket-btn").classList.add("hidden");
  setAuthMode("login");
}

function showApp() {
  document.getElementById("auth-screen").classList.add("hidden");
  const menu = document.getElementById("account-menu");
  menu.classList.remove("hidden");
  document.getElementById("new-ticket-btn").classList.remove("hidden");
  if (state.user) {
    const initials = (state.user.name || state.user.email).trim().charAt(0).toUpperCase();
    document.getElementById("account-avatar").textContent = initials;
    document.getElementById("account-name").textContent = state.user.name;
    document.getElementById("account-dd-name").textContent = state.user.name;
    document.getElementById("account-dd-email").textContent = state.user.email;
  }
}

function setAuthMode(mode) {
  state.authMode = mode;
  document.querySelectorAll(".auth-tab").forEach((b) => {
    const active = b.dataset.authTab === mode;
    b.classList.toggle("bg-white", active);
    b.classList.toggle("shadow-sm", active);
    b.classList.toggle("text-slate-900", active);
    b.classList.toggle("text-slate-500", !active);
  });
  document.getElementById("auth-name-row").classList.toggle("hidden", mode !== "signup");
  document.getElementById("auth-pw-hint").classList.toggle("hidden", mode !== "signup");
  document.getElementById("auth-submit").textContent = mode === "signup" ? "Create account" : "Sign in";
  document.getElementById("auth-error").classList.add("hidden");
  const pwInput = document.querySelector('#auth-form input[name="password"]');
  if (pwInput) pwInput.autocomplete = mode === "signup" ? "new-password" : "current-password";
}

function bindAuthUi() {
  document.querySelectorAll(".auth-tab").forEach((b) => {
    b.addEventListener("click", () => setAuthMode(b.dataset.authTab));
  });

  document.getElementById("auth-form").addEventListener("submit", async (e) => {
    e.preventDefault();
    const submit = document.getElementById("auth-submit");
    const errEl = document.getElementById("auth-error");
    const fd = new FormData(e.currentTarget);
    const payload = Object.fromEntries(fd.entries());
    submit.disabled = true;
    const original = submit.textContent;
    submit.textContent = state.authMode === "signup" ? "Creating account…" : "Signing in…";
    errEl.classList.add("hidden");
    try {
      const fn = state.authMode === "signup" ? api.signup : api.login;
      const { ok, body } = await fn(payload);
      if (!ok) {
        errEl.textContent = body.error || "Something went wrong.";
        errEl.classList.remove("hidden");
        return;
      }
      state.user = body.user;
      e.currentTarget.reset();
      showApp();
      state.selectedId = null;
      await refresh();
    } finally {
      submit.disabled = false;
      submit.textContent = original;
    }
  });

  document.getElementById("account-btn").addEventListener("click", (e) => {
    e.stopPropagation();
    document.getElementById("account-dropdown").classList.toggle("hidden");
  });
  document.addEventListener("click", () => {
    document.getElementById("account-dropdown")?.classList.add("hidden");
  });

  document.getElementById("logout-btn").addEventListener("click", async () => {
    await api.logout();
    state.user = null;
    state.tickets = [];
    state.selectedId = null;
    showAuth();
  });

  document.getElementById("open-account").addEventListener("click", async () => {
    document.getElementById("account-dropdown").classList.add("hidden");
    await openAccountModal();
  });

  document.querySelectorAll("[data-close-account]").forEach((el) => {
    el.addEventListener("click", () => document.getElementById("account-modal").classList.add("hidden"));
  });

  document.getElementById("acc-name-form").addEventListener("submit", async (e) => {
    e.preventDefault();
    const name = new FormData(e.currentTarget).get("name");
    const { ok, body } = await api.updateName(name);
    if (ok) {
      state.user = body.user;
      showApp();
      toast("Name updated");
      await openAccountModal();
    } else {
      accMsg(body.error || "Could not update", true);
    }
  });

  document.getElementById("acc-pw-form").addEventListener("submit", async (e) => {
    e.preventDefault();
    const fd = new FormData(e.currentTarget);
    const { ok, body } = await api.changePassword({
      current_password: fd.get("current_password"),
      new_password: fd.get("new_password"),
    });
    if (ok) {
      e.currentTarget.reset();
      accMsg("Password updated.", false);
      toast("Password updated");
    } else {
      accMsg(body.error || "Could not update password", true);
    }
  });
}

async function openAccountModal() {
  if (!state.user) return;
  const modal = document.getElementById("account-modal");
  document.getElementById("acc-avatar").textContent = (state.user.name || state.user.email).trim().charAt(0).toUpperCase();
  document.getElementById("acc-name").textContent = state.user.name;
  document.getElementById("acc-email").textContent = state.user.email;
  document.getElementById("acc-since").textContent = state.user.created_at
    ? `Member since ${new Date(state.user.created_at).toLocaleDateString()}`
    : "";
  document.querySelector('#acc-name-form input[name="name"]').value = state.user.name;

  const stats = await api.stats();
  document.getElementById("acc-stats").innerHTML = [
    { label: "Total", value: stats.total },
    { label: "Open", value: stats.open },
    { label: "Triaged", value: stats.analyzed },
    { label: "Resolved", value: stats.resolved },
  ].map((c) => `
    <div class="rounded-lg bg-slate-50 border border-slate-100 px-3 py-2">
      <div class="text-[10px] uppercase tracking-wide text-slate-500">${c.label}</div>
      <div class="text-lg font-semibold tracking-tight">${c.value}</div>
    </div>`).join("");

  modal.classList.remove("hidden");
}

function accMsg(text, isError) {
  const el = document.getElementById("acc-msg");
  el.textContent = text;
  el.className = "text-xs " + (isError ? "text-rose-700" : "text-emerald-700");
  el.classList.remove("hidden");
}

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

  document.getElementById("seed-btn").addEventListener("click", async () => {
    const res = await api.seed();
    if (res.inserted) {
      toast(`Loaded ${res.inserted} demo tickets`);
    } else {
      toast("Already populated — clear first to reseed");
    }
    await refresh();
  });

  document.addEventListener("keydown", (e) => {
    const tag = (e.target && e.target.tagName) || "";
    if (["INPUT", "TEXTAREA", "SELECT"].includes(tag) || e.target?.isContentEditable) return;
    if (e.metaKey || e.ctrlKey || e.altKey) return;

    if (e.key === "ArrowDown" || e.key === "ArrowRight" || e.key === "j" || e.key === "J") {
      e.preventDefault();
      goRelative(1);
    } else if (e.key === "ArrowUp" || e.key === "ArrowLeft" || e.key === "k" || e.key === "K") {
      e.preventDefault();
      goRelative(-1);
    } else if (e.key === "g" || e.key === "G") {
      const btn = document.getElementById("generate-btn");
      if (btn && !btn.disabled) {
        e.preventDefault();
        btn.click();
      }
    }
  });
}

// ---------------------------------------------------------------------------
// Render
// ---------------------------------------------------------------------------

async function refresh() {
  const [tickets, stats] = await Promise.all([api.list(), api.stats()]);
  if (tickets && tickets.error === "authentication required") {
    state.user = null;
    showAuth();
    return;
  }
  state.tickets = Array.isArray(tickets) ? tickets : [];
  renderStats(stats);
  renderList(state.tickets);
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
    li.addEventListener("click", () => selectTicket(li.dataset.id));
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

  const idx = state.tickets.findIndex((x) => x.id === t.id);
  const total = state.tickets.length;
  const hasPrev = idx > 0;
  const hasNext = idx >= 0 && idx < total - 1;

  detail.innerHTML = `
    <div class="p-6 fade-in">
      <div class="mb-4 flex items-center justify-between gap-2 rounded-lg border border-slate-200 bg-slate-50 px-3 py-2">
        <button id="prev-btn" ${hasPrev ? "" : "disabled"}
          class="inline-flex items-center gap-1 rounded-md px-2 py-1 text-xs font-medium text-slate-700 hover:bg-white disabled:opacity-40 disabled:cursor-not-allowed">
          <span aria-hidden="true">←</span> Previous
        </button>
        <div class="text-xs text-slate-500">
          Ticket <span class="font-semibold text-slate-700">${idx + 1}</span> of <span class="font-semibold text-slate-700">${total}</span>
          <span class="hidden sm:inline ml-2 text-slate-400">· ← / → or J / K</span>
        </div>
        <button id="next-btn" ${hasNext ? "" : "disabled"}
          class="inline-flex items-center gap-1 rounded-md px-2 py-1 text-xs font-medium text-slate-700 hover:bg-white disabled:opacity-40 disabled:cursor-not-allowed">
          Next <span aria-hidden="true">→</span>
        </button>
      </div>
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

  const prevBtn = document.getElementById("prev-btn");
  const nextBtn = document.getElementById("next-btn");
  if (prevBtn) prevBtn.addEventListener("click", () => goRelative(-1));
  if (nextBtn) nextBtn.addEventListener("click", () => goRelative(1));
}

function goRelative(delta) {
  if (!state.tickets.length) return;
  const idx = state.tickets.findIndex((x) => x.id === state.selectedId);
  if (idx === -1) return;
  const nextIdx = idx + delta;
  if (nextIdx < 0 || nextIdx >= state.tickets.length) return;
  selectTicket(state.tickets[nextIdx].id);
}

function selectTicket(id) {
  const t = state.tickets.find((x) => x.id === id);
  if (!t) return;
  state.selectedId = id;
  renderDetail(t);
  renderList(state.tickets);
  const sel = document.querySelector(`#ticket-list li[data-id="${id}"]`);
  if (sel) sel.scrollIntoView({ block: "nearest", behavior: "smooth" });
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
