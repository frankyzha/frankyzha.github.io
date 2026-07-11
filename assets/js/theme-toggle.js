(function () {
  "use strict";

  const root = document.documentElement;
  const toggle = document.getElementById("color-theme-toggle");
  if (!toggle) return;

  const darkMode = window.matchMedia("(prefers-color-scheme: dark)");
  const themeColor = document.querySelector('meta[name="theme-color"]');

  function readSavedTheme() {
    try {
      const theme = localStorage.getItem("theme");
      return theme === "dark" || theme === "light" ? theme : null;
    } catch (_error) {
      return null;
    }
  }

  function saveTheme(theme) {
    try {
      localStorage.setItem("theme", theme);
    } catch (_error) {
      // Switching themes still works when storage is unavailable.
    }
  }

  function announceTheme(theme) {
    if (typeof CustomEvent !== "function") return;
    document.dispatchEvent(new CustomEvent("site:themechange", { detail: { theme: theme } }));
  }

  function applyTheme(theme, persist) {
    const isDark = theme === "dark";
    toggle.checked = isDark;
    root.toggleAttribute("data-theme", isDark);
    toggle.setAttribute("aria-label", isDark ? "Use white theme" : "Use black theme");
    if (themeColor) themeColor.setAttribute("content", isDark ? "#000000" : "#ffffff");
    if (persist) saveTheme(theme);
    announceTheme(theme);
  }

  applyTheme(readSavedTheme() || (darkMode.matches ? "dark" : "light"), false);

  toggle.addEventListener("change", function () {
    applyTheme(toggle.checked ? "dark" : "light", true);
  });

  function followSystemTheme(event) {
    if (!readSavedTheme()) applyTheme(event.matches ? "dark" : "light", false);
  }

  if (darkMode.addEventListener) darkMode.addEventListener("change", followSystemTheme);
  else if (darkMode.addListener) darkMode.addListener(followSystemTheme);
}());
