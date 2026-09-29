const $ = (s) => document.querySelector(s);
const fmt = (n) => (n == null ? "–" : n.toLocaleString("fr-FR"));
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const pct = (v) => (v == null ? "–" : `<span class="${v >= 0 ? "up" : "down"}">${v > 0 ? "+" : ""}${v} %</span>`);
const dateFr = (iso) => (iso ? new Date(iso).toLocaleString("fr-FR", { dateStyle: "short", timeStyle: "short" }) : "");
const jourFr = (iso) => new Date(iso + "T12:00").toLocaleDateString("fr-FR", { weekday: "short", day: "numeric", month: "short", year: "numeric" });
const carte = (id, cls = "carte") => `<img class="${cls}" src="/api/image/${id}" alt="" loading="lazy" onerror="this.classList.add('vide')">`;
const EFFET = { crash: "Baisse", hausse: "Hausse", volatil: "Instable" };

async function api(url, opts = {}) {
  const res = await fetch(url, { headers: { "Content-Type": "application/json" }, ...opts,
    body: opts.body ? JSON.stringify(opts.body) : undefined });
  const data = res.status === 204 ? null : await res.json();
  if (!res.ok) throw new Error(data?.erreur || res.statusText);
  return data;
}

async function busy(btn, fn) {
  const label = btn.textContent;
  btn.disabled = true; btn.textContent = "En cours…";
  try { await fn(); } catch (e) { alert(e.message); }
  finally { btn.disabled = false; btn.textContent = label; }
}

// Onglets
document.querySelectorAll("nav button").forEach((b) => b.addEventListener("click", () => {
  document.querySelectorAll("nav button, .onglet").forEach((x) => x.classList.remove("actif"));
  b.classList.add("actif"); $("#" + b.dataset.tab).classList.add("actif");
  ({ signaux: loadJoueurs, populaires: loadPopulaires, calendrier: loadCalendrier, veille: loadVeille })[b.dataset.tab]();
}));

async function loadEtat() {
  const e = await api("/api/etat");
  $("#etat").textContent = `Dernier relevé : ${e.prix ? dateFr(e.prix) : "jamais"} · automatique toutes les ${e.intervalle_min} min`;
}

// Signaux
let selection = null, chart = null;
async function loadJoueurs() {
  const [joueurs, cal] = await Promise.all([api("/api/joueurs"), api("/api/calendrier")]);
  const ctx = cal.contexte;
  $("#contexte").innerHTML = [...ctx.crash_en_cours.map((e) => `<div class="alerte"><b>${esc(e.nom)} en cours</b> : ${esc(e.detail)}</div>`),
    ...ctx.crash_proche.map((e) => `<div class="alerte"><b>${esc(e.nom)} dans ${e.jours_avant} jour(s)</b>${e.estime ? " (date estimée)" : ""} : ${esc(e.detail)}</div>`)].join("");
  $("#liste-joueurs").innerHTML = joueurs.length ? joueurs.map((j) => {
    const s = j.stats, a = j.signal.avis, cls = a.includes("cheter") ? "acheter" : a.includes("endre") ? "vendre" : "attendre";
    return `<tr data-id="${j.id}">
      <td><div class="avec-carte">${carte(j.futbin_id)}<div><b>${esc(j.nom)}</b><br><span class="muted">${j.origine === "populaire" ? "top utilisés" : "ajouté"} · <a href="https://www.futbin.com/${window.ANNEE}/player/${j.futbin_id}" target="_blank" rel="noopener">FUTBIN</a></span></div></div></td>
      <td class="num">${s ? fmt(s.dernier) : "–"}</td><td class="num">${s ? pct(s.var_24h) : "–"}</td><td class="num">${s ? pct(s.var_7j) : "–"}</td>
      <td>${s ? `${fmt(s.min_30j)} – ${fmt(s.max_30j)}<div class="jauge"><i style="left:calc(${s.position_30j}% - 2px)"></i></div>` : "–"}</td>
      <td><span class="avis ${cls}">${esc(a)}</span></td>
      <td><button class="lien" data-suppr="${j.id}" title="Ne plus suivre">✕</button></td></tr>`;
  }).join("") : `<tr><td colspan="7" class="muted">Aucun joueur suivi. Colle un lien FUTBIN ci-dessus, ou va dans « Plus utilisés » pour suivre le top 20.</td></tr>`;
  window._joueurs = joueurs;
  loadEtat();
}

$("#liste-joueurs").addEventListener("click", async (ev) => {
  const suppr = ev.target.closest("[data-suppr]");
  if (suppr) { ev.stopPropagation(); await api(`/api/joueurs/${suppr.dataset.suppr}`, { method: "DELETE" }); return loadJoueurs(); }
  const tr = ev.target.closest("tr[data-id]");
  if (tr) showDetail(+tr.dataset.id);
});

async function showDetail(id) {
  selection = id;
  const j = window._joueurs.find((x) => x.id === id);
  const d = await api(`/api/joueurs/${id}/prix`);
  $("#detail").hidden = false;
  $("#detail-nom").innerHTML = `${carte(j.futbin_id, "carte grande")}<span>${esc(j.nom)}</span>`;
  $("#detail-raisons").innerHTML = j.signal.raisons.length
    ? `<ul>${j.signal.raisons.map((r) => `<li>${esc(r)}</li>`).join("")}</ul>` : `<p class="muted">${esc(j.signal.avis)}</p>`;
  const p = d.profil;
  $("#detail-profil").innerHTML = p.meilleur_achat
    ? `<p>D'après tes relevés, le jour le moins cher est le <b>${p.meilleur_achat}</b> et le plus cher le <b>${p.meilleure_vente}</b>.</p>`
    : `<p class="muted">Encore trop peu de relevés pour trouver le meilleur jour d'achat.</p>`;
  const css = getComputedStyle(document.documentElement);
  if (chart) chart.destroy();
  chart = new Chart($("#graph"), {
    type: "line",
    data: { labels: d.points.map((x) => dateFr(x[0])),
      datasets: [{ data: d.points.map((x) => x[1]), borderColor: css.getPropertyValue("--accent"), pointRadius: 0, borderWidth: 2, tension: 0.2 }] },
    options: { maintainAspectRatio: false, plugins: { legend: { display: false } },
      scales: { x: { ticks: { maxTicksLimit: 8, color: css.getPropertyValue("--muted") }, grid: { display: false } },
                y: { ticks: { color: css.getPropertyValue("--muted"), callback: (v) => fmt(v) }, grid: { color: css.getPropertyValue("--line") } } } },
  });
  $("#detail").scrollIntoView({ behavior: "smooth" });
}

$("#form-joueur").addEventListener("submit", async (ev) => {
  ev.preventDefault();
  const f = new FormData(ev.target);
  try { await api("/api/joueurs", { method: "POST", body: Object.fromEntries(f) }); ev.target.reset(); loadJoueurs(); }
  catch (e) { alert(e.message); }
});
$("#btn-collecter").addEventListener("click", (ev) => busy(ev.target, async () => {
  const r = await api("/api/collecter", { method: "POST" });
  if (r.erreurs.length) alert(`${r.releves} prix relevés.\nProblèmes :\n` + r.erreurs.join("\n"));
  loadJoueurs();
}));
$("#form-prix").addEventListener("submit", async (ev) => {
  ev.preventDefault();
  try { await api(`/api/joueurs/${selection}/prix`, { method: "POST", body: { prix: new FormData(ev.target).get("prix") } }); ev.target.reset(); await loadJoueurs(); showDetail(selection); }
  catch (e) { alert(e.message); }
});
$("#form-histo").addEventListener("submit", (ev) => {
  ev.preventDefault();
  busy(ev.submitter, async () => {
    const r = await api(`/api/joueurs/${selection}/historique`, { method: "POST" });
    alert(`${r.points} points d'historique importés.`); await loadJoueurs(); showDetail(selection);
  });
});

// Plus utilisés
// Un même joueur peut avoir plusieurs cartes (base, promo…) : on les numérote pour les distinguer.
function nommer(liste) {
  const total = {}, vus = {};
  liste.forEach((p) => { total[p.nom] = (total[p.nom] || 0) + 1; });
  return liste.map((p) => {
    if (total[p.nom] < 2) return { ...p, libelle: p.nom };
    vus[p.nom] = (vus[p.nom] || 0) + 1;
    return { ...p, libelle: `${p.nom} (carte ${vus[p.nom]})` };
  });
}
const lienCarte = (p) => `<a href="https://www.futbin.com/${window.ANNEE}/player/${p.futbin_id}" target="_blank" rel="noopener">${esc(p.libelle)}</a>`;
$("#pop-liste").addEventListener("click", async (ev) => {
  const b = ev.target.closest("[data-suivre]");
  if (!b) return;
  try { await api("/api/joueurs", { method: "POST", body: { futbin_id: b.dataset.suivre, nom: b.dataset.nom } }); loadPopulaires(); }
  catch (e) { alert(e.message); }
});
async function loadPopulaires() {
  const d = await api("/api/populaires");
  $("#pop-date").textContent = d.releve_le ? `Relevé du ${dateFr(d.releve_le)}` : "Jamais relevé";
  $("#pop-liste").innerHTML = nommer(d.joueurs).map((p) => `<li>${carte(p.futbin_id, "carte mini")}${lienCarte(p)}
    ${p.suivi ? '<span class="tag">suivi</span>' : `<button class="lien" data-suivre="${p.futbin_id}" data-nom="${esc(p.nom)}">+ suivre</button>`}</li>`).join("")
    || `<p class="muted">Clique sur « Actualiser depuis FUTBIN ».</p>`;
  $("#pop-reguliers").innerHTML = nommer(d.reguliers).map((p) => `<tr><td>${lienCarte(p)}</td><td class="num">${p.apparitions}</td><td class="num">${p.rang_moyen}</td></tr>`).join("");
}
$("#btn-pop-maj").addEventListener("click", (ev) => busy(ev.target, async () => {
  const r = await api("/api/populaires/actualiser", { method: "POST" });
  if (r.erreurs.length) alert(r.erreurs.join("\n"));
  loadPopulaires();
}));
$("#btn-pop-suivre").addEventListener("click", (ev) => busy(ev.target, async () => {
  const r = await api("/api/populaires/suivre", { method: "POST", body: { top: 20 } });
  alert(`${r.ajoutes} joueurs ajoutés au suivi.`); loadPopulaires();
}));

// Calendrier
async function loadCalendrier() {
  const d = await api("/api/calendrier");
  $("#cal-avenir").innerHTML = d.a_venir.map((e) => `<li><b>${esc(e.nom)}</b> <span class="tag ${e.effet}">${EFFET[e.effet] || e.effet}</span>
    ${e.estime ? '<span class="tag">estimé</span>' : ""}<br>
    <span class="muted">${jourFr(e.debut)} → ${jourFr(e.fin)} · ${e.en_cours ? "en cours" : `dans ${e.jours_avant} j`}</span><br>${esc(e.detail)}</li>`).join("")
    || `<li class="muted">Rien de prévu dans les 4 prochains mois.</li>`;
  $("#cal-semaine").innerHTML = d.hebdomadaire.map((r) => `<li><b>${r.jour_nom} ${r.heure}</b> · ${esc(r.nom)} <span class="tag ${r.effet}">${EFFET[r.effet]}</span><br>${esc(r.detail)}</li>`).join("");
  $("#cal-histo").innerHTML = d.historique.slice().reverse().map((e) => `<tr><td>FC ${e.saison}</td><td>${esc(e.nom)}</td>
    <td>${jourFr(e.debut)} → ${jourFr(e.fin)}</td><td><span class="tag ${e.effet}">${EFFET[e.effet]}</span></td><td>${esc(e.detail)}</td></tr>`).join("");
}
$("#form-evt").addEventListener("submit", async (ev) => {
  ev.preventDefault();
  try { await api("/api/calendrier", { method: "POST", body: Object.fromEntries(new FormData(ev.target)) }); ev.target.reset(); loadCalendrier(); }
  catch (e) { alert(e.message); }
});

// Veille
async function loadVeille() {
  const posts = await api(`/api/veille?importance=${$("#veille-importants").checked ? 4 : 0}`);
  $("#veille-liste").innerHTML = posts.map((p) => `<li><a href="${esc(p.url)}" target="_blank" rel="noopener">${esc(p.titre)}</a><br>
    <span class="muted">${esc(p.source)} · ${dateFr(p.publie_le || p.recupere_le)}</span> ${p.tags.map((t) => `<span class="tag ${t}">${t}</span>`).join("")}</li>`).join("")
    || `<li class="muted">Rien pour l'instant. Clique sur « Actualiser ».</li>`;
}
$("#veille-importants").addEventListener("change", loadVeille);
$("#btn-veille-maj").addEventListener("click", (ev) => busy(ev.target, async () => {
  const r = await api("/api/veille/actualiser", { method: "POST" });
  const err = r.filter((x) => x.erreur);
  if (err.length) alert("Sources non lues :\n" + err.map((x) => `${x.source} : ${x.erreur}`).join("\n"));
  loadVeille();
}));

loadJoueurs();
