const DESKTOP_QUERY = "(min-width: 761px)";

export function initNavigation() {
  const nav = document.getElementById("primary-nav");
  const toggle = document.getElementById("primary-nav-toggle");
  if (!nav || !toggle) return;

  const desktop = window.matchMedia(DESKTOP_QUERY);

  function setOpen(open) {
    nav.classList.toggle("is-open", open);
    toggle.setAttribute("aria-expanded", String(open));
    toggle.setAttribute("aria-label", open ? "Close navigation menu" : "Open navigation menu");
  }

  toggle.addEventListener("click", () => {
    setOpen(!nav.classList.contains("is-open"));
  });

  document.addEventListener("click", ({ target }) => {
    if (nav.classList.contains("is-open") && !nav.contains(target)) setOpen(false);
  });

  document.addEventListener("keydown", ({ key }) => {
    if (key !== "Escape" || !nav.classList.contains("is-open")) return;
    setOpen(false);
    toggle.focus();
  });

  desktop.addEventListener("change", ({ matches }) => {
    if (matches) setOpen(false);
  });
}
