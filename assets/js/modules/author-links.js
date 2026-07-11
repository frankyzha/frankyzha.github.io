const DESKTOP_QUERY = "(min-width: 761px)";

export function initAuthorLinks() {
  const button = document.querySelector(".author__urls-wrapper button");
  const links = document.querySelector(".author__urls");
  if (!button || !links) return;

  const desktop = window.matchMedia(DESKTOP_QUERY);

  function setOpen(open) {
    button.classList.toggle("open", open);
    button.setAttribute("aria-expanded", String(open));
    links.style.display = open ? "block" : "none";
  }

  button.addEventListener("click", () => {
    setOpen(button.getAttribute("aria-expanded") !== "true");
  });

  desktop.addEventListener("change", ({ matches }) => {
    if (!matches) return;
    button.classList.remove("open");
    button.setAttribute("aria-expanded", "false");
    links.style.removeProperty("display");
  });
}
