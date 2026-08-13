(function () {
  const SUPPORTED = ["en", "fr", "ar"];
  const DEFAULT = "en";
  const STORAGE_KEY = "nexus_lang";

  let _locale = {};
  let _currentLang = DEFAULT;

  function detectLang() {
    const stored = localStorage.getItem(STORAGE_KEY);
    if (stored && SUPPORTED.includes(stored)) return stored;
    const nav = navigator.language || navigator.userLanguage || "";
    const short = nav.slice(0, 2);
    if (SUPPORTED.includes(short)) return short;
    return DEFAULT;
  }

  async function loadLocale(lang) {
    try {
      const res = await fetch("locales/" + lang + ".json?v=2");
      if (!res.ok) throw new Error("HTTP " + res.status);
      return await res.json();
    } catch {
      if (lang !== DEFAULT) {
        console.warn("[i18n] Failed to load " + lang + ", falling back to " + DEFAULT);
        return loadLocale(DEFAULT);
      }
      return {};
    }
  }

  function translatePage() {
    document.documentElement.lang = _currentLang;
    document.documentElement.dir = _currentLang === "ar" ? "rtl" : "ltr";

    document.querySelectorAll("[data-i18n]").forEach(function (el) {
      var key = el.getAttribute("data-i18n");
      var text = resolveKey(key);
      if (text !== null) {
        if (el.tagName === "INPUT" || el.tagName === "TEXTAREA") {
          if (el.getAttribute("data-i18n-target") === "placeholder") {
            el.placeholder = text;
          }
        } else if (el.tagName === "META" && el.getAttribute("name") === "description") {
          el.content = text;
        } else if (el.tagName === "TITLE") {
          el.textContent = text;
        } else {
          el.textContent = text;
        }
      }
    });

    document.querySelectorAll("[data-i18n-value]").forEach(function (el) {
      var key = el.getAttribute("data-i18n-value");
      var text = resolveKey(key);
      if (text !== null) {
        el.value = text;
      }
    });

    var event = new CustomEvent("i18n-ready", { detail: { lang: _currentLang } });
    document.dispatchEvent(event);
  }

  function resolveKey(key) {
    var parts = key.split(".");
    var val = _locale;
    for (var i = 0; i < parts.length; i++) {
      if (val == null || typeof val !== "object") return null;
      val = val[parts[i]];
    }
    return typeof val === "string" ? val : null;
  }

  window.__ = function (key, fallback) {
    var text = resolveKey(key);
    return text !== null ? text : (fallback || key);
  };

  window.setLanguage = async function (lang) {
    if (!SUPPORTED.includes(lang)) return;
    _currentLang = lang;
    localStorage.setItem(STORAGE_KEY, lang);
    _locale = await loadLocale(lang);
    translatePage();
    updateLangSwitcher();
  };

  function createLangSwitcher() {
    var container = document.querySelector(".navbar-actions");
    if (!container || container.querySelector(".lang-switcher")) return;

    var wrapper = document.createElement("div");
    wrapper.className = "lang-switcher";
    wrapper.style.cssText = "display:inline-flex;align-items:center;gap:2px;margin-right:0.5rem;";

    var labels = { en: "EN", fr: "FR", ar: "AR" };
    SUPPORTED.forEach(function (code) {
      var btn = document.createElement("button");
      btn.className = "lang-btn";
      btn.textContent = labels[code] || code.toUpperCase();
      btn.dataset.lang = code;
      btn.style.cssText =
        "background:none;border:1px solid transparent;color:var(--text-dim);font-size:0.7rem;font-weight:600;padding:2px 6px;border-radius:4px;cursor:pointer;transition:all 0.15s;text-transform:uppercase;letter-spacing:0.05em;";
      btn.addEventListener("click", function () {
        window.setLanguage(code);
      });
      wrapper.appendChild(btn);
    });

    container.insertBefore(wrapper, container.firstChild);
    updateLangSwitcher();
  }

  function updateLangSwitcher() {
    document.querySelectorAll(".lang-btn").forEach(function (btn) {
      if (btn.dataset.lang === _currentLang) {
        btn.style.color = "var(--cyan)";
        btn.style.borderColor = "var(--cyan)";
      } else {
        btn.style.color = "var(--text-dim)";
        btn.style.borderColor = "transparent";
      }
    });
  }

  (async function init() {
    var lang = detectLang();
    _currentLang = lang;
    _locale = await loadLocale(lang);
    translatePage();
    if (document.querySelector(".navbar-actions")) {
      createLangSwitcher();
    }
  })();
})();
