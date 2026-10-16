/* Log in / create account page. */
(function () {
  "use strict";

  const error = document.getElementById("auth-error");
  const tabs = {
    login: { tab: document.getElementById("tab-login"), panel: document.getElementById("panel-login") },
    register: { tab: document.getElementById("tab-register"), panel: document.getElementById("panel-register") },
  };

  // Only allow redirects to our own pages (prevents open redirects via ?next=)
  function destination(user) {
    const next = new URLSearchParams(window.location.search).get("next");
    if (user.role === "admin") return "admin.html";
    return next && /^[a-z]+\.html$/.test(next) && next !== "admin.html" ? next : "account.html";
  }

  function selectTab(name, focus = false) {
    Object.entries(tabs).forEach(([key, { tab, panel }]) => {
      const selected = key === name;
      tab.setAttribute("aria-selected", String(selected));
      tab.tabIndex = selected ? 0 : -1;
      panel.hidden = !selected;
    });
    error.hidden = true;
    if (focus) tabs[name].tab.focus();
  }

  Object.entries(tabs).forEach(([name, { tab }]) => {
    tab.addEventListener("click", () => selectTab(name));
    tab.addEventListener("keydown", (event) => {
      if (event.key === "ArrowRight" || event.key === "ArrowLeft") {
        selectTab(name === "login" ? "register" : "login", true);
      }
    });
  });
  if (window.location.hash === "#register") selectTab("register");

  function showError(message, field) {
    error.textContent = message;
    error.hidden = false;
    if (field) {
      field.setAttribute("aria-invalid", "true");
      field.focus();
    }
  }

  function clearErrors(form) {
    error.hidden = true;
    form.querySelectorAll("[aria-invalid]").forEach((input) => input.removeAttribute("aria-invalid"));
  }

  async function submit(form, action) {
    const button = form.querySelector("button[type=submit]");
    clearErrors(form);
    for (const input of form.querySelectorAll("input[required]")) {
      if (!input.value.trim()) {
        showError(`Please enter your ${input.labels[0].textContent.toLowerCase()}.`, input);
        return;
      }
    }
    button.disabled = true;
    try {
      const user = await action();
      window.KQSite.clearChat();
      window.location.href = destination(user);
    } catch (err) {
      showError(err.message);
      button.disabled = false;
    }
  }

  document.getElementById("login-form").addEventListener("submit", (event) => {
    event.preventDefault();
    submit(event.target, () => window.KQApi.login(
      document.getElementById("login-email").value.trim(),
      document.getElementById("login-password").value,
    ));
  });

  document.getElementById("register-form").addEventListener("submit", (event) => {
    event.preventDefault();
    submit(event.target, () => window.KQApi.register(
      document.getElementById("register-name").value.trim(),
      document.getElementById("register-email").value.trim(),
      document.getElementById("register-password").value,
    ));
  });

  // Already logged in? Go straight to the right page.
  window.KQSite.ready.then((user) => {
    if (user) window.location.replace(destination(user));
  });
})();
