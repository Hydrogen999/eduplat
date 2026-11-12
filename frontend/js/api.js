const API_BASE = "/api/v1";

const auth = {
  getAccess:   () => localStorage.getItem("access_token"),
  setAccess:   (t) => localStorage.setItem("access_token", t),
  clear:       () => { localStorage.removeItem("access_token"); localStorage.removeItem("user"); },
  isLoggedIn:  () => !!localStorage.getItem("access_token"),
  getUser:     () => JSON.parse(localStorage.getItem("user") || "null"),
  setUser:     (u) => localStorage.setItem("user", JSON.stringify(u)),
};

async function apiCall(path, opts = {}) {
  const headers = { "Content-Type": "application/json", ...(opts.headers || {}) };
  const token = auth.getAccess();
  if (token) headers.Authorization = `Bearer ${token}`;

  let res = await fetch(API_BASE + path, { ...opts, headers, credentials: "include" });

  if (res.status === 401 && !opts._retry) {
    const r = await fetch(API_BASE + "/auth/refresh", { method: "POST", credentials: "include" });
    if (r.ok) {
      const data = await r.json();
      auth.setAccess(data.access_token);
      headers.Authorization = `Bearer ${data.access_token}`;
      res = await fetch(API_BASE + path, { ...opts, headers, credentials: "include", _retry: true });
    } else {
      auth.clear();
      window.location.href = "/login.html";
      throw new Error("Session expired");
    }
  }

  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: "Request failed" }));
    throw new Error(err.detail || err.message || "Request failed");
  }
  return res.json();
}

function requireAuth() {
  if (!auth.isLoggedIn()) window.location.href = "/login.html";
}

function toast(msg, kind = "info") {
  const colors = { info: "bg-ink-900", success: "bg-brand-600", error: "bg-red-600" };
  const el = document.createElement("div");
  el.className = `fixed top-4 right-4 z-50 rounded-lg px-4 py-3 text-sm font-medium text-white shadow-lg ${colors[kind] || colors.info}`;
  el.textContent = msg;
  document.body.appendChild(el);
  setTimeout(() => el.remove(), 3500);
}

function escapeHtml(str) {
  const div = document.createElement("div");
  div.textContent = String(str ?? "");
  return div.innerHTML;
}

function formatNaira(kobo) {
  return "₦" + (kobo / 100).toLocaleString("en-NG");
}

function renderNav() {
  const slot = document.getElementById("site-nav");
  if (!slot) return;
  const user = auth.getUser();
  slot.innerHTML = user ? `
    <header class="sticky top-0 z-30 border-b border-slate-100 bg-white/80 backdrop-blur">
      <div class="mx-auto flex max-w-6xl items-center justify-between px-4 py-3">
        <a href="/dashboard.html" class="flex items-center gap-2">
          <div class="grid h-8 w-8 place-items-center rounded-lg bg-green-600 font-bold text-white">E</div>
          <span class="font-bold">EduPlat<span class="text-green-600">NG</span></span>
        </a>
        <div class="flex items-center gap-2">
          <span class="hidden text-sm text-gray-700 sm:inline">${escapeHtml(user.full_name)}</span>
          <button onclick="logout()" class="rounded-lg border px-3 py-1.5 text-sm">Logout</button>
        </div>
      </div>
    </header>` : "";
}

async function logout() {
  try { await apiCall("/auth/logout", { method: "POST" }); } catch {}
  auth.clear();
  window.location.href = "/";
}