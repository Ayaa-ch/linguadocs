/* LinguaDocs — page de connexion (index.html) */
(function () {
  const $ = (id) => document.getElementById(id);
  const lang = localStorage.getItem("LD_LANG") || "en";
  const theme = localStorage.getItem("LD_THEME") || "dark";

  // thème + langue
  if (theme === "light") document.documentElement.classList.add("light");
  LDI.applyI18n(lang);
  $("lang-select").value = lang;
  $("theme-toggle").innerHTML = theme === "light" ? LD.icon("sun") : LD.icon("moon");

  // session déjà ouverte ?
  if (LD.getToken()) {
    location.href = "app.html";
    return;
  }

  $("lang-select").addEventListener("change", (e) => {
    localStorage.setItem("LD_LANG", e.target.value);
    LDI.applyI18n(e.target.value);
  });
  $("theme-toggle").addEventListener("click", () => {
    const next = document.documentElement.classList.contains("light") ? "dark" : "light";
    localStorage.setItem("LD_THEME", next);
    document.documentElement.classList.toggle("light", next === "light");
    $("theme-toggle").innerHTML = next === "light" ? LD.icon("sun") : LD.icon("moon");
  });

  // onglets
  function showTab(tab) {
    const isLogin = tab === "login";
    $("tab-login").classList.toggle("active", isLogin);
    $("tab-register").classList.toggle("active", !isLogin);
    $("form-login").classList.toggle("hidden", !isLogin);
    $("form-register").classList.toggle("hidden", isLogin);
    hideAlerts();
  }
  $("tab-login").addEventListener("click", () => showTab("login"));
  $("tab-register").addEventListener("click", () => showTab("register"));

  function hideAlerts() {
    $("auth-alert").classList.add("hidden");
    $("auth-ok").classList.add("hidden");
  }
  function showError(msg) {
    $("auth-ok").classList.add("hidden");
    const el = $("auth-alert");
    el.textContent = msg;
    el.classList.remove("hidden");
  }
  function showOk(msg) {
    $("auth-alert").classList.add("hidden");
    const el = $("auth-ok");
    el.textContent = msg;
    el.classList.remove("hidden");
  }

  // connexion
  $("form-login").addEventListener("submit", async (e) => {
    e.preventDefault();
    hideAlerts();
    const email = $("login-email").value.trim();
    const password = $("login-password").value;
    const t = LDI.t;

    if (!LD.isEmailValid(email)) return showError(t("auth_err_email_invalid", lang));
    if (password.length < 8) return showError(t("auth_err_password_len", lang));

    const btn = $("btn-login");
    btn.disabled = true;
    try {
      await LD.login(email, password);
      location.href = "app.html";
    } catch (err) {
      showError(err && err.message ? err.message : "Login failed");
      btn.disabled = false;
    }
  });

  // inscription
  $("form-register").addEventListener("submit", async (e) => {
    e.preventDefault();
    hideAlerts();
    const email = $("reg-email").value.trim();
    const password = $("reg-password").value;
    const confirm = $("reg-confirm").value;
    const t = LDI.t;

    if (!LD.isEmailValid(email)) return showError(t("auth_err_email_invalid", lang));
    if (password.length < 8) return showError(t("auth_err_password_len", lang));
    if (password !== confirm) return showError(t("auth_err_password_mismatch", lang));

    const btn = $("btn-register");
    btn.disabled = true;
    try {
      await LD.register(email, password);
      showOk(t("auth_success_registered", lang));
      $("login-email").value = email;
      $("login-password").value = password;
      showTab("login");
      showOk(t("auth_success_registered", lang));
    } catch (err) {
      showError(err && err.message ? err.message : "Registration failed");
    } finally {
      btn.disabled = false;
    }
  });
})();
