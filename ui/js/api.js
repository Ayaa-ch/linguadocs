/* LinguaDocs — couche API (fetch JWT + SSE /ask + documents + history + tools).
   Même origine quand la page est servie par FastAPI (:8000) ;
   sinon repli sur http://localhost:8000 (CORS autorisé côté backend). */

const LD = (() => {
  const API_BASE =
    typeof window.LD_API_BASE !== "undefined"
      ? window.LD_API_BASE
      : String(location.port) === "8000"
        ? ""
        : "http://localhost:8000";
  const TOKEN_KEY = "linguadocs_token";
  const EMAIL_KEY = "linguadocs_email";

  function getToken() {
    try { return localStorage.getItem(TOKEN_KEY); } catch (e) { return null; }
  }
  function getEmail() {
    try { return localStorage.getItem(EMAIL_KEY); } catch (e) { return null; }
  }
  function setSession(token, email) {
    try {
      localStorage.setItem(TOKEN_KEY, token);
      localStorage.setItem(EMAIL_KEY, email);
    } catch (e) { /* stockage indisponible */ }
  }
  function clearSession() {
    try {
      localStorage.removeItem(TOKEN_KEY);
      localStorage.removeItem(EMAIL_KEY);
    } catch (e) { /* ignore */ }
  }
  function logout() {
    clearSession();
    location.href = "index.html";
  }
  function requireAuth() {
    if (!getToken()) {
      location.href = "index.html";
      return false;
    }
    return true;
  }

  function isEmailValid(email) {
    return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(String(email || "").trim());
  }

  class ApiError extends Error {
    constructor(message, status, data) {
      super(message);
      this.name = "ApiError";
      this.status = status;
      this.data = data || null;
    }
  }

  function extractDetail(data, fallback) {
    if (data == null) return fallback;
    if (typeof data === "string" && data) return data;
    const d = data.detail;
    if (typeof d === "string" && d) return d;
    if (Array.isArray(d) && d.length)
      return d.map((x) => (x && x.msg) || JSON.stringify(x)).join(" ; ");
    return fallback;
  }

  async function apiCall(path, options) {
    options = options || {};
    const headers = Object.assign({}, options.headers || {});
    if (!(options.body instanceof FormData) && !headers["Content-Type"] && options.body !== undefined) {
      headers["Content-Type"] = "application/json";
    }
    const token = getToken();
    if (token) headers["Authorization"] = "Bearer " + token;

    let res;
    try {
      res = await fetch(API_BASE + path, Object.assign({}, options, { headers }));
    } catch (e) {
      throw new ApiError("Backend injoignable (uvicorn lancé sur :8000 ?)", 0, null);
    }

    if (res.status === 401 && token) {
      clearSession();
      throw new ApiError("Session expirée, reconnectez-vous.", 401, null);
    }

    let data = null;
    const ct = res.headers.get("content-type") || "";
    try {
      data = ct.includes("application/json") ? await res.json() : await res.text();
    } catch (e) { data = null; }

    if (!res.ok) {
      throw new ApiError(extractDetail(data, "HTTP " + res.status), res.status, data);
    }
    return data;
  }

  function authHeaders() {
    const token = getToken();
    return token ? { Authorization: "Bearer " + token } : {};
  }

  /* ------------------------------------------------------------- auth */
  async function login(email, password) {
    const data = await apiCall("/auth/login", {
      method: "POST",
      body: JSON.stringify({ email, password }),
    });
    setSession(data.access_token, String(email).trim().toLowerCase());
    return data.access_token;
  }
  async function register(email, password) {
    return apiCall("/auth/register", {
      method: "POST",
      body: JSON.stringify({ email, password }),
    });
  }
  async function deleteAccount() {
    await apiCall("/me", { method: "DELETE" });
    clearSession();
  }

  /* -------------------------------------------------------- documents */
  function listDocuments() { return apiCall("/documents", { method: "GET" }); }
  function getDocument(id) { return apiCall("/documents/" + id, { method: "GET" }); }
  function deleteDocument(id) { return apiCall("/documents/" + id, { method: "DELETE" }); }
  function uploadDocument(file) {
    const fd = new FormData();
    fd.append("file", file, file.name);
    return apiCall("/documents", { method: "POST", body: fd });
  }
  function getPages(id) { return apiCall("/documents/" + id + "/pages", { method: "GET" }); }
  function getChunks(id) { return apiCall("/documents/" + id + "/chunks", { method: "GET" }); }

  /* ---------------------------------------------------------- history */
  function getHistory(docId) {
    return apiCall("/history?doc_id=" + encodeURIComponent(docId) + "&limit=200", { method: "GET" });
  }
  function saveMessage(docId, role, content, extra) {
    extra = extra || {};
    return apiCall("/history", {
      method: "POST",
      body: JSON.stringify({
        doc_id: docId,
        role: role, // "user" | "bot"
        content: String(content).slice(0, 8000),
        sources: extra.sources || [],
        question_lang: extra.question_lang || null,
        refused: !!extra.refused,
      }),
    });
  }
  function clearHistory(docId) {
    return apiCall("/history?doc_id=" + encodeURIComponent(docId), { method: "DELETE" });
  }

  /* ---------------------------------------------------------------- ask
     POST /ask stream=true — lit response.body et yield chaque événement :
     {type:"meta", sources, question_lang, refused, latency_ms}
     {type:"token", token} | {type:"latency", latency_ms} | {type:"error", error}
     Refus / question vide : le backend répond en JSON même avec stream=true. */
  async function streamAsk(opts) {
    const onEvent = opts.onEvent;
    let res;
    try {
      res = await fetch(API_BASE + "/ask", {
        method: "POST",
        headers: Object.assign({ "Content-Type": "application/json" }, authHeaders()),
        body: JSON.stringify({
          question: opts.question,
          doc_id: opts.docId || null,
          stream: true,
        }),
        signal: opts.signal,
      });
    } catch (e) {
      if (e && e.name === "AbortError") return;
      throw new ApiError("Backend injoignable (uvicorn lancé sur :8000 ?)", 0, null);
    }
    if (!res.ok) {
      let detail = "HTTP " + res.status;
      try { detail = extractDetail(await res.json(), detail); } catch (e) { /* ignore */ }
      throw new ApiError(detail, res.status, null);
    }

    const contentType = res.headers.get("content-type") || "";
    if (contentType.includes("application/json")) {
      const data = await res.json();
      if (data.answer) onEvent({ type: "token", token: data.answer });
      onEvent({
        type: "meta",
        sources: data.sources || [],
        question_lang: data.question_lang,
        refused: !!data.refused,
        latency_ms: data.latency_ms,
      });
      onEvent({ type: "done" });
      return;
    }
    if (!res.body) throw new ApiError("Streaming non supporté par ce navigateur", 0, null);

    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";

    function parseBlock(block) {
      block.split(/\r?\n/).forEach((rawLine) => {
        const line = rawLine.trim();
        if (!line.startsWith("data:")) return;
        const payload = line.slice(5).trim();
        if (payload === "[DONE]") { onEvent({ type: "done" }); return; }
        let data;
        try { data = JSON.parse(payload); } catch (e) { return; }
        if (typeof data.error === "string") onEvent({ type: "error", error: data.error });
        else if (typeof data.token === "string") onEvent({ type: "token", token: data.token });
        else if (Array.isArray(data.sources))
          onEvent({
            type: "meta",
            sources: data.sources,
            question_lang: data.question_lang,
            refused: !!data.refused,
            latency_ms: data.latency_ms,
          });
        else if (data.latency_ms) onEvent({ type: "latency", latency_ms: data.latency_ms });
      });
    }

    try {
      while (true) {
        const { value, done } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        let idx;
        while ((idx = buffer.search(/\r?\n\r?\n/)) !== -1) {
          const m = buffer.slice(idx).match(/^\r?\n\r?\n/);
          const sep = m ? m[0].length : 2;
          parseBlock(buffer.slice(0, idx));
          buffer = buffer.slice(idx + sep);
        }
      }
      if (buffer.trim()) parseBlock(buffer);
    } catch (e) {
      if (e && e.name === "AbortError") return;
      throw e;
    }
  }

  /* ------------------------------------------------------------- tools */
  function summarize(body) { return apiCall("/summary", { method: "POST", body: JSON.stringify(body) }); }
  function quiz(body) { return apiCall("/quiz", { method: "POST", body: JSON.stringify(body) }); }
  function flashcards(body) { return apiCall("/flashcards", { method: "POST", body: JSON.stringify(body) }); }
  function translate(body) { return apiCall("/translate", { method: "POST", body: JSON.stringify(body) }); }

  /* --------------------------------------------------------- utilitaires */
  function esc(s) {
    return String(s == null ? "" : s)
      .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;").replace(/'/g, "&#39;");
  }
  // chunk_key backend = "{doc_id}#{idx}" → index entier
  function chunkIndexOf(chunkKey) {
    const n = Number.parseInt(String(chunkKey || "").split("#").pop(), 10);
    return Number.isFinite(n) ? n : 0;
  }
  function normalizeWs(s) {
    return String(s || "").replace(/\s+/g, " ").trim();
  }

  /* Icônes Lucide (SVG inline, currentColor, 16px par défaut).
     Remplacent tous les emojis de l'UI. */
  const ICONS = {
    bookOpen: '<path d="M12 7v14"/><path d="M3 18a1 1 0 0 1-1-1V4a1 1 0 0 1 1-1h5a4 4 0 0 1 4 4 4 4 0 0 1 4-4h5a1 1 0 0 1 1 1v13a1 1 0 0 1-1 1h-6a3 3 0 0 0-3 3 3 3 0 0 0-3-3z"/>',
    helpCircle: '<circle cx="12" cy="12" r="10"/><path d="M9.09 9a3 3 0 0 1 5.83 1c0 2-3 3-3 3"/><path d="M12 17h.01"/>',
    layers: '<path d="m12.83 2.18a2 2 0 0 0-1.66 0L2.6 6.08a1 1 0 0 0 0 1.83l8.58 3.91a2 2 0 0 0 1.66 0l8.58-3.9a1 1 0 0 0 0-1.83Z"/><path d="m22 17.65-9.17 4.16a2 2 0 0 1-1.66 0L2 17.65"/><path d="m22 12.65-9.17 4.16a2 2 0 0 1-1.66 0L2 12.65"/>',
    rotateCcw: '<path d="M3 12a9 9 0 1 0 9-9 9.75 9.75 0 0 0-6.74 2.74L3 8"/><path d="M3 3v5h5"/>',
    rotateCw: '<path d="M21 12a9 9 0 1 1-9-9 9.75 9.75 0 0 1 6.74 2.74L21 8"/><path d="M21 3v5h-5"/>',
    fileText: '<path d="M15 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7Z"/><path d="M14 2v4a2 2 0 0 0 2 2h4"/><path d="M10 9H8"/><path d="M16 13H8"/><path d="M16 17H8"/>',
    sparkles: '<path d="m12 3-1.9 5.8a2 2 0 0 1-1.3 1.3L3 12l5.8 1.9a2 2 0 0 1 1.3 1.3L12 21l1.9-5.8a2 2 0 0 1 1.3-1.3L21 12l-5.8-1.9a2 2 0 0 1-1.3-1.3Z"/><path d="M5 3v4"/><path d="M19 17v4"/><path d="M3 5h4"/><path d="M17 19h4"/>',
    moon: '<path d="M12 3a6 6 0 0 0 9 9 9 9 0 1 1-9-9Z"/>',
    sun: '<circle cx="12" cy="12" r="4"/><path d="M12 2v2"/><path d="M12 20v2"/><path d="m4.93 4.93 1.41 1.41"/><path d="m17.66 17.66 1.41 1.41"/><path d="M2 12h2"/><path d="M20 12h2"/><path d="m6.34 17.66-1.41 1.41"/><path d="m19.07 4.93-1.41 1.41"/>',
    user: '<path d="M19 21v-2a4 4 0 0 0-4-4H9a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/>',
    logOut: '<path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"/><path d="m16 17 5-5-5-5"/><path d="M21 12H9"/>',
    search: '<circle cx="11" cy="11" r="8"/><path d="m21 21-4.3-4.3"/>',
    upload: '<path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><path d="M17 8l-5-5-5 5"/><path d="M12 3v12"/>',
    messageSquare: '<path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/>',
    lock: '<rect width="18" height="11" x="3" y="11" rx="2" ry="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/>',
    trash2: '<path d="M3 6h18"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6"/><path d="M8 6V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/><path d="M10 11v6"/><path d="M14 11v6"/>',
    copy: '<rect width="14" height="14" x="8" y="8" rx="2" ry="2"/><path d="M4 16c-1.1 0-2-.9-2-2V4c0-1.1.9-2 2-2h10c1.1 0 2 .9 2 2"/>',
    zap: '<path d="M4 14a1 1 0 0 1-.78-1.63l9.9-10.2a.5.5 0 0 1 .86.46l-1.92 6.02A1 1 0 0 0 13 10h7a1 1 0 0 1 .78 1.63l-9.9 10.2a.5.5 0 0 1-.86-.46l1.92-6.02A1 1 0 0 0 11 14z"/>',
    lightbulb: '<path d="M15 14c.2-1 .7-1.7 1.5-2.5 1-.9 1.5-2.2 1.5-3.5A6 6 0 0 0 6 8c0 1 .2 2.2 1.5 3.5.7.7 1.3 1.5 1.5 2.5"/><path d="M9 18h6"/><path d="M10 22h4"/>',
    alertTriangle: '<path d="m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3"/><path d="M12 9v4"/><path d="M12 17h.01"/>',
    check: '<path d="M20 6 9 17l-5-5"/>',
    checkCircle: '<path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/><path d="m9 11 3 3L22 4"/>',
    play: '<polygon points="6 3 20 12 6 21 6 3"/>',
  };
  function icon(name, size) {
    const body = ICONS[name] || "";
    const s = size || 16;
    return '<svg class="lucide" width="' + s + '" height="' + s + '" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">' + body + "</svg>";
  }

  /* Retire tous les emojis (Extended_Pictographic) + ZWJ/VS16 résiduels.
     Appliqué avant affichage des textes générés (chatbot, outils). */
  function stripEmojis(s) {
    return String(s == null ? "" : s)
      .replace(/\p{Extended_Pictographic}/gu, "")
      .replace(/[\uFE0F\u200D]/g, "")
      .replace(/[ \t]{2,}/g, " ");
  }

  return {
    API_BASE, getToken, getEmail, setSession, clearSession, logout, requireAuth,
    isEmailValid, ApiError, apiCall, login, register, deleteAccount,
    listDocuments, getDocument, deleteDocument, uploadDocument, getPages, getChunks,
    getHistory, saveMessage, clearHistory, streamAsk,
    summarize, quiz, flashcards, translate,
    esc, chunkIndexOf, normalizeWs, icon, stripEmojis,
  };
})();
