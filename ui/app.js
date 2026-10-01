/* LinguaDocs — fonctions communes */
const API_BASE = "http://localhost:8000";
const TOKEN_KEY = "linguadocs_token";

function getToken() {
  return localStorage.getItem(TOKEN_KEY);
}

function logout() {
  localStorage.removeItem(TOKEN_KEY);
  window.location.href = "index.html";
}

function showApiBanner(show) {
  const el = document.getElementById("api-banner");
  if (el) el.classList.toggle("show", !!show);
}

function isEmailValid(email) {
  return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email);
}

/**
 * Appel API authentifié.
 * @param {string} path ex "/documents"
 * @param {object} options fetch options
 * @returns {Promise<{ok:boolean,status:number,data:any}>}
 */
async function apiCall(path, options = {}) {
  const token = getToken();
  const headers = Object.assign({}, options.headers || {});
  // Ne pas forcer Content-Type si FormData
  if (!(options.body instanceof FormData) && !headers["Content-Type"]) {
    headers["Content-Type"] = "application/json";
  }
  if (token) headers["Authorization"] = "Bearer " + token;

  let res;
  try {
    res = await fetch(API_BASE + path, Object.assign({}, options, { headers }));
  } catch (e) {
    showApiBanner(true);
    throw new Error("network");
  }
  if (res.status === 401) {
    logout();
    throw new Error("unauthorized");
  }
  let data = null;
  const ct = res.headers.get("content-type") || "";
  try {
    data = ct.includes("application/json") ? await res.json() : await res.text();
  } catch (e) { data = null; }
  if (!res.ok) {
    const err = new Error("http-" + res.status);
    err.status = res.status;
    err.data = data;
    throw err;
  }
  showApiBanner(false);
  return data;
}

function apiErrorMessage(err, fallback) {
  if (err && err.message === "network") return "Cannot connect to API (port 8000). Make sure the server is running.";
  if (err && err.data) {
    if (typeof err.data === "string") return err.data;
    if (err.data.detail) {
      if (Array.isArray(err.data.detail)) {
        return err.data.detail.map(d => d.msg || JSON.stringify(d)).join("; ");
      }
      return err.data.detail;
    }
  }
  return fallback || "An error occurred.";
}

function requireAuth() {
  if (!getToken()) {
    window.location.href = "index.html";
    return false;
  }
  return true;
}

// Expose globals
window.LD = { API_BASE, TOKEN_KEY, getToken, logout, apiCall, apiErrorMessage, isEmailValid, requireAuth, showApiBanner };
