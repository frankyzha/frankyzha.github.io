const HEADING_SELECTOR = "h2, h3, h4";
const COMPACT_QUERY = "(max-width: 1100px)";

function createTocItem(heading, index) {
  if (!heading.id) heading.id = `section-${index + 1}`;

  const item = document.createElement("li");
  const link = document.createElement("a");

  item.className = `floating-toc__item floating-toc__item--${heading.tagName.toLowerCase()}`;
  link.href = `#${heading.id}`;
  link.textContent = heading.textContent.trim();
  item.append(link);

  return { item, link };
}

export function initFloatingToc() {
  const toc = document.querySelector("[data-floating-toc]");
  const content = document.querySelector(".page--post .page__content");
  if (!toc || !content) return;

  const headings = [...content.querySelectorAll(HEADING_SELECTOR)];
  if (headings.length < 2) {
    toc.remove();
    return;
  }

  const toggle = toc.querySelector(".floating-toc__toggle");
  const panel = toc.querySelector(".floating-toc__panel");
  const close = toc.querySelector(".floating-toc__close");
  const list = toc.querySelector(".floating-toc__list");
  if (!toggle || !panel || !close || !list) return;

  const compact = window.matchMedia(COMPACT_QUERY);
  const fragment = document.createDocumentFragment();
  const links = headings.map((heading, index) => {
    const { item, link } = createTocItem(heading, index);
    fragment.append(item);
    return link;
  });
  list.append(fragment);

  function setOpen(open) {
    toc.classList.toggle("is-open", open);
    toggle.setAttribute("aria-expanded", String(open));
    panel.setAttribute("aria-hidden", String(!open));
    panel.toggleAttribute("inert", !open);
  }

  function setActive(id) {
    for (const link of links) {
      const active = link.hash === `#${id}`;
      link.classList.toggle("is-active", active);
      if (active) link.setAttribute("aria-current", "location");
      else link.removeAttribute("aria-current");
    }
  }

  function updateActiveSection() {
    const active = headings.findLast((heading) => heading.getBoundingClientRect().top <= 150) || headings[0];
    setActive(active.id);
  }

  let frame;
  window.addEventListener("scroll", () => {
    if (frame) return;
    frame = window.requestAnimationFrame(() => {
      updateActiveSection();
      frame = null;
    });
  }, { passive: true });

  toggle.addEventListener("click", () => setOpen(!toc.classList.contains("is-open")));
  close.addEventListener("click", () => {
    setOpen(false);
    toggle.focus();
  });

  list.addEventListener("click", ({ target }) => {
    const link = target.closest("a");
    if (!link) return;
    setActive(link.hash.slice(1));
    if (compact.matches) setOpen(false);
  });

  document.addEventListener("click", ({ target }) => {
    if (toc.classList.contains("is-open") && !toc.contains(target)) setOpen(false);
  });

  document.addEventListener("keydown", ({ key }) => {
    if (key !== "Escape" || !toc.classList.contains("is-open")) return;
    setOpen(false);
    toggle.focus();
  });

  toc.hidden = false;
  updateActiveSection();
}
