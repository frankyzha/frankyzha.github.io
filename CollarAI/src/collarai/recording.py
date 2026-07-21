from __future__ import annotations

import json
import os
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from collarai.stagehand_browser import StagehandPage

_RECORDER_SCRIPT = r"""
({ storageKey, marker }) => {
  if (window[marker]) return;
  window[marker] = true;

  const clean = value => String(value || '').replace(/\s+/g, ' ').trim().slice(0, 240);
  const clickable = 'button,a,input,select,textarea,[role],[data-testid]';
  const read = () => {
    try { return JSON.parse(sessionStorage.getItem(storageKey) || '[]'); }
    catch { return window[storageKey] || []; }
  };
  const write = event => {
    const events = read();
    events.push({ recorded_at: new Date().toISOString(), page_url: location.href, ...event });
    window[storageKey] = events;
    try { sessionStorage.setItem(storageKey, JSON.stringify(events)); }
    catch {}
  };

  function targetFor(event) {
    return event.composedPath().find(node => node instanceof Element && node.matches(clickable))
      || (event.target instanceof Element ? event.target : null);
  }

  function cssPath(element) {
    if (!element) return null;
    if (element.id) return `#${CSS.escape(element.id)}`;
    const testId = element.getAttribute('data-testid');
    if (testId) return `[data-testid=${JSON.stringify(testId)}]`;
    const name = element.getAttribute('name');
    if (name) return `${element.localName}[name=${JSON.stringify(name)}]`;
    const parts = [];
    let node = element;
    while (node && node.localName && parts.length < 5) {
      let part = node.localName;
      const siblings = node.parentElement
        ? [...node.parentElement.children].filter(item => item.localName === node.localName)
        : [];
      if (siblings.length > 1) part += `:nth-of-type(${siblings.indexOf(node) + 1})`;
      parts.unshift(part);
      node = node.parentElement;
    }
    return parts.join(' > ');
  }

  function describe(element) {
    if (!element) return {};
    const labels = element.labels
      ? [...element.labels].map(label => clean(label.innerText)).filter(Boolean).join(' ')
      : '';
    const password = element instanceof HTMLInputElement && element.type === 'password';
    const value = 'value' in element ? (password ? '[REDACTED]' : clean(element.value)) : null;
    return {
      tag: element.localName,
      role: element.getAttribute('role'),
      text: clean(element.innerText || element.textContent),
      label: labels || null,
      ariaLabel: clean(element.getAttribute('aria-label')) || null,
      placeholder: clean(element.getAttribute('placeholder')) || null,
      id: element.id || null,
      name: element.getAttribute('name'),
      type: element.getAttribute('type'),
      testId: element.getAttribute('data-testid'),
      href: element instanceof HTMLAnchorElement ? element.href : null,
      value,
      selectedText: element instanceof HTMLSelectElement
        ? clean(element.selectedOptions[0]?.textContent)
        : null,
      css: cssPath(element),
    };
  }

  function emit(type, event, extra = {}) {
    write({ type, element: describe(targetFor(event)), ...extra });
  }

  write({ type: 'navigation', main_frame: true });
  document.addEventListener('click', event => emit('click', event), true);
  document.addEventListener('change', event => emit('change', event), true);
  document.addEventListener('submit', event => emit('submit', event), true);
  document.addEventListener('keydown', event => {
    if (event.key === 'Enter') emit('keypress', event, { key: 'Enter' });
  }, true);
  let scrollTimer;
  document.addEventListener('scroll', event => {
    clearTimeout(scrollTimer);
    scrollTimer = setTimeout(() => emit('scroll', event, {
      scrollX: Math.round(window.scrollX),
      scrollY: Math.round(window.scrollY),
    }), 250);
  }, true);
}
"""


class InteractionRecorder:
    """Record human actions through the same Stagehand-owned CDP page."""

    def __init__(self, output_dir: Path) -> None:
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.output_dir.chmod(0o700)
        self.started_at = datetime.now(UTC)
        token = uuid4().hex
        self.storage_key = f"collarai-record-{token}"
        self.marker = f"__collarai_record_{token}"
        arguments = json.dumps({"storageKey": self.storage_key, "marker": self.marker})
        self.script = f"({_RECORDER_SCRIPT})({arguments});"

    async def attach(self, page: StagehandPage) -> None:
        await page._send("Page.addScriptToEvaluateOnNewDocument", {"source": self.script})
        await page.evaluate(self.script)

    async def save(self, page: StagehandPage) -> Path:
        timestamp = self.started_at.strftime("%Y%m%dT%H%M%SZ")
        stem = self.output_dir / f"pitchbook-{timestamp}"
        screenshot = stem.with_name(f"{stem.name}-final.png")
        accessibility = stem.with_name(f"{stem.name}-final.aria.json")
        try:
            await page.screenshot(screenshot)
        except Exception:
            screenshot = None
        try:
            tree = await page.accessibility_tree()
            accessibility.write_text(json.dumps(tree, indent=2), encoding="utf-8")
            accessibility.chmod(0o600)
        except Exception:
            accessibility = None

        key = json.dumps(self.storage_key)
        events = await page.evaluate(
            "(() => { try { return JSON.parse(sessionStorage.getItem("
            + key
            + ") || '[]'); } catch { return window["
            + key
            + "] || []; } })()"
        )
        result = {
            "version": 2,
            "driver": "stagehand-v3",
            "started_at": self.started_at.isoformat(),
            "ended_at": datetime.now(UTC).isoformat(),
            "final_url": await page.current_url(),
            "final_title": await page.title(),
            "events": events or [],
            "screenshot": str(screenshot) if screenshot else None,
            "aria_snapshot": str(accessibility) if accessibility else None,
        }
        output = stem.with_suffix(".json")
        temporary = output.with_suffix(".tmp")
        temporary.write_text(json.dumps(result, indent=2), encoding="utf-8")
        os.replace(temporary, output)
        output.chmod(0o600)
        return output
