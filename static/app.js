/* SkillMatrix v2 - interfaz web sobre la API /api/v1 */
"use strict";

const LEVEL_NAMES = ["No lo conoce", "Nociones básicas", "Principiante", "Intermedio", "Avanzado", "Experto"];
const LEVEL_COLORS = ["#F2F4F7", "#DCEEF3", "#B3DCE7", "#6FB3C9", "#2F7F9E", "#17324D"];
const ROLE_NAMES = { admin: "RRHH / Administrador", manager: "Manager", lector: "Solo lectura" };
const state = { me: null, charts: [] };
const $ = (s, el = document) => el.querySelector(s);
const $$ = (s, el = document) => [...el.querySelectorAll(s)];
const esc = (v) => String(v ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const canEdit = () => ["admin", "manager"].includes(state.me?.role);
const isAdmin = () => state.me?.role === "admin";
const fmt = (n, d = 1) => Number(n || 0).toLocaleString("es-ES", { minimumFractionDigits: d, maximumFractionDigits: d });
const fdate = (iso) => (iso ? new Date(iso).toLocaleDateString("es-ES", { day: "2-digit", month: "2-digit", year: "numeric" }) : "");
const fdatetime = (iso) => (iso ? new Date(iso).toLocaleString("es-ES", { dateStyle: "short", timeStyle: "short" }) : "");
const rtf = new Intl.RelativeTimeFormat("es", { numeric: "auto" });
function ago(iso) {
  if (!iso) return "";
  const days = Math.round((new Date(iso) - Date.now()) / 86400000);
  if (Math.abs(days) < 1) return "hoy";
  if (Math.abs(days) < 31) return rtf.format(days, "day");
  if (Math.abs(days) < 365) return rtf.format(Math.round(days / 30.4), "month");
  const m = Math.round(days / 30.4);
  return Math.abs(m) < 24 ? rtf.format(m, "month") : rtf.format(Math.round(days / 365), "year");
}

/* ------------------------------------------------------------------ API */
async function api(method, url, body) {
  const opts = { method, headers: { "X-Requested-With": "SkillMatrix" } };
  if (body instanceof FormData) opts.body = body;
  else if (body !== undefined) { opts.headers["Content-Type"] = "application/json"; opts.body = JSON.stringify(body); }
  const res = await fetch("/api/v1" + url, opts);
  let data = null;
  if (res.status !== 204) { try { data = await res.json(); } catch { /* sin cuerpo */ } }
  if (res.status === 401 && url !== "/auth/login") { showLogin(); throw new Error("Tu sesión ha caducado. Vuelve a iniciar sesión."); }
  if (!res.ok) {
    const extra = data?.errors?.length ? "\n" + data.errors.slice(0, 5).map((e) => `Fila ${e.index + 1}: ${e.error}`).join("\n") : "";
    throw new Error((data?.error || `Error ${res.status}`) + extra);
  }
  return data;
}

function toast(msg, err = false) {
  const t = document.createElement("div");
  t.className = "toast" + (err ? " err" : "");
  t.textContent = msg;
  document.body.appendChild(t);
  setTimeout(() => t.remove(), err ? 5000 : 2200);
}

/* Modal de formulario genérico */
function formModal({ title, fields, submit = "Guardar", onSubmit, danger, cancel = "Cancelar" }) {
  return new Promise((resolve) => {
    const bg = document.createElement("div");
    bg.className = "modal-bg";
    bg.innerHTML = `<form class="modal" role="dialog" aria-modal="true" aria-label="${esc(title)}">
      <h2>${esc(title)}</h2>
      ${fields.map((f) => f.type === "info" ? `<div class="muted">${f.html}</div>` : `
        <label class="field">${esc(f.label)}
          ${f.type === "select"
            ? `<select name="${f.name}">${f.options.map((o) => `<option value="${esc(o.value)}" ${String(o.value) === String(f.value ?? "") ? "selected" : ""}>${esc(o.label)}</option>`).join("")}</select>`
            : `<input name="${f.name}" type="${f.type || "text"}" value="${esc(f.value ?? "")}" ${f.required ? "required" : ""} ${f.min != null ? `min="${f.min}"` : ""} ${f.placeholder ? `placeholder="${esc(f.placeholder)}"` : ""} ${f.list ? `list="dl-${f.name}"` : ""}>
               ${f.list ? `<datalist id="dl-${f.name}">${f.list.map((o) => `<option value="${esc(o)}">`).join("")}</datalist>` : ""}`}
        </label>`).join("")}
      <div class="error" style="white-space:pre-line"></div>
      <div class="foot">${cancel ? `<button type="button" class="btn" data-x>${esc(cancel)}</button>` : ""}
        ${submit ? `<button class="btn ${danger ? "danger" : "primary"}">${esc(submit)}</button>` : ""}</div>
    </form>`;
    const close = (v) => { bg.remove(); resolve(v); };
    bg.addEventListener("click", (e) => { if (e.target === bg || e.target.hasAttribute("data-x")) close(null); });
    bg.addEventListener("keydown", (e) => { if (e.key === "Escape") close(null); });
    $("form", bg).addEventListener("submit", async (e) => {
      e.preventDefault();
      const vals = Object.fromEntries(new FormData(e.target).entries());
      try { const r = await onSubmit(vals); close(r ?? true); }
      catch (err) { $(".error", bg).textContent = err.message; }
    });
    document.body.appendChild(bg);
    ($("input,select", bg) || $(".foot button:last-child", bg))?.focus();
  });
}
const confirmModal = (title, text, action = "Eliminar") =>
  formModal({ title, fields: [{ type: "info", html: esc(text) }], submit: action, danger: action === "Eliminar", onSubmit: () => true });

/* ---------------------------------------------------------------- login */
function showLogin() {
  $("#app").classList.add("hidden");
  $("#login").classList.remove("hidden");
  const grid = $("#login-grid");
  if (!grid.children.length) {
    const pattern = [0, 1, 3, 5, 4, 2, 1, 0, 2, 4, 5, 3];
    for (let r = 0; r < 6; r++) for (let c = 0; c < 12; c++) {
      const s = document.createElement("span");
      const lv = pattern[(c + r * 5) % 12];
      s.style.background = lv === 0 ? "#22455F" : LEVEL_COLORS[lv];
      s.style.opacity = lv === 5 ? ".35" : "1";
      grid.appendChild(s);
    }
  }
  $("#login-form input").focus();
}

$("#login-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  $("#login-error").textContent = "";
  try {
    const f = new FormData(e.target);
    await api("POST", "/auth/login", { username: f.get("username"), password: f.get("password") });
    state.me = await api("GET", "/auth/me");
    e.target.reset();
    startApp();
  } catch (err) { $("#login-error").textContent = err.message; }
});

$("#btn-logout").addEventListener("click", async () => { await api("POST", "/auth/logout"); state.me = null; showLogin(); });
$("#btn-password").addEventListener("click", () => formModal({
  title: "Cambiar contraseña",
  fields: [{ name: "current", label: "Contraseña actual", type: "password", required: true },
           { name: "new", label: "Nueva contraseña (mínimo 8 caracteres)", type: "password", required: true }],
  submit: "Cambiar contraseña",
  onSubmit: (v) => api("PUT", "/auth/password", v).then(() => toast("Contraseña cambiada")),
}));

/* ------------------------------------------------------------ navegación */
const ICONS = {
  dashboard: '<path d="M3 13h8V3H3zM13 21h8V11h-8zM3 21h8v-6H3zM13 3v6h8V3z"/>',
  matriz: '<rect x="3" y="3" width="7" height="7" rx="1"/><rect x="14" y="3" width="7" height="7" rx="1"/><rect x="3" y="14" width="7" height="7" rx="1"/><rect x="14" y="14" width="7" height="7" rx="1"/>',
  puestos: '<path d="M4 20V10M10 20V4M16 20v-8M22 20H2"/>',
  empleados: '<circle cx="9" cy="8" r="4"/><path d="M2 21c0-4 3-6 7-6s7 2 7 6M17 11a3 3 0 1 0 0-6M22 21c0-3-2-5-5-5"/>',
  habilidades: '<path d="M12 2l3 6 6 1-4.5 4.5L18 20l-6-3-6 3 1.5-6.5L3 9l6-1z"/>',
  datos: '<path d="M12 3v12M7 10l5 5 5-5M4 21h16"/>',
  admin: '<circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.7 1.7 0 0 0 .3 1.8l.1.1a2 2 0 1 1-2.8 2.8l-.1-.1a1.7 1.7 0 0 0-1.8-.3 1.7 1.7 0 0 0-1 1.5V21a2 2 0 0 1-4 0v-.1a1.7 1.7 0 0 0-1.1-1.5 1.7 1.7 0 0 0-1.8.3l-.1.1a2 2 0 1 1-2.8-2.8l.1-.1a1.7 1.7 0 0 0 .3-1.8 1.7 1.7 0 0 0-1.5-1H3a2 2 0 0 1 0-4h.1a1.7 1.7 0 0 0 1.5-1.1 1.7 1.7 0 0 0-.3-1.8l-.1-.1a2 2 0 1 1 2.8-2.8l.1.1a1.7 1.7 0 0 0 1.8.3H9a1.7 1.7 0 0 0 1-1.5V3a2 2 0 0 1 4 0v.1a1.7 1.7 0 0 0 1 1.5 1.7 1.7 0 0 0 1.8-.3l.1-.1a2 2 0 1 1 2.8 2.8l-.1.1a1.7 1.7 0 0 0-.3 1.8V9a1.7 1.7 0 0 0 1.5 1H21a2 2 0 0 1 0 4h-.1a1.7 1.7 0 0 0-1.5 1z"/>',
};
const ROUTES = {
  dashboard: { label: "Resumen", render: viewDashboard },
  matriz: { label: "Matriz", render: viewMatrix },
  puestos: { label: "Puestos y brechas", render: viewRoles },
  empleados: { label: "Empleados", render: viewEmployees },
  habilidades: { label: "Habilidades", render: viewSkills },
  datos: { label: "Importar / exportar", render: viewData },
  admin: { label: "Administración", render: viewAdmin, admin: true },
};

function renderNav(active) {
  $("#nav").innerHTML = Object.entries(ROUTES).filter(([, r]) => !r.admin || isAdmin()).map(([k, r]) =>
    `<a href="#/${k}" class="${k === active ? "active" : ""}"><svg viewBox="0 0 24 24">${ICONS[k]}</svg><span>${r.label}</span></a>`).join("");
}

async function router() {
  if (!state.me) return;
  const [, key = "dashboard", param] = location.hash.split("/");
  const route = key === "empleado" ? { render: viewEmployee } : ROUTES[key] || ROUTES.dashboard;
  if (route.admin && !isAdmin()) { location.hash = "#/dashboard"; return; }
  renderNav(key === "empleado" ? "empleados" : ROUTES[key] ? key : "dashboard");
  state.charts.forEach((c) => c.destroy());
  state.charts = [];
  closePicker();
  const view = $("#view");
  const fresh = view.cloneNode(false);          // descarta listeners de la vista anterior
  view.replaceWith(fresh);
  fresh.innerHTML = '<p class="muted">Cargando…</p>';
  try { await route.render(fresh, param ? decodeURIComponent(param) : param); }
  catch (err) { fresh.innerHTML = `<div class="panel empty" style="white-space:pre-line">${esc(err.message)}</div>`; }
}
window.addEventListener("hashchange", router);

function startApp() {
  $("#login").classList.add("hidden");
  $("#app").classList.remove("hidden");
  $("#user-name").textContent = state.me.full_name || state.me.username;
  $("#user-role").textContent = ROLE_NAMES[state.me.role];
  router();
}

const head = (title, sub, actions = "") =>
  `<div class="page-head"><div><h1>${esc(title)}</h1>${sub ? `<p>${sub}</p>` : ""}</div><div class="actions">${actions}</div></div>`;
const lvl = (n, stale = false, title = "") => n == null
  ? `<span class="lvl na" title="Sin evaluar">–</span>`
  : `<span class="lvl l${n}${stale ? " stale" : ""}" title="${esc(title || `${n} · ${LEVEL_NAMES[n]}`)}">${n}</span>`;
const legend = (months) => `<div class="legend">${LEVEL_NAMES.map((n, i) => `<span><i style="background:${LEVEL_COLORS[i]}"></i>${i} ${n}</span>`).join("")}
  <span><i class="na"></i>Sin evaluar</span>
  <span><i class="hatch"></i>Evaluado hace más de ${months} meses</span>
  <span><i class="dot"></i>Por debajo de lo que pide su puesto</span></div>`;

/* --------------------------------------------------------------- resumen */
async function viewDashboard(view) {
  const d = await api("GET", "/dashboard");
  const t = d.totals;
  const risky = [...d.per_skill].sort((a, b) => a.experts - b.experts || a.avg - b.avg).slice(0, 6);
  view.innerHTML = head("Resumen", "Estado de las habilidades de todo el equipo.") + `
    <div class="summary">
      <div><b>${t.employees}</b><span>empleados</span></div>
      <div><b>${t.skills}</b><span>habilidades registradas</span></div>
      <div><b>${fmt(t.avg_known)}</b><span>nivel medio en lo que conocen</span></div>
      <div><b class="${t.stale ? "warn" : ""}">${t.stale}</b><span>de ${t.assessments} evaluaciones tienen más de ${d.stale_months} meses</span></div>
    </div>
    <div class="grid g-3-1">
      <div class="panel"><h2>Nivel medio por habilidad</h2><p class="sub">Media de toda la plantilla; sin evaluar cuenta como 0.</p>
        <div class="chart-box" style="height:${Math.max(260, d.per_skill.length * 26)}px"><canvas id="c-skills"></canvas></div></div>
      <div class="grid" style="align-content:start">
        <div class="panel"><h2>Pendientes de revisar</h2><p class="sub">Personas con evaluaciones de hace más de ${d.stale_months} meses o sin evaluar.</p>
          ${d.needs_review.length ? `<table class="list">${d.needs_review.map((r) => `<tr>
            <td><a href="#/empleado/${r.id}">${esc(r.name)}</a><br><small class="muted">${esc(r.job_role || "Sin puesto")}</small></td>
            <td class="num">${r.assessed ? `<span class="stale-text">${r.stale} de ${r.assessed}</span><br><small class="date" title="${fdatetime(r.last_evaluated_at)}">última ${ago(r.last_evaluated_at)}</small>`
              : '<span class="tag pill-gap">Sin evaluar</span>'}</td></tr>`).join("")}</table>`
            : '<p class="muted">Todas las evaluaciones están al día.</p>'}
        </div>
        <div class="panel"><h2>Cumplimiento por puesto</h2><p class="sub">Media de cobertura de los requisitos del puesto.</p>
          ${d.per_role.length ? `<table class="list">${d.per_role.map((r) => `<tr>
            <td><a href="#/puestos/${r.id}">${esc(r.name)}</a><br><small class="muted">${r.employees} empleado(s)</small></td>
            <td style="width:40%">${r.coverage == null ? '<span class="muted">Sin datos</span>' : `<div class="bar"><i style="width:${r.coverage}%"></i></div>`}</td>
            <td class="num">${r.coverage == null ? "" : r.coverage + "%"}</td></tr>`).join("")}</table>`
            : '<p class="muted">Define puestos en «Puestos y brechas» para ver el cumplimiento.</p>'}
        </div>
      </div>
    </div>
    <div class="grid g-2" style="margin-top:16px">
      <div class="panel"><h2>Habilidades con menos expertos</h2><p class="sub">Conocimiento concentrado en pocas personas: candidatas a formación.</p>
        <table class="list"><tr><th>Habilidad</th><th class="num">Nivel 4-5</th><th class="num">La conocen</th><th class="num">Media</th></tr>
        ${risky.map((s) => `<tr><td>${esc(s.name)} <span class="tag">${esc(s.category)}</span></td>
          <td class="num">${s.experts === 0 ? '<span class="tag pill-gap">Nadie</span>' : s.experts}</td>
          <td class="num">${s.known}</td><td class="num">${fmt(s.avg)}</td></tr>`).join("")}</table>
        <h2 style="margin-top:20px">Distribución de niveles</h2><p class="sub">Evaluaciones registradas por nivel.</p>
        <div class="chart-box" style="height:200px"><canvas id="c-dist"></canvas></div></div>
      <div class="panel"><h2>Últimos cambios</h2><p class="sub">Cambios de nivel desde la web, la API o importaciones.</p>
        ${d.recent.length ? `<ul class="feed">${d.recent.map((r) => `<li>${lvl(r.old_level)} → ${lvl(r.new_level)}
          <div><a href="#/empleado/${r.employee_id}"><b>${esc(r.employee)}</b></a> · ${esc(r.skill)}<small>${esc(r.changed_by)}, ${fdatetime(r.changed_at)}</small></div></li>`).join("")}</ul>`
          : '<p class="muted">Todavía no hay cambios. Edita un nivel en la matriz y aparecerá aquí.</p>'}</div>
    </div>`;

  const base = { responsive: true, maintainAspectRatio: false, plugins: { legend: { display: false } } };
  Chart.defaults.font.family = getComputedStyle(document.body).fontFamily;
  Chart.defaults.color = "#5B6B7C";
  const ps = [...d.per_skill].sort((a, b) => b.avg - a.avg);
  state.charts.push(new Chart($("#c-skills"), {
    type: "bar",
    data: { labels: ps.map((s) => s.name), datasets: [{ data: ps.map((s) => s.avg), backgroundColor: ps.map((s) => LEVEL_COLORS[Math.max(1, Math.round(s.avg))]), borderColor: "#9FB3C5", borderWidth: 1, borderRadius: 3 }] },
    options: { ...base, indexAxis: "y", scales: { x: { min: 0, max: 5, ticks: { stepSize: 1 } }, y: { grid: { display: false } } } },
  }));
  state.charts.push(new Chart($("#c-dist"), {
    type: "bar",
    data: { labels: LEVEL_NAMES.map((n, i) => i), datasets: [{ data: Object.values(d.distribution), backgroundColor: LEVEL_COLORS, borderColor: "#C9D2DB", borderWidth: 1, borderRadius: 3 }] },
    options: { ...base, plugins: { legend: { display: false }, tooltip: { callbacks: { title: (i) => `${i[0].label} · ${LEVEL_NAMES[i[0].dataIndex]}` } } }, scales: { x: { grid: { display: false } } } },
  }));
}

/* ---------------------------------------------------------------- matriz */
const matrixFilters = { q: "", dept: "", cat: "", role: "", marks: true, onlyStale: false };
const reqMap = (roles) => Object.fromEntries(roles.map((r) => [r.id, Object.fromEntries(r.requirements.map((x) => [x.skill_id, x.required_level]))]));

async function viewMatrix(view) {
  const m = await api("GET", "/matrix");
  const reqByRole = reqMap(m.job_roles);
  const depts = [...new Set(m.employees.map((e) => e.department).filter(Boolean))].sort();
  const cats = [...new Set(m.skills.map((s) => s.category))].sort();
  const opt = (arr, cur, all) => `<option value="">${all}</option>` + arr.map((v) => `<option value="${esc(v.value ?? v)}" ${String(v.value ?? v) === cur ? "selected" : ""}>${esc(v.label ?? v)}</option>`).join("");

  view.innerHTML = head("Matriz de habilidades",
    canEdit() ? "Haz clic en una celda para evaluar, o selecciónala y pulsa 0-5. Pulsar el mismo nivel confirma que sigue vigente." : "Consulta el nivel de cada persona. Solo managers y RRHH pueden editar.",
    `<a class="btn" href="/api/v1/export?format=xlsx">Exportar a Excel</a>`) + `
    <div class="filters">
      <input class="input" id="f-q" type="search" placeholder="Buscar empleado o habilidad" value="${esc(matrixFilters.q)}">
      <select class="input" id="f-dept">${opt(depts, matrixFilters.dept, "Todos los departamentos")}</select>
      <select class="input" id="f-cat">${opt(cats, matrixFilters.cat, "Todas las categorías")}</select>
      <select class="input" id="f-role">${opt(m.job_roles.map((r) => ({ value: String(r.id), label: r.name })), matrixFilters.role, "Todos los puestos")}</select>
      <label class="check"><input type="checkbox" id="f-stale" ${matrixFilters.onlyStale ? "checked" : ""}> Solo personas con evaluaciones antiguas</label>
      <label class="check"><input type="checkbox" id="f-marks" ${matrixFilters.marks ? "checked" : ""}> Marcar brechas y antigüedad</label>
    </div>
    <div class="matrix-wrap" id="mwrap"></div>
    ${legend(m.stale_months)}`;

  const cellOf = (e, s) => m.assessments[`${e}-${s}`];
  const draw = () => {
    const q = matrixFilters.q.toLowerCase();
    let skills = m.skills.filter((s) => !matrixFilters.cat || s.category === matrixFilters.cat);
    const skillMatch = q && skills.some((s) => s.name.toLowerCase().includes(q));
    if (skillMatch) skills = skills.filter((s) => s.name.toLowerCase().includes(q));
    const emps = m.employees.filter((e) =>
      (!matrixFilters.dept || e.department === matrixFilters.dept) &&
      (!matrixFilters.role || String(e.job_role_id) === matrixFilters.role) &&
      (!matrixFilters.onlyStale || m.skills.some((s) => cellOf(e.id, s.id)?.stale)) &&
      (!q || skillMatch || [e.name, e.email, e.external_id].join(" ").toLowerCase().includes(q)));
    if (!emps.length || !skills.length) {
      $("#mwrap").innerHTML = `<div class="empty">${!m.employees.length ? 'Aún no hay empleados. Añádelos en <a href="#/empleados">Empleados</a> o impórtalos desde <a href="#/datos">Excel</a>.' : "Ningún resultado con estos filtros."}</div>`;
      return;
    }
    const groups = [];
    skills.forEach((s) => { const g = groups.at(-1); g && g.cat === s.category ? g.n++ : groups.push({ cat: s.category, n: 1 }); });
    $("#mwrap").innerHTML = `<table class="matrix"><thead>
      <tr class="cats"><th class="emp"></th>${groups.map((g) => `<th colspan="${g.n}" title="${esc(g.cat)}"><div style="width:${g.n * 45 - 8}px">${esc(g.cat)}</div></th>`).join("")}</tr>
      <tr class="skills"><th class="emp"></th>${skills.map((s) => `<th title="${esc(s.description || s.name)}"><div class="sk-head">${esc(s.name)}</div></th>`).join("")}</tr>
      </thead><tbody>${emps.map((e) => `<tr><td class="emp"><a href="#/empleado/${e.id}" style="color:inherit;text-decoration:none"><span class="n">${esc(e.name)}</span></a>
        <span class="r">${esc([e.job_role, e.department].filter(Boolean).join(" · ") || "Sin puesto")}</span></td>
        ${skills.map((s) => cellHtml(e, s)).join("")}</tr>`).join("")}</tbody></table>`;
  };
  const cellHtml = (e, s) => {
    const a = cellOf(e.id, s.id);
    const v = a ? a.level : null;
    const req = reqByRole[e.job_role_id]?.[s.id];
    const below = matrixFilters.marks && req && (v ?? 0) < req;
    const stale = matrixFilters.marks && a?.stale;
    const tip = `${e.name} · ${s.name}: ` + (a ? `${v} ${LEVEL_NAMES[v]}. Evaluado el ${fdate(a.evaluated_at)}${a.stale ? " (desactualizado)" : ""}` : "sin evaluar") +
      (req ? `. El puesto pide ${req}` : "");
    const cls = a ? `l${v}` : "na";
    return `<td class="cell ${cls}${canEdit() ? " editable" : ""}${below ? " below" : ""}${stale ? " stale" : ""}" data-e="${e.id}" data-s="${s.id}" ${canEdit() ? 'tabindex="0"' : ""} title="${esc(tip)}">${a ? v : ""}</td>`;
  };
  const refreshCell = (td, flash = true) => {
    const e = m.employees.find((x) => x.id == td.dataset.e), s = m.skills.find((x) => x.id == td.dataset.s);
    const tmp = document.createElement("tr");
    tmp.innerHTML = cellHtml(e, s);
    const nt = tmp.firstElementChild;
    if (flash) nt.classList.add("saved");
    td.replaceWith(nt);
    return nt;
  };
  const save = async (td, level) => {
    const key = `${td.dataset.e}-${td.dataset.s}`;
    const prev = m.assessments[key];
    try {
      if (level === null) {
        if (!prev) return;
        await api("DELETE", `/assessments/${td.dataset.e}/${td.dataset.s}`);
        delete m.assessments[key];
      } else {
        const r = await api("PUT", `/assessments/${td.dataset.e}/${td.dataset.s}`, { level });
        m.assessments[key] = { level: r.level, evaluated_at: r.evaluated_at, evaluated_by: r.evaluated_by, stale: r.stale };
        if (r.result === "reviewed") toast("Nivel confirmado con fecha de hoy");
      }
      refreshCell(td).focus();
    } catch (err) { toast(err.message, true); }
  };

  draw();
  const bind = (id, key, ev = "change") => $(id).addEventListener(ev, (e) => { matrixFilters[key] = e.target.type === "checkbox" ? e.target.checked : e.target.value; draw(); });
  bind("#f-q", "q", "input"); bind("#f-dept", "dept"); bind("#f-cat", "cat"); bind("#f-role", "role"); bind("#f-marks", "marks"); bind("#f-stale", "onlyStale");

  if (!canEdit()) return;
  const wrap = $("#mwrap");
  wrap.addEventListener("click", (e) => {
    const td = e.target.closest("td.cell.editable");
    if (!td) return;
    const emp = m.employees.find((x) => x.id == td.dataset.e), sk = m.skills.find((x) => x.id == td.dataset.s);
    openPicker(td, { title: emp.name, sub: sk.name, assessment: cellOf(emp.id, sk.id),
      required: reqByRole[emp.job_role_id]?.[sk.id], onPick: (lv) => save(td, lv) });
  });
  wrap.addEventListener("keydown", (e) => {
    const td = e.target.closest("td.cell.editable");
    if (!td) return;
    if (/^[0-5]$/.test(e.key)) { e.preventDefault(); closePicker(); save(td, +e.key); return; }
    if (e.key === "Delete" || e.key === "Backspace") { e.preventDefault(); save(td, null); return; }
    if (e.key === "Enter" || e.key === " ") { e.preventDefault(); td.click(); return; }
    const moves = { ArrowLeft: [0, -1], ArrowRight: [0, 1], ArrowUp: [-1, 0], ArrowDown: [1, 0] };
    if (moves[e.key]) {
      e.preventDefault();
      const tr = td.parentElement, col = [...tr.children].indexOf(td);
      const [dr, dc] = moves[e.key];
      const row = dr ? (dr < 0 ? tr.previousElementSibling : tr.nextElementSibling) : tr;
      const next = row?.children[col + dc];
      if (next?.classList.contains("cell")) next.focus();
    }
  });
}

/* Selector flotante de nivel */
let pickerEl = null;
function closePicker() { pickerEl?.remove(); pickerEl = null; }
function openPicker(anchor, { title, sub, assessment: a, required, onPick }) {
  closePicker();
  const current = a ? a.level : null;
  pickerEl = document.createElement("div");
  pickerEl.className = "picker";
  pickerEl.innerHTML = `<div class="ph"><b>${esc(title)}</b>${esc(sub)}</div>
    <div class="meta ${a?.stale ? "stale-text" : ""}">${a ? `Evaluado el ${fdate(a.evaluated_at)} (${ago(a.evaluated_at)}) por ${esc(a.evaluated_by || "—")}${a.stale ? ". Conviene revisarlo." : ""}` : "Sin evaluar"}</div>
    ${LEVEL_NAMES.map((n, i) => `<button data-l="${i}" class="${i === current ? "cur" : ""}"><i style="background:${LEVEL_COLORS[i]};color:${i >= 4 ? "#fff" : "#17324D"}">${i}</i>${n}</button>`).join("")}
    ${required ? `<div class="req">Su puesto requiere nivel ${required} (${LEVEL_NAMES[required]})</div>` : ""}
    ${a ? `<div class="acts"><button data-l="${current}">Confirmar nivel ${current} con fecha de hoy</button><button class="rm" data-l="">Quitar evaluación</button></div>` : ""}`;
  document.body.appendChild(pickerEl);
  const r = anchor.getBoundingClientRect(), p = pickerEl.getBoundingClientRect();
  pickerEl.style.left = Math.min(window.innerWidth - p.width - 8, Math.max(8, r.left)) + "px";
  pickerEl.style.top = (r.bottom + p.height + 8 > window.innerHeight ? Math.max(8, r.top - p.height - 6) : r.bottom + 6) + "px";
  pickerEl.addEventListener("click", (e) => {
    const b = e.target.closest("button[data-l]");
    if (b) { const lv = b.dataset.l === "" ? null : +b.dataset.l; closePicker(); onPick(lv); }
  });
  $(`button[data-l="${current ?? 0}"]`, pickerEl).focus();
}
document.addEventListener("mousedown", (e) => { if (pickerEl && !pickerEl.contains(e.target) && !e.target.closest("td.cell")) closePicker(); });
document.addEventListener("keydown", (e) => { if (e.key === "Escape") closePicker(); });
window.addEventListener("scroll", closePicker, true);

/* ------------------------------------------------------ puestos y brechas */
let gapScope = "role";
async function viewRoles(view, param) {
  const [{ items: roles }, { items: skills }] = await Promise.all([api("GET", "/job-roles"), api("GET", "/skills")]);
  const addBtn = canEdit() ? '<button class="btn primary" id="new-role">Nuevo puesto</button>' : "";
  view.innerHTML = head("Puestos y brechas", "Define el nivel que exige cada puesto y compáralo con el nivel real de las personas.", addBtn) +
    (roles.length ? `<div class="grid side-list"><div class="panel" style="padding:8px"><div class="role-list">
      ${roles.map((r) => `<button data-id="${r.id}"><span>${esc(r.name)}</span><span class="muted">${r.employees}</span></button>`).join("")}
      </div></div><div id="role-detail" class="grid"></div></div>`
      : `<div class="panel empty">Todavía no hay puestos. ${canEdit() ? "Crea el primero con «Nuevo puesto»." : ""}</div>`);

  $("#new-role")?.addEventListener("click", () => formModal({ title: "Nuevo puesto",
    fields: [{ name: "name", label: "Nombre del puesto", required: true, placeholder: "p. ej. Arquitecto de datos" }],
    submit: "Crear puesto", onSubmit: (v) => api("POST", "/job-roles", v) }).then((r) => { if (r) location.hash = `#/puestos/${r.id}`; }));
  if (!roles.length) return;

  const selected = roles.find((r) => String(r.id) === param) || roles[0];
  $$(".role-list button").forEach((b) => {
    b.classList.toggle("active", b.dataset.id == selected.id);
    b.addEventListener("click", () => { location.hash = `#/puestos/${b.dataset.id}`; });
  });

  const req = Object.fromEntries(selected.requirements.map((x) => [x.skill_id, x.required_level]));
  const skillName = Object.fromEntries(skills.map((s) => [s.id, s.name]));
  const detail = $("#role-detail");
  const cats = [...new Set(skills.map((s) => s.category))];
  detail.innerHTML = `
    <div class="panel">
      <div class="page-head" style="margin-bottom:10px"><div><h2 style="font-size:19px">${esc(selected.name)}</h2>
        <p class="sub" style="margin:0">Nivel mínimo requerido por habilidad. Deja en 0 las que el puesto no necesita.</p></div>
        ${canEdit() ? `<div class="actions"><button class="btn small" id="ren-role">Renombrar</button><button class="btn small danger" id="del-role">Eliminar</button></div>` : ""}</div>
      <div class="table-wrap"><table class="list">${cats.map((c) => `<tr><th colspan="2">${esc(c)}</th></tr>` +
        skills.filter((s) => s.category === c).map((s) => `<tr><td>${esc(s.name)}</td><td class="num"><div class="lvl-select" data-s="${s.id}">
          ${[0, 1, 2, 3, 4, 5].map((i) => `<button type="button" data-l="${i}" ${canEdit() ? "" : "disabled"} title="${LEVEL_NAMES[i]}">${i}</button>`).join("")}</div></td></tr>`).join("")).join("")}
      </table></div>
      ${canEdit() ? '<div class="actions" style="justify-content:flex-end;margin-top:12px"><button class="btn primary" id="save-req">Guardar requisitos</button></div>' : ""}
    </div>
    <div class="panel" id="gap-panel"></div>`;

  const paint = () => $$(".lvl-select", detail).forEach((g) => {
    const cur = +(req[g.dataset.s] || 0);
    $$("button", g).forEach((b) => {
      const on = +b.dataset.l === cur && cur > 0;
      b.classList.toggle("on", on);
      b.style.background = on ? LEVEL_COLORS[cur] : "";
      b.style.color = on && cur >= 4 ? "#fff" : "";
    });
  });
  paint();
  detail.addEventListener("click", (e) => {
    const b = e.target.closest(".lvl-select button");
    if (!b || b.disabled) return;
    const s = b.closest(".lvl-select").dataset.s;
    if (+b.dataset.l === 0) delete req[s]; else req[s] = +b.dataset.l;
    paint();
  });
  $("#save-req")?.addEventListener("click", async () => {
    try {
      await api("PUT", `/job-roles/${selected.id}`, { requirements: Object.entries(req).map(([skill_id, required_level]) => ({ skill_id: +skill_id, required_level })) });
      toast("Requisitos guardados"); loadGaps();
    } catch (err) { toast(err.message, true); }
  });
  $("#ren-role")?.addEventListener("click", () => formModal({ title: "Renombrar puesto", fields: [{ name: "name", label: "Nombre", value: selected.name, required: true }],
    submit: "Renombrar", onSubmit: (v) => api("PUT", `/job-roles/${selected.id}`, v) }).then((r) => r && router()));
  $("#del-role")?.addEventListener("click", async () => {
    if (await confirmModal("Eliminar puesto", `Se eliminará «${selected.name}» y sus requisitos. Los empleados quedarán sin puesto asignado.`)) {
      await api("DELETE", `/job-roles/${selected.id}`); location.hash = "#/puestos";
    }
  });

  async function loadGaps() {
    const g = await api("GET", `/job-roles/${selected.id}/gaps?scope=${gapScope}`);
    const reqs = g.by_skill;
    const panel = $("#gap-panel");
    const toggle = `<div class="actions"><select class="input" id="gap-scope">
      <option value="role" ${gapScope === "role" ? "selected" : ""}>Empleados con este puesto</option>
      <option value="all" ${gapScope === "all" ? "selected" : ""}>Toda la plantilla (buscar candidatos)</option></select></div>`;
    if (!reqs.length) { panel.innerHTML = `<h2>Análisis de brechas</h2><p class="muted">Define al menos un requisito para ver las brechas.</p>`; return; }
    panel.innerHTML = `<div class="page-head" style="margin-bottom:8px"><div><h2>Análisis de brechas</h2>
      <p class="sub" style="margin:0">Nivel actual frente al requerido. En ámbar, lo que falta; rayado, evaluaciones antiguas.</p></div>${toggle}</div>
      ${g.employees.length ? `<div class="table-wrap"><table class="list"><tr><th>Empleado</th><th>Cumplimiento</th><th class="num">Pendientes</th>
        ${reqs.map((b) => `<th class="num">${esc(skillName[b.skill_id])}<br><small class="muted">≥ ${b.required_level}</small></th>`).join("")}</tr>
        ${g.employees.map((e) => `<tr><td style="min-width:170px"><a href="#/empleado/${e.id}">${esc(e.name)}</a><br><small class="muted">${esc(e.job_role || "Sin puesto")}</small></td>
          <td><div class="actions" style="flex-wrap:nowrap"><div class="bar" style="flex:1"><i style="width:${e.coverage}%;background:${e.coverage === 100 ? "var(--green)" : "var(--l4)"}"></i></div><b>${e.coverage}%</b></div></td>
          <td class="num">${e.below ? `<span class="tag pill-gap">${e.below}</span>` : '<span class="tag pill-ok">Cumple</span>'}</td>
          ${e.skills.map((s) => { const v = s.level ?? 0;
            return `<td class="num">${lvl(s.level, s.stale, s.level == null ? "" : `${s.level} · evaluado el ${fdate(s.evaluated_at)}`)}${v < s.required_level ? ` <small style="color:var(--amber);font-weight:600">−${s.required_level - v}</small>` : ""}</td>`; }).join("")}</tr>`).join("")}
        <tr><td colspan="3" class="muted">Personas que cumplen</td>${reqs.map((b) => `<td class="num muted">${b.meeting}/${b.total}</td>`).join("")}</tr>
        </table></div>` : `<p class="muted">No hay empleados asignados a este puesto. Cambia a «Toda la plantilla» para buscar candidatos.</p>`}`;
    $("#gap-scope").addEventListener("change", (e) => { gapScope = e.target.value; loadGaps(); });
  }
  loadGaps();
}

/* -------------------------------------------------------------- empleados */
async function employeeForm(emp) {
  const [{ items: roles }, { items: emps }] = await Promise.all([api("GET", "/job-roles"), api("GET", "/employees?limit=1000")]);
  const depts = [...new Set(emps.map((e) => e.department).filter(Boolean))].sort();
  return formModal({
    title: emp ? "Editar empleado" : "Nuevo empleado",
    fields: [
      { name: "name", label: "Nombre y apellidos", value: emp?.name, required: true },
      { name: "email", label: "Email", type: "email", value: emp?.email },
      { name: "external_id", label: "Código de empleado (opcional, el de vuestro sistema de RRHH)", value: emp?.external_id },
      { name: "department", label: "Departamento", value: emp?.department, list: depts },
      { name: "job_role_id", label: "Puesto", type: "select", value: emp?.job_role_id ?? "",
        options: [{ value: "", label: "Sin puesto" }, ...roles.map((r) => ({ value: r.id, label: r.name }))] },
    ],
    submit: emp ? "Guardar cambios" : "Crear empleado",
    onSubmit: (v) => emp ? api("PUT", `/employees/${emp.id}`, v) : api("POST", "/employees", v),
  });
}

async function viewEmployees(view) {
  const { items: emps, total } = await api("GET", "/employees?limit=1000");
  view.innerHTML = head("Empleados", `${total} personas registradas.`, canEdit() ? '<button class="btn primary" id="new-emp">Nuevo empleado</button>' : "") +
    `<div class="filters"><input class="input" id="q" type="search" placeholder="Buscar por nombre, email, código o departamento">
      <label class="check"><input type="checkbox" id="only-stale"> Solo con evaluaciones antiguas o sin evaluar</label></div>
    <div class="panel" style="padding:8px 12px"><div class="table-wrap"><table class="list" id="tbl"></table></div></div>`;
  const draw = () => {
    const q = $("#q").value.toLowerCase(), onlyStale = $("#only-stale").checked;
    const list = emps.filter((e) => [e.name, e.email, e.department, e.job_role, e.external_id].join(" ").toLowerCase().includes(q) &&
      (!onlyStale || e.stale > 0 || e.assessed === 0));
    $("#tbl").innerHTML = `<tr><th>Nombre</th><th>Código</th><th>Departamento</th><th>Puesto</th><th class="num">Evaluadas</th><th>Última evaluación</th><th></th></tr>` +
      (list.length ? list.map((e) => `<tr>
        <td><a href="#/empleado/${e.id}"><b>${esc(e.name)}</b></a><br><small class="muted">${esc(e.email || "")}</small></td>
        <td class="muted">${esc(e.external_id || "")}</td>
        <td>${esc(e.department)}</td><td>${esc(e.job_role) || '<span class="muted">Sin puesto</span>'}</td>
        <td class="num">${e.assessed}</td>
        <td>${e.last_evaluated_at ? `<span class="date" title="${fdatetime(e.last_evaluated_at)}">${ago(e.last_evaluated_at)}</span>
            ${e.stale ? `<br><small class="stale-text">${e.stale} desactualizada(s)</small>` : ""}` : '<span class="tag pill-gap">Sin evaluar</span>'}</td>
        <td class="num">${canEdit() ? `<button class="btn small" data-edit="${e.id}">Editar</button> <button class="btn small danger" data-del="${e.id}">Eliminar</button>` : ""}</td></tr>`).join("")
        : `<tr><td colspan="7" class="empty">No hay empleados que coincidan.</td></tr>`);
  };
  draw();
  $("#q").addEventListener("input", draw);
  $("#only-stale").addEventListener("change", draw);
  $("#new-emp")?.addEventListener("click", () => employeeForm().then((r) => r && router()));
  $("#tbl").addEventListener("click", async (e) => {
    const ed = e.target.dataset.edit, del = e.target.dataset.del;
    if (ed) employeeForm(emps.find((x) => x.id == ed)).then((r) => r && router());
    if (del) {
      const emp = emps.find((x) => x.id == del);
      if (await confirmModal("Eliminar empleado", `Se eliminará a ${emp.name} y todas sus evaluaciones. No se puede deshacer.`)) {
        await api("DELETE", `/employees/${del}`); toast("Empleado eliminado"); router();
      }
    }
  });
}

/* Ficha de un empleado */
async function viewEmployee(view, id) {
  const [emp, { items: skills }, { items: hist }, settings] = await Promise.all([
    api("GET", `/employees/${id}`), api("GET", "/skills"), api("GET", `/employees/${id}/history`), api("GET", "/settings")]);
  const byskill = Object.fromEntries(emp.assessments.map((a) => [a.skill_id, a]));
  const req = Object.fromEntries(emp.requirements.map((r) => [r.skill_id, r.required_level]));
  const cats = [...new Set(skills.map((s) => s.category))];
  const info = [emp.job_role || "Sin puesto", emp.department, emp.email, emp.external_id && `Código ${emp.external_id}`].filter(Boolean).join(" · ");
  view.innerHTML = head(emp.name, esc(info),
    `<a class="btn" href="#/empleados">Volver</a>${canEdit() ? `<button class="btn" id="edit-emp">Editar datos</button>
     <button class="btn primary" id="review-all" ${emp.assessed ? "" : "disabled"}>Confirmar todos los niveles</button>` : ""}`) + `
    <div class="summary">
      <div><b>${emp.coverage == null ? "—" : emp.coverage + "%"}</b><span>cumplimiento del puesto</span></div>
      <div><b>${emp.assessed}</b><span>habilidades evaluadas</span></div>
      <div><b>${emp.last_evaluated_at ? ago(emp.last_evaluated_at) : "—"}</b><span>última evaluación</span></div>
      <div><b class="${emp.stale ? "warn" : ""}">${emp.stale}</b><span>con más de ${settings.stale_months} meses</span></div>
    </div>
    <div class="grid g-3-1" id="emp-detail">
      <div class="panel"><h2>Habilidades</h2><p class="sub">${canEdit() ? "Pulsa un nivel para cambiarlo; pulsar el nivel actual lo confirma con fecha de hoy." : "Nivel actual y fecha de la última evaluación."}</p>
        <div class="table-wrap"><table class="list">${cats.map((c) => `<tr><th colspan="4">${esc(c)}</th></tr>` +
          skills.filter((s) => s.category === c).map((s) => `<tr data-row="${s.id}"><td>${esc(s.name)}</td>
              <td class="num muted">${req[s.id] ? `Puesto ≥ ${req[s.id]}` : ""}</td>
              <td class="num"><div class="lvl-select" data-s="${s.id}">${[0, 1, 2, 3, 4, 5].map((i) =>
                `<button type="button" data-l="${i}" ${canEdit() ? "" : "disabled"} title="${LEVEL_NAMES[i]}">${i}</button>`).join("")}</div></td>
              <td class="date" data-date="${s.id}"></td></tr>`).join("")).join("")}
        </table></div></div>
      <div class="panel"><h2>Historial</h2><p class="sub">Últimos cambios de nivel.</p>
        ${hist.length ? `<ul class="feed">${hist.slice(0, 25).map((h) => `<li>${lvl(h.old_level)} → ${lvl(h.new_level)}<div>${esc(h.skill)}
          <small>${esc(h.changed_by)}, ${fdate(h.changed_at)}</small></div></li>`).join("")}</ul>`
          : '<p class="muted">Sin cambios registrados.</p>'}</div>
    </div>`;
  const paint = () => $$(".lvl-select", view).forEach((g) => {
    const a = byskill[g.dataset.s], cur = a ? a.level : null, r = req[g.dataset.s] || 0;
    $$("button", g).forEach((b) => {
      const on = +b.dataset.l === cur;
      b.classList.toggle("on", on);
      b.style.background = on ? LEVEL_COLORS[cur] : "";
      b.style.backgroundImage = on && a.stale ? (cur >= 3 ? "var(--hatch-dark)" : "var(--hatch-light)") : "";
      b.style.color = on && cur >= 4 ? "#fff" : "";
      b.style.outline = on && r && cur < r ? "2px solid var(--amber)" : "";
    });
    const cell = $(`[data-date="${g.dataset.s}"]`, view);
    cell.innerHTML = a ? `<span class="${a.stale ? "stale-text" : ""}" title="${esc(`Evaluado por ${a.evaluated_by}`)}">${fdate(a.evaluated_at)}</span>`
                       : `<span class="muted">${r ? '<span class="stale-text">Sin evaluar</span>' : "Sin evaluar"}</span>`;
  });
  paint();
  $("#emp-detail").addEventListener("click", async (e) => {
    const b = e.target.closest(".lvl-select button");
    if (!b || b.disabled) return;
    const s = b.closest(".lvl-select").dataset.s;
    try {
      const r = await api("PUT", `/assessments/${id}/${s}`, { level: +b.dataset.l });
      byskill[s] = { ...(byskill[s] || {}), level: r.level, evaluated_at: r.evaluated_at, evaluated_by: r.evaluated_by, stale: r.stale };
      paint();
      if (r.result === "reviewed") toast("Nivel confirmado con fecha de hoy");
    } catch (err) { toast(err.message, true); }
  });
  $("#edit-emp")?.addEventListener("click", () => employeeForm(emp).then((r) => r && router()));
  $("#review-all")?.addEventListener("click", async () => {
    if (!await confirmModal("Confirmar todos los niveles", `Se registrará hoy como fecha de evaluación de las ${emp.assessed} habilidades evaluadas de ${emp.name}, sin cambiar sus niveles. Hazlo solo si los has revisado.`, "Confirmar niveles")) return;
    const r = await api("POST", `/employees/${id}/review`, {});
    toast(`${r.reviewed} niveles confirmados`); router();
  });
}

/* ------------------------------------------------------------ habilidades */
async function viewSkills(view) {
  const { items: skills } = await api("GET", "/skills");
  const cats = [...new Set(skills.map((s) => s.category))].sort();
  const form = (s) => formModal({
    title: s ? "Editar habilidad" : "Nueva habilidad",
    fields: [{ name: "name", label: "Nombre", value: s?.name, required: true, placeholder: "p. ej. Terraform" },
             { name: "category", label: "Categoría", value: s?.category, list: cats, placeholder: "p. ej. Infraestructura" },
             { name: "description", label: "Descripción (opcional)", value: s?.description }],
    submit: s ? "Guardar cambios" : "Crear habilidad",
    onSubmit: (v) => s ? api("PUT", `/skills/${s.id}`, v) : api("POST", "/skills", v),
  }).then((r) => r && router());
  view.innerHTML = head("Habilidades", `${skills.length} habilidades en ${cats.length} categorías.`, canEdit() ? '<button class="btn primary" id="new-sk">Nueva habilidad</button>' : "") +
    `<div class="panel" style="padding:8px 12px"><div class="table-wrap"><table class="list" id="tbl">
      <tr><th>Habilidad</th><th>Categoría</th><th class="num">La conocen</th><th class="num">Nivel 4-5</th><th class="num">Evaluaciones antiguas</th><th></th></tr>
      ${skills.length ? skills.map((s) => `<tr><td><b>${esc(s.name)}</b>${s.description ? `<br><small class="muted">${esc(s.description)}</small>` : ""}</td>
        <td><span class="tag">${esc(s.category)}</span></td><td class="num">${s.people}</td><td class="num">${s.experts}</td>
        <td class="num">${s.stale ? `<span class="stale-text">${s.stale}</span>` : "0"}</td>
        <td class="num">${canEdit() ? `<button class="btn small" data-edit="${s.id}">Editar</button> <button class="btn small danger" data-del="${s.id}">Eliminar</button>` : ""}</td></tr>`).join("")
        : '<tr><td colspan="6" class="empty">Aún no hay habilidades. Crea la primera con «Nueva habilidad».</td></tr>'}
    </table></div></div>`;
  $("#new-sk")?.addEventListener("click", () => form());
  $("#tbl").addEventListener("click", async (e) => {
    const ed = e.target.dataset.edit, del = e.target.dataset.del;
    if (ed) form(skills.find((s) => s.id == ed));
    if (del) {
      const s = skills.find((x) => x.id == del);
      if (await confirmModal("Eliminar habilidad", `Se eliminará «${s.name}» con todas sus evaluaciones y los requisitos de puesto que la usen.`)) {
        await api("DELETE", `/skills/${del}`); toast("Habilidad eliminada"); router();
      }
    }
  });
}

/* -------------------------------------------------------------- datos */
async function viewData(view) {
  view.innerHTML = head("Importar / exportar", "Trabaja la matriz en Excel y vuelve a cargarla.") + `
    <div class="grid g-2">
      <div class="panel"><h2>Exportar</h2><p class="sub">El Excel incluye la matriz con colores, una hoja con todas las evaluaciones y sus fechas, las habilidades y la escala.</p>
        <div class="actions"><a class="btn primary" href="/api/v1/export?format=xlsx">Descargar Excel</a>
          <a class="btn" href="/api/v1/export?format=csv">CSV (matriz)</a>
          <a class="btn" href="/api/v1/export?format=csv&layout=long">CSV (evaluaciones con fecha)</a></div>
        <h2 style="margin-top:22px">Formatos que se pueden importar</h2>
        <p class="sub"><b>Matriz</b>: columnas Código, Nombre, Email, Departamento, Puesto y una columna por habilidad con valores 0-5.
          La celda vacía no cambia nada. Es la hoja «Matriz» del Excel exportado.</p>
        <p class="sub"><b>Evaluaciones</b>: una fila por evaluación con Código o Email, Empleado, Habilidad, Nivel y, opcionalmente,
          Fecha evaluación (AAAA-MM-DD). Útil para cargar datos históricos conservando su fecha.</p>
        <p class="sub">Los empleados se identifican por Código, después por Email. Las habilidades y puestos nuevos se crean automáticamente.</p>
      </div>
      <div class="panel"><h2>Importar</h2>
        ${canEdit() ? `<p class="sub">Archivos .xlsx o .csv (separado por punto y coma o coma).</p>
        <label class="check" style="margin-bottom:12px"><input type="checkbox" id="review-unchanged">
          Contar como revisados hoy los niveles que no cambian</label>
        <p class="sub" style="margin-top:-6px">Márcalo solo si el archivo es el resultado de una revisión completa. Sin marcar, reimportar un Excel no altera las fechas.</p>
        <label class="drop" id="drop"><input type="file" id="file" accept=".xlsx,.csv" class="hidden">
          <b>Arrastra aquí el archivo</b><br>o haz clic para seleccionarlo</label>
        <div id="import-result" style="margin-top:14px"></div>`
        : '<p class="muted">Tu usuario es de solo lectura. Pide a RRHH o a un manager que importe los datos.</p>'}
      </div>
    </div>`;
  if (!canEdit()) return;
  const drop = $("#drop"), input = $("#file");
  const upload = async (file) => {
    if (!file) return;
    const fd = new FormData();
    fd.append("file", file);
    fd.append("review_unchanged", $("#review-unchanged").checked ? "1" : "0");
    $("#import-result").innerHTML = '<p class="muted">Importando…</p>';
    try {
      const r = await api("POST", "/import", fd);
      const row = (label, n) => `<tr><td>${label}</td><td class="num">${n}</td></tr>`;
      $("#import-result").innerHTML = `<table class="list">
        ${row("Formato detectado", r.format === "long" ? "Evaluaciones" : "Matriz")}
        ${row("Empleados nuevos", r.employees_created)}${row("Empleados actualizados", r.employees_updated)}
        ${row("Habilidades nuevas", r.skills_created)}${row("Evaluaciones nuevas", r.created)}
        ${row("Niveles modificados", r.changed)}${row("Niveles confirmados sin cambios", r.reviewed)}
        ${row("Sin cambios", r.unchanged)}${r.skipped ? row("Ignoradas por ser más antiguas que las registradas", r.skipped) : ""}</table>
        ${r.warnings.length ? `<p class="sub" style="color:var(--amber);margin-top:10px">${r.warnings.map(esc).join("<br>")}</p>` : ""}
        <p><a href="#/matriz">Ver la matriz</a></p>`;
      toast("Importación completada");
    } catch (err) { $("#import-result").innerHTML = `<p class="error">${esc(err.message)}</p>`; }
    input.value = "";
  };
  input.addEventListener("change", () => upload(input.files[0]));
  ["dragover", "dragenter"].forEach((ev) => drop.addEventListener(ev, (e) => { e.preventDefault(); drop.classList.add("over"); }));
  ["dragleave", "drop"].forEach((ev) => drop.addEventListener(ev, () => drop.classList.remove("over")));
  drop.addEventListener("drop", (e) => { e.preventDefault(); upload(e.dataTransfer.files[0]); });
}

/* -------------------------------------------------------- administración */
async function viewAdmin(view, tab = "usuarios") {
  const tabs = { usuarios: "Usuarios", aplicaciones: "Aplicaciones (API)", ajustes: "Ajustes" };
  view.innerHTML = head("Administración", "Usuarios de la web, acceso de otras aplicaciones y ajustes generales.") +
    `<nav class="tabs">${Object.entries(tabs).map(([k, v]) => `<a href="#/admin/${k}" class="${k === tab ? "active" : ""}">${v}</a>`).join("")}</nav><div id="tab"></div>`;
  const el = $("#tab");
  if (tab === "aplicaciones") return adminTokens(el);
  if (tab === "ajustes") return adminSettings(el);
  return adminUsers(el);
}

async function adminUsers(el) {
  const { items: users } = await api("GET", "/users");
  const roleOpts = Object.entries(ROLE_NAMES).map(([value, label]) => ({ value, label }));
  const form = (u) => formModal({
    title: u ? `Editar usuario ${u.username}` : "Nuevo usuario",
    fields: [...(u ? [] : [{ name: "username", label: "Usuario", required: true }]),
      { name: "full_name", label: "Nombre completo", value: u?.full_name },
      { name: "role", label: "Rol", type: "select", value: u?.role || "lector", options: roleOpts },
      { name: "password", label: u ? "Nueva contraseña (vacío para mantenerla)" : "Contraseña (mínimo 8 caracteres)", type: "password", required: !u }],
    submit: u ? "Guardar cambios" : "Crear usuario",
    onSubmit: (v) => u ? api("PUT", `/users/${u.id}`, v) : api("POST", "/users", v),
  }).then((r) => r && router());
  el.innerHTML = `<div class="page-head" style="margin-bottom:12px"><p class="muted" style="margin:0">RRHH y managers editan niveles; los lectores solo consultan.</p>
      <button class="btn primary" id="new-user">Nuevo usuario</button></div>
    <div class="panel" style="padding:8px 12px"><div class="table-wrap"><table class="list" id="tbl">
      <tr><th>Usuario</th><th>Nombre</th><th>Rol</th><th></th></tr>
      ${users.map((u) => `<tr><td><b>${esc(u.username)}</b></td><td>${esc(u.full_name)}</td><td><span class="tag">${ROLE_NAMES[u.role]}</span></td>
        <td class="num"><button class="btn small" data-edit="${u.id}">Editar</button>
        ${u.id !== state.me.id ? `<button class="btn small danger" data-del="${u.id}">Eliminar</button>` : ""}</td></tr>`).join("")}
    </table></div></div>`;
  $("#new-user").addEventListener("click", () => form());
  $("#tbl").addEventListener("click", async (e) => {
    const ed = e.target.dataset.edit, del = e.target.dataset.del;
    if (ed) form(users.find((u) => u.id == ed));
    if (del) {
      const u = users.find((x) => x.id == del);
      if (await confirmModal("Eliminar usuario", `El usuario ${u.username} ya no podrá iniciar sesión.`)) {
        await api("DELETE", `/users/${del}`); toast("Usuario eliminado"); router();
      }
    }
  });
}

async function adminTokens(el) {
  const { items: tokens } = await api("GET", "/tokens");
  const origin = location.origin;
  el.innerHTML = `<div class="grid g-3-1">
    <div class="panel"><div class="page-head" style="margin-bottom:8px"><div><h2>Tokens de acceso</h2>
        <p class="sub" style="margin:0">Cada aplicación que se conecte a la API necesita su propio token. Revócalo si deja de usarse o se filtra.</p></div>
        <button class="btn primary" id="new-token">Nuevo token</button></div>
      <div class="table-wrap"><table class="list" id="tbl"><tr><th>Aplicación</th><th>Token</th><th>Permiso</th><th>Último uso</th><th>Estado</th><th></th></tr>
      ${tokens.length ? tokens.map((t) => `<tr><td><b>${esc(t.name)}</b><br><small class="muted">creado por ${esc(t.created_by)}, ${fdate(t.created_at)}</small></td>
        <td class="muted" style="font-family:Consolas,monospace">${esc(t.token_prefix)}…</td>
        <td><span class="tag">${t.scope === "write" ? "Lectura y escritura" : "Solo lectura"}</span></td>
        <td class="date">${t.last_used_at ? ago(t.last_used_at) : "Nunca"}</td>
        <td>${t.revoked_at ? '<span class="tag">Revocado</span>' : '<span class="tag pill-ok">Activo</span>'}</td>
        <td class="num">${t.revoked_at ? "" : `<button class="btn small danger" data-rev="${t.id}">Revocar</button>`}</td></tr>`).join("")
        : '<tr><td colspan="6" class="empty">Todavía no hay aplicaciones conectadas.</td></tr>'}</table></div></div>
    <div class="panel"><h2>Cómo usar la API</h2>
      <p class="sub">Documentación completa y pruebas en <a href="/api/docs" target="_blank" rel="noopener">${origin}/api/docs</a>.</p>
      <p class="sub" style="margin-bottom:0">Consultar empleados con evaluaciones antiguas:</p>
      <pre class="code">curl -H "Authorization: Bearer smx_…" \\
  "${origin}/api/v1/employees?has_stale=true"</pre>
      <p class="sub" style="margin:12px 0 0">Registrar evaluaciones:</p>
      <pre class="code">curl -X POST -H "Authorization: Bearer smx_…" \\
  -H "Content-Type: application/json" \\
  -d '[{"employee_email":"ana@empresa.com",
       "skill":"Kubernetes","level":3}]' \\
  ${origin}/api/v1/assessments</pre></div></div>`;
  $("#new-token").addEventListener("click", async () => {
    const r = await formModal({ title: "Nuevo token de API",
      fields: [{ name: "name", label: "Aplicación que lo usará", required: true, placeholder: "p. ej. Portal de formación" },
               { name: "scope", label: "Permiso", type: "select", value: "read", options: [{ value: "read", label: "Solo lectura" }, { value: "write", label: "Lectura y escritura" }] }],
      submit: "Crear token", onSubmit: (v) => api("POST", "/tokens", v) });
    if (!r) return;
    await formModal({ title: "Token creado", cancel: null, submit: "Ya lo he guardado", onSubmit: () => true,
      fields: [{ type: "info", html: `Copia el token ahora: <b>no se volverá a mostrar</b>. Guárdalo en la configuración de «${esc(r.name)}».
        <div class="token-box" style="margin-top:10px" id="tok">${esc(r.token)}</div>
        <button type="button" class="btn small" style="margin-top:8px" onclick="navigator.clipboard.writeText('${esc(r.token)}').then(()=>toast('Token copiado'))">Copiar</button>` }] });
    router();
  });
  $("#tbl").addEventListener("click", async (e) => {
    const id = e.target.dataset.rev;
    if (!id) return;
    const t = tokens.find((x) => x.id == id);
    if (await confirmModal("Revocar token", `«${t.name}» dejará de poder acceder a la API inmediatamente.`, "Revocar")) {
      await api("DELETE", `/tokens/${id}`); toast("Token revocado"); router();
    }
  });
}

async function adminSettings(el) {
  const s = await api("GET", "/settings");
  el.innerHTML = `<div class="panel" style="max-width:560px"><h2>Evaluaciones desactualizadas</h2>
    <p class="sub">Una evaluación se marca como desactualizada cuando han pasado más meses de los indicados desde su fecha.</p>
    <form id="set-form" class="actions" style="align-items:flex-end">
      <label class="field">Meses<input name="stale_months" type="number" min="1" max="120" value="${s.stale_months}" required style="width:110px"></label>
      <button class="btn primary">Guardar</button></form></div>`;
  $("#set-form").addEventListener("submit", async (e) => {
    e.preventDefault();
    try { await api("PUT", "/settings", { stale_months: +new FormData(e.target).get("stale_months") }); toast("Ajuste guardado"); state.me = await api("GET", "/auth/me"); }
    catch (err) { toast(err.message, true); }
  });
}

/* ---------------------------------------------------------------- inicio */
(async () => {
  try { state.me = await api("GET", "/auth/me"); startApp(); }
  catch { showLogin(); }
})();
