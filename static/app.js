const state = { counter: "1", history: [], clients: [], lines: [newLine()] };
let currentFile = null, currentMeta = null;

function newLine() { return { d: "", n: "500€/jour", q: "1", a: "" }; }
function el(id) { return document.getElementById(id); }
function today() {
  const d = new Date(), p = n => String(n).padStart(2, "0");
  return p(d.getDate()) + "/" + p(d.getMonth() + 1) + "/" + d.getFullYear();
}
function fmtTotal(t) { return (Math.round(t * 100) / 100) + " €"; }
function setStatus(s) { el("status").textContent = s; }
function notify(s) { if (window.notify === undefined) console.log(s); }

async function api(path, opts) {
  const r = await fetch(path, Object.assign({ headers: { "Content-Type": "application/json" } }, opts || {}));
  let d = null;
  try { d = await r.json(); } catch (e) { /* pas de JSON */ }
  if (!r.ok) throw new Error((d && d.error) || ("HTTP " + r.status));
  return d;
}

async function init() {
  try {
    const s = await api("/api/state");
    if (s.counter) state.counter = s.counter;
    if (s.history) state.history = s.history;
    if (s.clients) state.clients = s.clients;
  } catch (e) { /* premier lancement */ }
  el("number").value = state.counter;
  el("date").value = today();
  updateCounterInfo();
  renderLines(); renderClients(); renderHistory();
  el("gen").addEventListener("click", () => generate());
  el("chatAdd").addEventListener("click", chatAdd);
  el("chatFill").addEventListener("click", chatFill);
  el("chatInput").addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); chatAdd(); }
  });
  el("addLine").addEventListener("click", () => { state.lines.push(newLine()); renderLines(); });
  el("dl").addEventListener("click", () => { if (currentFile) download(currentFile); });
}

function updateCounterInfo() {
  el("counterInfo").textContent = "Prochain numéro : " + state.counter;
}

async function persistState() {
  await api("/api/state", { method: "POST", body: JSON.stringify({
    counter: state.counter, history: state.history, clients: state.clients
  })});
}

function renderLines() {
  const box = el("lines");
  box.innerHTML = "";
  state.lines.forEach((l, i) => {
    const row = document.createElement("div");
    row.className = "line";
    const mk = (cls, ph, val) => {
      const inp = document.createElement("input");
      inp.className = "inp " + cls; inp.placeholder = ph; inp.value = val;
      inp.addEventListener("input", () => {
        if (cls === "d") l.d = inp.value;
        if (cls === "n") l.n = inp.value;
        if (cls === "q") l.q = inp.value;
        if (cls === "a") l.a = inp.value;
      });
      return inp;
    };
    row.appendChild(mk("d", "Prestation (gras)", l.d));
    row.appendChild(mk("n", "Note (ex : 500€/jour)", l.n));
    row.appendChild(mk("q", "Qté", l.q));
    row.appendChild(mk("a", "Montant", l.a));
    const del = document.createElement("button");
    del.className = "btn del"; del.textContent = "✕";
    del.addEventListener("click", () => {
      state.lines.splice(i, 1);
      if (!state.lines.length) state.lines.push(newLine());
      renderLines();
    });
    row.appendChild(del);
    box.appendChild(row);
  });
}

function renderClients() {
  const dl = el("clients");
  dl.innerHTML = "";
  state.clients.forEach(c => {
    const o = document.createElement("option");
    o.value = c;
    dl.appendChild(o);
  });
}

function renderHistory() {
  const box = el("history");
  box.innerHTML = "";
  if (!state.history.length) {
    const d = document.createElement("div");
    d.className = "muted";
    d.textContent = "Aucune facture générée pour l'instant.";
    box.appendChild(d);
    return;
  }
  state.history.forEach(h => {
    const row = document.createElement("div");
    row.className = "hrow";
    const info = document.createElement("div");
    info.className = "info";
    info.textContent = "N° " + h.number + " — " + h.client + " — " + fmtTotal(h.total);
    row.appendChild(info);
    if (h.test) {
      const tag = document.createElement("span");
      tag.className = "tag"; tag.textContent = "TEST";
      row.appendChild(tag);
    }
    const mkBtn = (txt, fn) => {
      const b = document.createElement("button");
      b.className = "btn hbtn"; b.textContent = txt;
      b.addEventListener("click", () => fn(b));
      return b;
    };
    row.appendChild(mkBtn("Aperçu", () => showPreview(h)));
    row.appendChild(mkBtn("PDF", () => download(h.file)));
    let armed = false, timer = null;
    row.appendChild(mkBtn("Supprimer", (b) => {
      if (!armed) {
        armed = true;
        b.textContent = "Confirmer ?";
        timer = setTimeout(() => { armed = false; b.textContent = "Supprimer"; }, 3000);
        return;
      }
      clearTimeout(timer);
      const del = async (n) => { if (n) api("/api/files/" + encodeURIComponent(n), { method: "DELETE" }).catch(() => {}); };
      del(h.file);
      if (h.preview) del(h.preview);
      state.history = state.history.filter(x => x !== h);
      persistState();
      renderHistory();
      if (currentFile === h.file) { currentFile = null; el("result").classList.add("hidden"); }
    }));
    box.appendChild(row);
  });
}

function download(name) {
  const a = document.createElement("a");
  a.href = "/files/" + encodeURIComponent(name);
  a.download = name;
  document.body.appendChild(a);
  a.click();
  a.remove();
}

function showPreview(h) {
  const img = el("preview");
  if (img.src.startsWith("blob:")) URL.revokeObjectURL(img.src);
  img.src = "/files/" + encodeURIComponent(h.preview) + "?t=" + Date.now();
  el("result").classList.remove("hidden");
  currentFile = h.file;
  currentMeta = h;
  el("result").scrollIntoView({ behavior: "smooth" });
}

async function generate() {
  const number = el("number").value.trim();
  const date = el("date").value.trim();
  const client = el("client").value.trim();
  const addr = el("addr").value.split("\n").map(s => s.trim()).filter(Boolean);
  const title = el("title").value.split("\n").map(s => s.trim()).filter(Boolean);
  const lines = state.lines
    .map(l => ({
      desc: l.d.trim(),
      note: l.n.trim(),
      qty: l.q.trim() === "" ? 1 : parseFloat(l.q),
      amount: parseFloat(l.a)
    }))
    .filter(l => l.desc || l.amount > 0);
  if (!/^\d+$/.test(number)) return setStatus("Numéro invalide.");
  if (!date) return setStatus("Date manquante.");
  if (!client) return setStatus("Client manquant.");
  if (!lines.length) return setStatus("Ajoutez au moins une ligne de prestation.");
  if (lines.some(l => !(l.amount > 0))) return setStatus("Chaque ligne doit avoir un montant.");

  setStatus("Génération…");
  el("gen").disabled = true;
  try {
    const d = await api("/api/generate", {
      method: "POST",
      body: JSON.stringify({ number, date, client_name: client, client_addr: addr, title, lines })
    });
    state.counter = String(parseInt(number, 10) + 1);
    el("number").value = state.counter;
    updateCounterInfo();
    const entry = {
      file: d.file, preview: d.preview, number: number, client: client,
      total: Math.round(d.total * 100) / 100, date: date,
      title: title.join(" "),
      when: new Date().toISOString()
    };
    state.history.unshift(entry);
    if (state.history.length > 60) state.history.length = 60;
    if (state.clients.indexOf(client) === -1 && state.clients.length < 200) {
      state.clients.push(client);
    }
    await persistState();
    renderHistory(); renderClients();
    showPreview(entry);
    setStatus("Facture générée. Prochain numéro : " + state.counter);
  } catch (e) {
    setStatus("Erreur : " + e.message);
  } finally {
    el("gen").disabled = false;
  }
}

function addChatMsg(role, text) {
  const box = el("chatMsgs");
  const d = document.createElement("div");
  d.className = "msg " + role;
  d.textContent = text;
  box.appendChild(d);
  box.scrollTop = box.scrollHeight;
}

function chatAdd() {
  const t = el("chatInput").value.trim();
  if (!t) return;
  addChatMsg("user", t);
  el("chatInput").value = "";
  el("chatStatus").textContent = "";
}

function parseAI(text) {
  if (!text) return null;
  const m = text.match(/\{[\s\S]*\}/);
  if (!m) return null;
  try { return JSON.parse(m[0]); } catch (e) { return null; }
}

function applyAI(j) {
  if (j.number) el("number").value = String(j.number);
  if (j.date) el("date").value = j.date;
  if (j.client) el("client").value = j.client;
  if (Array.isArray(j.addr) && j.addr.length) {
    // Si le modèle renvoie plus de 2 éléments, fusionner les derniers (ville + code postal)
    let a = j.addr.map(s => String(s).trim()).filter(Boolean);
    while (a.length > 2) a.splice(a.length - 2, 2, a[a.length - 2] + " " + a[a.length - 1]);
    el("addr").value = a.join("\n");
  }
  if (Array.isArray(j.title) && j.title.length) el("title").value = j.title.join("\n");
  if (Array.isArray(j.lines) && j.lines.length) {
    state.lines = j.lines.map(l => ({
      d: String(l.desc || ""),
      n: String(l.note || ""),
      q: String(l.qty == null ? 1 : l.qty),
      a: String(l.amount == null ? "" : l.amount)
    }));
    renderLines();
  }
}

async function chatFill() {
  const userMsgs = [];
  el("chatMsgs").querySelectorAll(".msg.user").forEach(m => userMsgs.push(m.textContent));
  if (!userMsgs.length) { el("chatStatus").textContent = "Écrivez d'abord la facture dans le chat."; return; }
  el("chatFill").disabled = true;
  el("chatStatus").textContent = "Interprétation en cours (modèle local)…";
  try {
    const r = await api("/api/assistant", {
      method: "POST",
      body: JSON.stringify({ messages: userMsgs, today: today() })
    });
    const j = parseAI(r.text);
    if (!j) throw new Error("réponse illisible");
    applyAI(j);
    const total = state.lines.reduce((s, l) => s + (parseFloat(l.a) || 0), 0);
    addChatMsg("ai", "Formulaire rempli." + (total ? " Total : " + fmtTotal(total) : "") +
      " Vérifiez la date, le numéro et le code postal avant de générer.");
    el("chatStatus").textContent = "Formulaire rempli.";
  } catch (e) {
    addChatMsg("ai", "Je n'ai pas réussi à interpréter le message : " + e.message);
    el("chatStatus").textContent = "Échec de l'interprétation.";
  } finally {
    el("chatFill").disabled = false;
  }
}

init();
