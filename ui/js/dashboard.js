/* LinguaDocs — workspace (app.html) : documents, chat SSE, viewer, dialogs.
   Upload + polling de l'indexation, watchdog SSE, viewer avec surlignage. */

(function () {
  if (!LD.requireAuth()) return;

  const $ = (id) => document.getElementById(id);
  const $$ = (sel) => Array.from(document.querySelectorAll(sel));

  // ---------------------------------------------------------------- état
  let lang = localStorage.getItem("LD_LANG") || "en";
  let docs = [];
  let activeDocId = null;
  let historyLoaded = new Set();
  let historyCache = {}; // docId -> [{role, content, sources, refused, latency_ms}]
  let streaming = false;
  let abortCtrl = null;
  let refreshTimer = null;
  const pageCache = {};
  const chunkCache = {};

  // quiz / flashcards
  let quizState = null; // {questions, answers, submitted}
  let flashState = null; // {cards, idx, known, review}

  const t = (key) => LDI.t(key, lang);

  // ------------------------------------------------------------- thème/i18n
  function applyTheme(theme) {
    document.documentElement.classList.toggle("light", theme === "light");
    $("theme-toggle").innerHTML = theme === "light" ? LD.icon("sun") : LD.icon("moon");
  }
  applyTheme(localStorage.getItem("LD_THEME") || "dark");
  LDI.applyI18n(lang);
  $("lang-select").value = lang;
  $("user-email").textContent = LD.getEmail() || "";

  $("lang-select").addEventListener("change", (e) => {
    lang = e.target.value;
    localStorage.setItem("LD_LANG", lang);
    LDI.applyI18n(lang);
    renderDocs();
    updateChatHeader();
    renderMessages();
  });
  $("theme-toggle").addEventListener("click", () => {
    const next = document.documentElement.classList.contains("light") ? "dark" : "light";
    localStorage.setItem("LD_THEME", next);
    applyTheme(next);
  });
  $("btn-logout").addEventListener("click", () => LD.logout());
  $("btn-home").addEventListener("click", () => showHero());

  // ------------------------------------------------------------- utilitaires
  function toast(msg, kind) {
    const el = $("toast");
    el.textContent = msg;
    el.className = "toast " + (kind || "");
    clearTimeout(el._timer);
    el._timer = setTimeout(() => el.classList.add("hidden"), 5000);
  }
  function onApiError(err) {
    if (err && err.status === 0) {
      const banner = $("api-banner");
      banner.classList.add("show");
      setTimeout(() => banner.classList.remove("show"), 4000);
    }
    toast(err && err.message ? err.message : "Erreur inattendue", "err");
    if (err && err.status === 401) LD.logout();
  }
  function esc(s) { return LD.esc(s); }
  function now() {
    return new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
  }

  // ------------------------------------------------------------ dialogs
  function openDialog(id) { $(id).classList.remove("hidden"); }
  function closeDialogs() { $$(".overlay").forEach((o) => o.classList.add("hidden")); }
  $$(".dlg-close").forEach((b) => b.addEventListener("click", closeDialogs));
  $$(".overlay").forEach((o) =>
    o.addEventListener("click", (e) => { if (e.target === o) closeDialogs(); })
  );
  $$(".seg").forEach((seg) =>
    seg.addEventListener("click", (e) => {
      const btn = e.target.closest("button[data-val]");
      if (!btn) return;
      seg.querySelectorAll("button").forEach((b) => b.classList.remove("active"));
      btn.classList.add("active");
    })
  );
  const segVal = (id) => $(id).querySelector("button.active").dataset.val;
  function alertBox(id, msg, ok) {
    const el = $(id);
    if (!msg) { el.classList.add("hidden"); return; }
    el.textContent = msg;
    el.className = "alert " + (ok ? "ok" : "err");
  }

  // ------------------------------------------------------------- documents
  function iconFor(doc) {
    return LD.icon("fileText", 15);
  }
  function isBusy(doc) { return doc.status === "queued" || doc.status === "processing"; }

  async function loadDocs() {
    try {
      docs = (await LD.listDocuments()) || [];
      if (activeDocId && !docs.some((d) => d.id === activeDocId)) activeDocId = null;
      if (!activeDocId && docs.length) activeDocId = docs[0].id;
      renderDocs();
      updateChatHeader();
      if (activeDocId) showWorkspace(); else showHero();
      scheduleRefresh();
    } catch (e) { onApiError(e); }
  }

  function scheduleRefresh() {
    if (refreshTimer) { clearInterval(refreshTimer); refreshTimer = null; }
    if (!docs.some(isBusy)) return;
    refreshTimer = setInterval(async () => {
      try {
        docs = (await LD.listDocuments()) || [];
        renderDocs();
        updateChatHeader();
        if (!docs.some(isBusy)) { clearInterval(refreshTimer); refreshTimer = null; }
      } catch (e) { /* silencieux pendant le polling */ }
    }, 2500);
  }

  function statusBadge(doc) {
    const map = {
      indexed: '<span class="badge indexed"><span class="dot"></span>' + t("docs_status_indexed") + "</span>",
      processing: '<span class="badge processing"><span class="spinner"></span>' + t("docs_status_processing") + "</span>",
      queued: '<span class="badge queued"><span class="dot"></span>' + t("docs_status_queued") + "</span>",
      error: '<span class="badge error"><span class="dot"></span>' + t("docs_status_error") + "</span>",
    };
    return map[doc.status] || "";
  }

  function renderDocs() {
    const q = ($("doc-search").value || "").toLowerCase().trim();
    const list = docs.filter((d) => (d.filename || "").toLowerCase().includes(q));
    $("docs-count").textContent = String(list.length);
    const box = $("doc-list");
    if (!list.length) {
      box.innerHTML = '<div style="padding:24px; text-align:center; font-size:12px; color:var(--text-secondary)">' +
        esc(q ? t("docs_no_match") : t("docs_no_documents")) + "</div>";
      return;
    }
    box.innerHTML = list.map((d) => {
      const pages = d.n_pages ? `<span>${d.n_pages} p</span>` : "";
      const err = d.status === "error" && d.error ? `<span style="color:var(--err)" title="${esc(d.error)}">${LD.icon("alertTriangle", 13)}</span>` : "";
      return `<div class="doc-item ${d.id === activeDocId ? "active" : ""}" data-id="${esc(d.id)}">
        <div class="doc-row">
          <div class="doc-name-wrap"><span>${iconFor(d)}</span><span class="doc-name" title="${esc(d.filename)}">${esc(d.filename)}</span></div>
          <button class="doc-del" data-del="${esc(d.id)}" title="${t("delete")}">${LD.icon("trash2", 14)}</button>
        </div>
        <div class="doc-meta">${statusBadge(d)}<div class="doc-meta-right">${pages}${err}</div></div>
      </div>`;
    }).join("");
  }

  $("doc-list").addEventListener("click", async (e) => {
    const del = e.target.closest("button[data-del]");
    if (del) {
      e.stopPropagation();
      if (!confirm(t("docs_delete_confirm"))) return;
      try {
        await LD.deleteDocument(del.dataset.del);
        docs = docs.filter((d) => d.id !== del.dataset.del);
        delete historyCache[del.dataset.del];
        historyLoaded.delete(del.dataset.del);
        if (activeDocId === del.dataset.del) activeDocId = docs.length ? docs[0].id : null;
        renderDocs();
        updateChatHeader();
        if (activeDocId) showWorkspace(); else showHero();
        toast(t("delete") + " ✓", "ok");
      } catch (err) { onApiError(err); }
      return;
    }
    const item = e.target.closest(".doc-item");
    if (item) selectDoc(item.dataset.id);
  });
  $("doc-search").addEventListener("input", renderDocs);
  $("btn-refresh").addEventListener("click", loadDocs);

  function selectDoc(id) {
    activeDocId = id;
    renderDocs();
    updateChatHeader();
    showWorkspace();
    closeViewer();
    loadHistoryOnce(id);
  }

  function activeDoc() { return docs.find((d) => d.id === activeDocId) || null; }

  function updateChatHeader() {
    const doc = activeDoc();
    if (!doc) return;
    $("chat-doc-name").textContent = doc.filename;
    $("chat-doc-pages").textContent = doc.n_pages ? doc.n_pages + " pages" : "";
    $("chat-doc-status").outerHTML = statusBadge(doc).replace('class="badge', 'id="chat-doc-status" class="badge');
  }

  function showWorkspace() {
    $("hero").classList.add("hidden");
    $("messages").classList.remove("hidden");
    $("chat-header").classList.remove("hidden");
    renderMessages();
  }
  function showHero() {
    activeDocId = null;
    renderDocs();
    $("hero").classList.remove("hidden");
    $("messages").classList.add("hidden");
    $("chat-header").classList.add("hidden");
    closeViewer();
  }

  // ------------------------------------------------------------- historique
  async function loadHistoryOnce(docId) {
    if (historyLoaded.has(docId)) { renderMessages(); return; }
    const doc = docs.find((d) => d.id === docId);
    try {
      const rows = (await LD.getHistory(docId)) || [];
      historyCache[docId] = rows.map((m) => ({
        role: m.role === "bot" ? "bot" : "user",
        content: m.content,
        sources: m.sources || [],
        refused: !!m.refused,
        question_lang: m.question_lang,
        latency_ms: null,
      }));
      historyLoaded.add(docId);
    } catch (e) {
      historyCache[docId] = historyCache[docId] || [];
      onApiError(e);
    }
    if (doc) renderMessages();
  }

  function renderMessages() {
    const box = $("messages");
    const msgs = historyCache[activeDocId] || [];
    if (!msgs.length) {
      box.innerHTML = `<div style="margin:auto; text-align:center; color:var(--text-secondary); max-width:480px">
        <div style="font-size:28px; margin-bottom:8px">${LD.icon("sparkles", 26)}</div>
        <h3 class="font-heading" style="font-size:16px; color:var(--text-primary); margin-bottom:6px">${esc(t("welcome_heading"))}</h3>
        <p style="font-size:12px">${esc(t("chat_placeholder"))}</p>
      </div>`;
      return;
    }
    box.innerHTML = msgs.map((m, i) => bubbleHtml(m, i)).join("");
    box.scrollTop = box.scrollHeight;
  }

  function bubbleHtml(m, idx) {
    if (m.role === "user") {
      return `<div class="msg user"><div class="bubble">${esc(m.content)}</div></div>`;
    }
    const sources = (m.sources || []).map((s) => {
      const page = s.page != null ? s.page : "?";
      return `<button class="cite-chip" data-src="${idx}">${LD.icon("fileText", 13)} ${esc(s.filename || activeDoc()?.filename || "")} · p.${esc(page)}</button>`;
    }).join("");
    const refusal = m.refused
      ? `<div class="refusal"><b>${LD.icon("alertTriangle", 14)} ${esc(t("chat_refusal_banner"))}</b></div>` : "";
    const latency = m.latency_ms
      ? `<span class="latency">${LD.icon("zap", 13)} ${Math.round(m.latency_ms)} ms</span>` : "";
    return `<div class="msg bot"><div class="bubble">
      ${refusal}<div>${esc(LD.stripEmojis(m.content)) || '<span class="typing"><i></i><i></i><i></i></span>'}</div>
      ${sources ? `<div class="sources"><div class="sources-title">${esc(t("chat_sources_label"))}</div><div class="sources-row">${sources}</div></div>` : ""}
      <div class="msg-meta"><span>${latency}<span style="margin-inline-start:${latency ? "8px" : "0"}">${esc(m.timestamp || "")}</span></span>
        <button class="copy-btn" data-copy="${idx}" title="${t("copy")}">${LD.icon("copy", 13)}</button></div>
    </div></div>`;
  }

  $("messages").addEventListener("click", (e) => {
    const cite = e.target.closest(".cite-chip");
    if (cite) {
      const m = (historyCache[activeDocId] || [])[Number(cite.dataset.src)];
      if (m && m.sources && m.sources.length) {
        const s = m.sources[Number(cite.dataset.src != null ? 0 : 0)] || m.sources[0];
        // index de la source cliquée : on retrouve via l'ordre des chips
        const chips = Array.from(cite.parentElement.querySelectorAll(".cite-chip"));
        const i = chips.indexOf(cite);
        openViewer(m.sources[i] || s);
      }
      return;
    }
    const copy = e.target.closest(".copy-btn");
    if (copy) {
      const m = (historyCache[activeDocId] || [])[Number(copy.dataset.copy)];
      if (m) navigator.clipboard.writeText(m.content || "");
    }
  });

  // ------------------------------------------------------------------ chat
  function setStreamingUI(on) {
    streaming = on;
    $("btn-stop").classList.toggle("hidden", !on);
    $("btn-send").classList.toggle("hidden", on);
    $("question-input").disabled = on;
  }

  async function sendQuestion(question) {
    if (streaming || !activeDocId) return;
    const docId = activeDocId;
    const doc = activeDoc();
    const msgs = historyCache[docId] = historyCache[docId] || [];
    msgs.push({ role: "user", content: question, sources: [], timestamp: now() });
    msgs.push({ role: "bot", content: "", sources: [], timestamp: now(), _pending: true });
    renderMessages();
    setStreamingUI(true);

    const botMsg = msgs[msgs.length - 1];
    abortCtrl = new AbortController();
    let streamError = null;

    try {
      await LD.streamAsk({
        question,
        docId,
        signal: abortCtrl.signal,
        onEvent(ev) {
          if (ev.type === "token") {
            botMsg._pending = false;
            botMsg.content += ev.token;
            updateLastBubble();
          } else if (ev.type === "meta") {
            botMsg.refused = ev.refused;
            botMsg.sources = (ev.sources || []).map((s) => ({
              chunk_key: s.chunk_key,
              filename: s.filename || (doc && doc.filename) || "",
              page: s.page,
              score: s.score,
              text: s.text,
            }));
            botMsg.question_lang = ev.question_lang;
            if (ev.latency_ms && ev.latency_ms.total) botMsg.latency_ms = ev.latency_ms.total;
          } else if (ev.type === "latency") {
            if (ev.latency_ms && ev.latency_ms.total) botMsg.latency_ms = ev.latency_ms.total;
          } else if (ev.type === "error") {
            streamError = ev.error;
          }
        },
      });
    } catch (e) {
      if (e && e.status === 401) return LD.logout();
      streamError = e && e.message ? e.message : "Streaming failed";
    } finally {
      setStreamingUI(false);
      abortCtrl = null;
    }

    botMsg._pending = false;
    if (streamError) {
      botMsg.content = (botMsg.content ? botMsg.content + "\n\n" : "") + LD.stripEmojis(streamError);
      toast(streamError, "err");
    }
    updateLastBubble();

    // persistance (best-effort)
    try {
      await LD.saveMessage(docId, "user", question, { question_lang: botMsg.question_lang });
      await LD.saveMessage(docId, "bot", botMsg.content, {
        sources: botMsg.sources || [],
        question_lang: botMsg.question_lang,
        refused: !!botMsg.refused,
      });
    } catch (e) { /* on n'altère pas l'UI pour l'historique */ }
  }

  function updateLastBubble() {
    const box = $("messages");
    const last = box.querySelector(".msg.bot:last-of-type .bubble");
    if (!last) { renderMessages(); return; }
    const msgs = historyCache[activeDocId] || [];
    const m = msgs[msgs.length - 1];
    last.innerHTML = bubbleInner(m);
    box.scrollTop = box.scrollHeight;
  }
  function bubbleInner(m) {
    const tmp = document.createElement("div");
    tmp.innerHTML = bubbleHtml(m, (historyCache[activeDocId] || []).length - 1);
    const bubble = tmp.querySelector(".bubble");
    return bubble ? bubble.innerHTML : esc(m.content || "");
  }

  $("ask-form").addEventListener("submit", (e) => {
    e.preventDefault();
    const q = $("question-input").value.trim();
    if (!q || !activeDocId) return;
    $("question-input").value = "";
    sendQuestion(q);
  });
  $("btn-stop").addEventListener("click", () => {
    if (abortCtrl) abortCtrl.abort();
    setStreamingUI(false);
  });
  $("btn-clear").addEventListener("click", async () => {
    if (!activeDocId) return;
    historyCache[activeDocId] = [];
    renderMessages();
    try { await LD.clearHistory(activeDocId); } catch (e) { /* ignore */ }
  });
  $("btn-home").addEventListener("click", showHero);
  $$(".eg-item").forEach((el) =>
    el.addEventListener("click", () => {
      if (docs.length) selectDoc(docs[0].id);
      else openDialog("dlg-upload");
    })
  );

  // --------------------------------------------------------------- viewer
  function closeViewer() { $("viewer").classList.add("hidden"); }
  $("btn-close-viewer").addEventListener("click", closeViewer);

  function normWs(s) { return LD.normalizeWs(s); }

  async function openViewer(source) {
    if (!activeDocId) return;
    const body = $("viewer-body");
    $("viewer").classList.remove("hidden");
    body.innerHTML = '<p class="label">…</p>';

    const score = source.score != null ? (source.score * 100).toFixed(1) + " %" : "—";
    const chunkIdx = LD.chunkIndexOf(source.chunk_key);
    let html = `<div class="viewer-meta">
      <span>${t("viewer_page")}: <b>${esc(source.page != null ? source.page : "?")}</b></span>
      <span>${t("viewer_chunk")}: <b>#${chunkIdx}</b></span>
      <span>${t("viewer_score")}: <b>${score}</b></span>
      <span>${LD.icon("fileText", 13)} <b>${esc(source.filename || "")}</b></span>
    </div>`;

    try {
      if (!pageCache[activeDocId]) pageCache[activeDocId] = await LD.getPages(activeDocId);
      const pages = (pageCache[activeDocId].pages || []);
      const needle = normWs(source.text).slice(0, 80);
      let page = pages.find((p) => normWs(p.text).includes(needle)) || pages.find((p) => p.page === source.page);
      if (page) {
        const text = esc(page.text);
        const marked = needle
          ? text.replace(new RegExp(escapeRe(esc(source.text).slice(0, 60)), "i"), (m) => `<mark>${m}</mark>`)
          : text;
        html += `<div class="label">${t("viewer_page")} ${page.page}</div><div>${marked}</div>`;
      } else {
        html += `<div>${esc(source.text || t("viewer_no_source"))}</div>`;
      }
    } catch (e) {
      html += `<div>${esc(source.text || "")}</div>`;
      if (e && e.status === 404) { /* doc supprimé */ }
    }
    body.innerHTML = html;
  }
  function escapeRe(s) { return String(s).replace(/[.*+?^${}()|[\]\\]/g, "\\$&"); }

  // --------------------------------------------------------------- upload
  let uploadFiles = [];
  $("btn-open-upload").addEventListener("click", () => {
    uploadFiles = [];
    $("file-input").value = "";
    $("upload-status").classList.add("hidden");
    $("btn-do-upload").disabled = true;
    alertBox("upload-alert", null);
    openDialog("dlg-upload");
  });
  const dz = $("dropzone");
  ["dragenter", "dragover"].forEach((ev) =>
    dz.addEventListener(ev, (e) => { e.preventDefault(); dz.classList.add("drag"); })
  );
  ["dragleave", "drop"].forEach((ev) =>
    dz.addEventListener(ev, (e) => { e.preventDefault(); dz.classList.remove("drag"); })
  );
  dz.addEventListener("drop", (e) => handleFiles(e.dataTransfer.files));
  $("file-input").addEventListener("change", (e) => handleFiles(e.target.files));

  function handleFiles(fileList) {
    alertBox("upload-alert", null);
    const allowed = [".pdf", ".txt", ".md", ".docx"];
    const files = [];
    for (const f of Array.from(fileList || [])) {
      const ext = "." + f.name.split(".").pop().toLowerCase();
      if (!allowed.includes(ext)) return alertBox("upload-alert", `"${f.name}" — formats : .pdf .txt .md .docx`);
      if (f.size > 50 * 1024 * 1024) return alertBox("upload-alert", `"${f.name}" — max 50MB`);
      if (f.size === 0) return alertBox("upload-alert", `"${f.name}" — fichier vide`);
      files.push(f);
    }
    uploadFiles = files;
    const box = $("upload-status");
    if (!files.length) { box.classList.add("hidden"); $("btn-do-upload").disabled = true; return; }
    box.classList.remove("hidden");
    box.innerHTML = `<div class="label">${files.length} fichier(s)</div>` + files.map((f) =>
      `<div class="row"><span>${esc(f.name)}</span><span>${(f.size / 1048576).toFixed(2)} MB</span></div>`
    ).join("");
    $("btn-do-upload").disabled = false;
  }

  $("btn-do-upload").addEventListener("click", async () => {
    if (!uploadFiles.length) return;
    const btn = $("btn-do-upload");
    btn.disabled = true;
    const box = $("upload-status");
    for (const f of uploadFiles) {
      try {
        box.innerHTML += `<div class="row"><span>${esc(f.name)}</span><span>…</span></div>`;
        const doc = await LD.uploadDocument(f);
        docs.unshift(doc);
        activeDocId = doc.id;
        renderDocs();
        updateChatHeader();
        showWorkspace();
        scheduleRefresh();
        pollStatus(doc.id);
      } catch (e) {
        alertBox("upload-alert", e && e.message ? e.message : "Upload failed");
        break;
      }
    }
    uploadFiles = [];
    btn.disabled = true;
    closeDialogs();
  });

  async function pollStatus(docId) {
    for (let i = 0; i < 120; i++) {
      await new Promise((r) => setTimeout(r, 1500));
      try {
        const fresh = await LD.getDocument(docId);
        const idx = docs.findIndex((d) => d.id === docId);
        if (idx >= 0) docs[idx] = fresh;
        renderDocs();
        if (activeDocId === docId) updateChatHeader();
        if (!isBusy(fresh)) return;
      } catch (e) { return; }
    }
  }

  // -------------------------------------------------------------- résumé
  $("btn-summary").addEventListener("click", () => {
    alertBox("summary-alert", null);
    $("summary-result").classList.add("hidden");
    openDialog("dlg-summary");
  });
  $("btn-summary-gen").addEventListener("click", async () => {
    const doc = activeDoc();
    if (!doc) return;
    const btn = $("btn-summary-gen");
    btn.disabled = true;
    const range = ($("summary-pages").value || "").split("-").map((x) => parseInt(x, 10));
    try {
      const res = await LD.summarize({
        doc_id: doc.id,
        length: segVal("summary-length"),
        language: lang,
        page_from: Number.isFinite(range[0]) ? range[0] : null,
        page_to: Number.isFinite(range[1]) ? range[1] : (Number.isFinite(range[0]) ? range[0] : null),
      });
      $("summary-text").textContent = LD.stripEmojis(res.summary || "");
      $("summary-bullets").innerHTML = (res.bullets || []).map((b) => `<li>${esc(LD.stripEmojis(b))}</li>`).join("");
      $("summary-sources").textContent = (res.sources || []).map((s) => `${s.filename} · p.${s.page}`).join("  |  ");
      $("summary-result").classList.remove("hidden");
    } catch (e) {
      alertBox("summary-alert", e && e.message ? e.message : "Summary failed");
    } finally { btn.disabled = false; }
  });

  // ----------------------------------------------------------------- quiz
  $("btn-quiz").addEventListener("click", () => {
    quizState = null;
    alertBox("quiz-alert", null);
    $("quiz-setup").classList.remove("hidden");
    $("quiz-play").classList.add("hidden");
    $("btn-quiz-gen").classList.remove("hidden");
    $("btn-quiz-submit").classList.add("hidden");
    openDialog("dlg-quiz");
  });
  $("btn-quiz-gen").addEventListener("click", async () => {
    const doc = activeDoc();
    if (!doc) return;
    const btn = $("btn-quiz-gen");
    btn.disabled = true;
    try {
      const res = await LD.quiz({
        doc_id: doc.id,
        n_questions: parseInt($("quiz-count").value, 10) || 3,
        difficulty: segVal("quiz-diff"),
        language: lang,
      });
      quizState = { questions: res.questions || [], answers: {}, submitted: false };
      $("quiz-setup").classList.add("hidden");
      $("btn-quiz-gen").classList.add("hidden");
      $("btn-quiz-submit").classList.remove("hidden");
      renderQuiz();
    } catch (e) {
      alertBox("quiz-alert", e && e.message ? e.message : "Quiz failed");
    } finally { btn.disabled = false; }
  });
  function renderQuiz() {
    const box = $("quiz-play");
    box.classList.remove("hidden");
    const qs = quizState.questions;
    let html = "";
    if (quizState.submitted) {
      const score = qs.reduce((n, q, i) => n + (quizState.answers[i] === q.correct ? 1 : 0), 0);
      html += `<div class="quiz-score">${t("dialog_quiz_score")} ${score} / ${qs.length} (${Math.round((score / qs.length) * 100)}%)</div>`;
    }
    qs.forEach((q, i) => {
      html += `<div style="margin-bottom:14px"><div class="quiz-q">${i + 1}. ${esc(LD.stripEmojis(q.question))}</div>`;
      Object.entries(q.options || {}).forEach(([letter, text]) => {
        let cls = "quiz-opt";
        if (!quizState.submitted) cls += quizState.answers[i] === letter ? " sel" : "";
        else if (letter === q.correct) cls += " good";
        else if (quizState.answers[i] === letter) cls += " bad";
        html += `<button type="button" class="${cls}" data-q="${i}" data-l="${esc(letter)}" ${quizState.submitted ? "disabled" : ""}>
          <b>${esc(letter)}</b><span>${esc(LD.stripEmojis(text))}</span></button>`;
      });
      if (quizState.submitted && q.explanation)
        html += `<div class="quiz-expl">${LD.icon("lightbulb", 13)} ${esc(LD.stripEmojis(q.explanation))}</div>`;
      html += "</div>";
    });
    box.innerHTML = html;
    box.querySelectorAll(".quiz-opt").forEach((btn) =>
      btn.addEventListener("click", () => {
        quizState.answers[Number(btn.dataset.q)] = btn.dataset.l;
        renderQuiz();
      })
    );
  }
  $("btn-quiz-submit").addEventListener("click", () => {
    if (!quizState) return;
    quizState.submitted = true;
    $("btn-quiz-submit").classList.add("hidden");
    renderQuiz();
  });

  // ---------------------------------------------------------- flashcards
  $("btn-flashcards").addEventListener("click", () => {
    flashState = null;
    alertBox("flash-alert", null);
    $("flash-setup").classList.remove("hidden");
    $("flash-play").classList.add("hidden");
    $("btn-flash-gen").classList.remove("hidden");
    openDialog("dlg-flash");
  });
  $("btn-flash-gen").addEventListener("click", async () => {
    const doc = activeDoc();
    if (!doc) return;
    const btn = $("btn-flash-gen");
    btn.disabled = true;
    try {
      const res = await LD.flashcards({
        doc_id: doc.id,
        n_cards: parseInt($("flash-count").value, 10) || 10,
        language: lang,
      });
      flashState = { cards: res.cards || [], idx: 0, known: 0, review: 0 };
      $("flash-setup").classList.add("hidden");
      $("btn-flash-gen").classList.add("hidden");
      $("flash-play").classList.remove("hidden");
      renderFlash();
    } catch (e) {
      alertBox("flash-alert", e && e.message ? e.message : "Flashcards failed");
    } finally { btn.disabled = false; }
  });
  function renderFlash() {
    const s = flashState;
    if (!s || !s.cards.length) return;
    if (s.idx >= s.cards.length) {
      $("flash-front").innerHTML = LD.icon("checkCircle", 28);
      $("flash-front").style.display = "flex";
      $("flash-front").style.alignItems = "center";
      $("flash-front").style.justifyContent = "center";
      $("flash-back").textContent = `${s.known} / ${s.cards.length}`;
      $("flash-progress").textContent = "Done";
      return;
    }
    const c = s.cards[s.idx];
    $("flash-card").classList.remove("flipped");
    $("flash-front").textContent = LD.stripEmojis(c.question);
    $("flash-back").textContent = LD.stripEmojis(c.answer);
    $("flash-progress").textContent = `${s.idx + 1} / ${s.cards.length}`;
    $("flash-known").textContent = String(s.known);
    $("flash-review").textContent = String(s.review);
  }
  $("flash-card").addEventListener("click", () => $("flash-card").classList.toggle("flipped"));
  $("btn-flash-known").addEventListener("click", () => { if (flashState) { flashState.known++; flashState.idx++; renderFlash(); } });
  $("btn-flash-review").addEventListener("click", () => { if (flashState) { flashState.review++; flashState.idx++; renderFlash(); } });

  // -------------------------------------------------------------- compte
  $("btn-account").addEventListener("click", () => {
    $("account-email").textContent = LD.getEmail() || "";
    $("account-confirm").value = "";
    alertBox("account-alert", null);
    openDialog("dlg-account");
  });
  $("btn-account-delete").addEventListener("click", async () => {
    if ($("account-confirm").value.trim().toUpperCase() !== "DELETE") {
      return alertBox("account-alert", "Tapez DELETE pour confirmer.");
    }
    try {
      await LD.deleteAccount();
      location.href = "index.html";
    } catch (e) {
      alertBox("account-alert", e && e.message ? e.message : "Delete failed");
    }
  });

  // ---------------------------------------------------------------- init
  loadDocs();
})();
