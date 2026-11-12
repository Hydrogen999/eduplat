// frontend/js/dashboard.js
requireAuth();
renderNav();

(async () => {
  const user = auth.getUser();
  document.getElementById("greeting").textContent = `Welcome, ${user.full_name.split(" ")[0]} 👋`;

  try {
    const history = await apiCall("/exams/history");
    const list = document.getElementById("recent-results");
    if (history.length === 0) {
      document.getElementById("no-results").classList.remove("hidden");
    } else {
      history.slice(0, 5).forEach((r) => {
        const li = document.createElement("li");
        li.className = "flex items-center justify-between rounded-lg bg-slate-50 p-3 text-sm";
        li.innerHTML = `
          <span class="font-medium">${escapeHtml(r.exam_category.toUpperCase())}</span>
          <span class="text-ink-500">${r.correct}/${r.total} · ${r.score_percent}%</span>
        `;
        list.appendChild(li);
      });
    }
  } catch (e) { console.error(e); }
})();