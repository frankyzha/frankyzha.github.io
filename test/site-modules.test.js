import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { afterEach, test } from "node:test";
import { runInNewContext } from "node:vm";

import { initNavigation } from "../assets/js/modules/navigation.js";

class ClassList {
  #values = new Set();

  contains(name) {
    return this.#values.has(name);
  }

  toggle(name, force) {
    const add = force ?? !this.contains(name);
    if (add) this.#values.add(name);
    else this.#values.delete(name);
    return add;
  }
}

class ElementStub extends EventTarget {
  #attributes = new Map();

  classList = new ClassList();

  setAttribute(name, value) {
    this.#attributes.set(name, String(value));
  }

  getAttribute(name) {
    return this.#attributes.get(name) ?? null;
  }

  hasAttribute(name) {
    return this.#attributes.has(name);
  }

  toggleAttribute(name, force) {
    if (force) this.#attributes.set(name, "");
    else this.#attributes.delete(name);
  }

  contains(target) {
    return target === this;
  }

  focus() {
    this.focused = true;
  }
}

class DocumentStub extends EventTarget {
  constructor(elements, root = new ElementStub()) {
    super();
    this.elements = elements;
    this.documentElement = root;
  }

  getElementById(id) {
    return this.elements[id] ?? null;
  }

  querySelector(selector) {
    return this.elements[selector] ?? null;
  }
}

class MediaQueryStub extends EventTarget {
  constructor(matches) {
    super();
    this.matches = matches;
  }
}

afterEach(() => {
  delete globalThis.document;
  delete globalThis.localStorage;
  delete globalThis.window;
});

test("theme toggle applies and persists the selected theme", () => {
  const root = new ElementStub();
  const toggle = new ElementStub();
  const themeColor = new ElementStub();
  const storage = new Map();

  const document = new DocumentStub({
    "color-theme-toggle": toggle,
    'meta[name="theme-color"]': themeColor
  }, root);
  const localStorage = {
    getItem: (key) => storage.get(key) ?? null,
    setItem: (key, value) => storage.set(key, value)
  };
  const window = { matchMedia: () => new MediaQueryStub(false) };

  runInNewContext(readFileSync("assets/js/theme-toggle.js", "utf8"), {
    CustomEvent,
    document,
    localStorage,
    String,
    window
  });
  assert.equal(root.hasAttribute("data-theme"), false);

  toggle.checked = true;
  toggle.dispatchEvent(new Event("change"));
  assert.equal(root.hasAttribute("data-theme"), true);
  assert.equal(toggle.checked, true);
  assert.equal(themeColor.getAttribute("content"), "#000000");
  assert.equal(storage.get("theme"), "dark");

  toggle.checked = false;
  toggle.dispatchEvent(new Event("change"));
  assert.equal(root.hasAttribute("data-theme"), false);
  assert.equal(toggle.checked, false);
  assert.equal(themeColor.getAttribute("content"), "#ffffff");
  assert.equal(storage.get("theme"), "light");
});

test("navigation keeps visual and accessibility state synchronized", () => {
  const nav = new ElementStub();
  const toggle = new ElementStub();

  globalThis.document = new DocumentStub({
    "primary-nav": nav,
    "primary-nav-toggle": toggle
  });
  globalThis.window = { matchMedia: () => new MediaQueryStub(false) };

  initNavigation();
  toggle.dispatchEvent(new Event("click"));

  assert.equal(nav.classList.contains("is-open"), true);
  assert.equal(toggle.getAttribute("aria-expanded"), "true");
  assert.equal(toggle.getAttribute("aria-label"), "Close navigation menu");
});
