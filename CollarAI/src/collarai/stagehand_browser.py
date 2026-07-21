from __future__ import annotations

import asyncio
import base64
import json
import os
import re
import urllib.request
from pathlib import Path
from time import perf_counter
from typing import Any
from urllib.parse import urlparse
from uuid import uuid4

from stagehand import AsyncSession
from websockets.asyncio.client import connect

from collarai.errors import WorkflowError


class ActionCache:
    """Small local cache for Stagehand actions discovered during semantic recovery."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        self._actions = self._load()

    def get(self, key: str) -> dict[str, Any] | None:
        action = self._actions.get(key)
        return dict(action) if isinstance(action, dict) else None

    def put(self, key: str, action: dict[str, Any]) -> None:
        self._actions[key] = action
        temporary = self.path.with_suffix(".tmp")
        temporary.write_text(json.dumps(self._actions, indent=2), encoding="utf-8")
        os.replace(temporary, self.path)
        self.path.chmod(0o600)

    def _load(self) -> dict[str, dict[str, Any]]:
        try:
            value = json.loads(self.path.read_text(encoding="utf-8"))
        except (FileNotFoundError, json.JSONDecodeError):
            return {}
        return value if isinstance(value, dict) else {}


class CDPConnection:
    """Minimal request/response Chrome DevTools Protocol connection."""

    def __init__(self, websocket: Any) -> None:
        self.websocket = websocket
        self._identifier = 0
        self._lock = asyncio.Lock()

    @classmethod
    async def open(cls, url: str) -> CDPConnection:
        websocket = await connect(url, open_timeout=10, max_size=None)
        return cls(websocket)

    async def send(
        self,
        method: str,
        params: dict[str, Any] | None = None,
        session_id: str | None = None,
    ) -> dict[str, Any]:
        async with self._lock:
            self._identifier += 1
            identifier = self._identifier
            message: dict[str, Any] = {
                "id": identifier,
                "method": method,
                "params": params or {},
            }
            if session_id:
                message["sessionId"] = session_id
            await self.websocket.send(json.dumps(message))
            while True:
                response = json.loads(await self.websocket.recv())
                if response.get("id") != identifier:
                    continue
                if error := response.get("error"):
                    raise WorkflowError(
                        f"CDP {method} failed: {error.get('message', 'unknown error')}"
                    )
                return response.get("result", {})

    async def close(self) -> None:
        await self.websocket.close()


class StagehandPage:
    """Stagehand actions plus deterministic CDP inspection for one browser page."""

    def __init__(
        self,
        session: AsyncSession,
        cdp: CDPConnection,
        target_session_id: str,
        cache: ActionCache,
        model: dict[str, str],
        timeout_ms: int,
    ) -> None:
        self.session = session
        self.cdp = cdp
        self.target_session_id = target_session_id
        self.cache = cache
        self.model = model
        self.timeout_ms = timeout_ms
        self.action_log: list[dict[str, Any]] = []
        self.frame_id: str | None = None
        self._recovery_health: tuple[float, bool] | None = None

    @classmethod
    async def open(
        cls,
        session: AsyncSession,
        cdp_url: str,
        cache: ActionCache,
        model: dict[str, str],
        timeout_ms: int,
        preferred_host: str | None = None,
    ) -> StagehandPage:
        cdp = await CDPConnection.open(cdp_url)
        targets = (await cdp.send("Target.getTargets")).get("targetInfos", [])
        pages = [item for item in targets if item.get("type") == "page"]
        target = next(
            (
                item
                for item in reversed(pages)
                if urlparse(item.get("url", "")).hostname == preferred_host
            ),
            None,
        )
        target = target or next(
            (item for item in reversed(pages) if item.get("url") != "devtools://devtools/"),
            None,
        )
        if target is None:
            target_id = (await cdp.send("Target.createTarget", {"url": "about:blank"}))["targetId"]
        else:
            target_id = target["targetId"]
        attached = await cdp.send(
            "Target.attachToTarget",
            {"targetId": target_id, "flatten": True},
        )
        page = cls(
            session=session,
            cdp=cdp,
            target_session_id=attached["sessionId"],
            cache=cache,
            model=model,
            timeout_ms=timeout_ms,
        )
        for domain in ("Page", "Runtime", "Network", "Accessibility"):
            await page._send(f"{domain}.enable")
        await page._refresh_frame_id()
        return page

    async def close(self) -> None:
        await self.cdp.close()

    def begin_run(self) -> None:
        self.action_log.clear()

    async def goto(self, url: str) -> None:
        await self.session.navigate(
            url=url,
            frame_id=self.frame_id,
            options={"wait_until": "domcontentloaded", "timeout": self.timeout_ms},
            timeout=max(30, self.timeout_ms / 1_000 + 5),
        )
        await self._refresh_frame_id()

    async def act(
        self,
        *,
        selector: str,
        method: str,
        arguments: list[str] | None,
        intent: str,
        recover: bool = True,
        sensitive: bool = False,
    ) -> None:
        primary = {
            "selector": selector,
            "description": intent,
            "method": method,
            "arguments": arguments or [],
        }
        candidates = [primary]
        cached = self.cache.get(intent)
        if cached and cached.get("selector") != selector:
            candidates.insert(0, cached)

        errors: list[str] = []
        for candidate in candidates:
            try:
                await self._perform(candidate, sensitive=sensitive)
                return
            except Exception as error:  # Stagehand exposes provider-specific exceptions.
                errors.append(str(error))

        if recover and await self._semantic_recovery_available():
            try:
                observed = await self.session.observe(
                    instruction=intent,
                    frame_id=self.frame_id,
                    options={"model": self.model, "timeout": self.timeout_ms},
                    timeout=max(30, self.timeout_ms / 1_000 + 15),
                )
                for item in observed.data.result:
                    candidate = item.to_dict(exclude_none=True)
                    if candidate.get("method") not in {None, method}:
                        continue
                    candidate["method"] = method
                    candidate.setdefault("arguments", arguments or [])
                    await self._perform(candidate, sensitive=sensitive)
                    self.cache.put(intent, candidate)
                    return
            except Exception as error:
                errors.append(str(error))

        detail = errors[-1][:300] if errors else "no matching element"
        raise WorkflowError(f"Could not {intent}: {detail}")

    async def mark(self, selector: str, index: int = 0) -> str:
        """Give one inspected DOM element a stable XPath for a Stagehand action."""
        marker = f"target-{uuid4().hex}"
        value = await self.evaluate(
            "(() => { const elements = document.querySelectorAll("
            + json.dumps(selector)
            + "); const element = elements["
            + str(index)
            + "]; if (!element) return false; element.setAttribute("
            + json.dumps("data-collarai-target")
            + ", "
            + json.dumps(marker)
            + "); return true; })()"
        )
        if not value:
            raise WorkflowError(f"Could not mark element {index} matching {selector!r}")
        return f"xpath=//*[@data-collarai-target={json.dumps(marker)}]"

    async def _perform(self, action: dict[str, Any], sensitive: bool) -> None:
        started = perf_counter()
        response = await self.session.act(
            input=action,
            frame_id=self.frame_id,
            options={"timeout": self.timeout_ms},
            timeout=max(30, self.timeout_ms / 1_000 + 5),
        )
        if not response.success or not response.data.result.success:
            raise WorkflowError(response.data.result.message)
        await self._refresh_frame_id()
        logged = dict(action)
        if sensitive:
            logged["arguments"] = ["[REDACTED]"]
        logged["elapsed_seconds"] = round(perf_counter() - started, 4)
        self.action_log.append(logged)

    async def _semantic_recovery_available(self) -> bool:
        """Avoid slow provider retries when the optional local model is offline."""
        now = perf_counter()
        if self._recovery_health and now - self._recovery_health[0] < 5:
            return self._recovery_health[1]

        base_url = str(self.model.get("base_url", "")).rstrip("/")
        api_key = str(self.model.get("api_key", ""))

        def check() -> bool:
            if not base_url:
                return False
            request = urllib.request.Request(f"{base_url}/models")
            if api_key:
                request.add_header("Authorization", f"Bearer {api_key}")
            try:
                with urllib.request.urlopen(request, timeout=0.4) as response:
                    return 200 <= response.status < 300
            except Exception:
                return False

        available = await asyncio.to_thread(check)
        self._recovery_health = (now, available)
        return available

    async def evaluate(self, expression: str) -> Any:
        result = await self._send(
            "Runtime.evaluate",
            {
                "expression": expression,
                "awaitPromise": True,
                "returnByValue": True,
            },
        )
        if details := result.get("exceptionDetails"):
            description = details.get("exception", {}).get("description", "JavaScript failed")
            raise WorkflowError(description)
        return result.get("result", {}).get("value")

    async def current_url(self) -> str:
        return str(await self.evaluate("location.href"))

    async def title(self) -> str:
        return str(await self.evaluate("document.title"))

    async def body_text(self, limit: int = 4_000) -> str:
        expression = f"(document.body?.innerText || '').slice(0, {int(limit)})"
        return str(await self.evaluate(expression))

    async def visible(self, selector: str) -> bool:
        encoded = json.dumps(selector)
        return bool(
            await self.evaluate(
                "(() => { const e = document.querySelector("
                + encoded
                + "); if (!e) return false; const s = getComputedStyle(e); "
                "const r = e.getBoundingClientRect(); return s.visibility !== 'hidden' "
                "&& s.display !== 'none' && r.width > 0 && r.height > 0; })()"
            )
        )

    async def wait_visible(self, selector: str, timeout_ms: int | None = None) -> None:
        await self.wait_until(
            lambda: self.visible(selector),
            f"element {selector!r} did not become visible",
            timeout_ms,
        )

    async def value(self, selector: str) -> str:
        encoded = json.dumps(selector)
        value = await self.evaluate(f"document.querySelector({encoded})?.value ?? ''")
        return str(value)

    async def attribute(self, selector: str, name: str) -> str | None:
        value = await self.evaluate(
            f"document.querySelector({json.dumps(selector)})"
            f"?.getAttribute({json.dumps(name)}) ?? null"
        )
        return str(value) if value is not None else None

    async def texts(self, selector: str) -> list[str]:
        value = await self.evaluate(
            "Array.from(document.querySelectorAll("
            + json.dumps(selector)
            + "), e => e.innerText || e.textContent || '')"
        )
        return [str(item) for item in value or []]

    async def exact_text_visible(self, container: str, value: str) -> bool:
        return bool(
            await self.evaluate(
                "(() => { const root = document.querySelector("
                + json.dumps(container)
                + "); if (!root) return false; const wanted = "
                + json.dumps(value)
                + "; return Array.from(root.querySelectorAll('*')).some(e => "
                "(e.innerText || e.textContent || '').trim() === wanted && "
                "getComputedStyle(e).display !== 'none'); })()"
            )
        )

    async def wait_until(
        self,
        predicate: Any,
        message: str,
        timeout_ms: int | None = None,
    ) -> None:
        deadline = asyncio.get_running_loop().time() + (timeout_ms or self.timeout_ms) / 1_000
        while asyncio.get_running_loop().time() < deadline:
            if await predicate():
                return
            await asyncio.sleep(0.1)
        raise WorkflowError(message)

    async def wait_for_url(self, pattern: re.Pattern[str], timeout_ms: int | None = None) -> None:
        async def matches() -> bool:
            return bool(pattern.search(await self.current_url()))

        await self.wait_until(matches, f"URL did not match {pattern.pattern!r}", timeout_ms)

    async def cookies(self) -> list[dict[str, Any]]:
        return list((await self._send("Network.getAllCookies")).get("cookies", []))

    async def add_cookies(self, cookies: list[dict[str, Any]]) -> None:
        allowed = {
            "name",
            "value",
            "url",
            "domain",
            "path",
            "secure",
            "httpOnly",
            "sameSite",
            "expires",
            "priority",
            "sameParty",
            "sourceScheme",
            "sourcePort",
            "partitionKey",
        }
        clean = [{key: value for key, value in item.items() if key in allowed} for item in cookies]
        await self._send("Network.setCookies", {"cookies": clean})

    async def screenshot(self, path: Path) -> None:
        result = await self._send(
            "Page.captureScreenshot",
            {"format": "png", "fromSurface": True, "captureBeyondViewport": False},
        )
        path.write_bytes(base64.b64decode(result["data"]))
        path.chmod(0o600)

    async def accessibility_tree(self) -> dict[str, Any]:
        return await self._send("Accessibility.getFullAXTree")

    async def set_content(self, html: str) -> None:
        await self._refresh_frame_id()
        if not self.frame_id:
            raise WorkflowError("The browser page has no main frame")
        await self._send("Page.setDocumentContent", {"frameId": self.frame_id, "html": html})

    async def transaction_table(self) -> dict[str, Any]:
        value = await self.evaluate(
            """
            (() => {
              const clean = value => String(value || '').replace(/\\s+/g, ' ').trim();
              const tables = Array.from(document.querySelectorAll('table'));
              const table = tables.find(candidate =>
                Array.from(candidate.querySelectorAll('thead th')).some(
                  header => clean(header.innerText || header.textContent) === 'Deal Type'
                )
              );
              if (!table) return null;
              const headers = Array.from(table.querySelectorAll('thead th'), header =>
                clean(header.innerText || header.textContent)
              );
              const rows = Array.from(table.querySelectorAll('tbody > tr'), row =>
                Array.from(row.querySelectorAll(':scope > td'), cell =>
                  clean(cell.innerText || cell.textContent)
                )
              );
              return {headers, rows};
            })()
            """
        )
        if not isinstance(value, dict):
            raise WorkflowError("PitchBook transaction table is not visible")
        return value

    async def next_button(self) -> dict[str, Any] | None:
        marker = f"next-{uuid4().hex}"
        script = f"""
            (() => {{
              const visible = element => {{
                const style = getComputedStyle(element);
                const rect = element.getBoundingClientRect();
                return style.display !== 'none' && style.visibility !== 'hidden'
                  && rect.width > 0 && rect.height > 0;
              }};
              const button = Array.from(document.querySelectorAll('button')).find(element => {{
                const name = (element.getAttribute('aria-label') || element.title
                  || element.innerText || element.textContent || '').trim();
                return visible(element) && /^next(?: page)?$/i.test(name);
              }});
              if (!button) return null;
              button.setAttribute('data-collarai-next', {json.dumps(marker)});
              const disabled = button.disabled
                || button.getAttribute('aria-disabled') === 'true';
              return {{disabled: Boolean(disabled)}};
            }})()
            """
        value = await self.evaluate(script)
        if not isinstance(value, dict):
            return None
        return {
            **value,
            "selector": f"xpath=//*[@data-collarai-next={json.dumps(marker)}]",
        }

    async def _refresh_frame_id(self) -> None:
        tree = await self._send("Page.getFrameTree")
        self.frame_id = tree.get("frameTree", {}).get("frame", {}).get("id")

    async def _send(
        self,
        method: str,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        return await self.cdp.send(method, params, self.target_session_id)


def browser_websocket_url(cdp_url: str) -> str:
    if cdp_url.startswith(("ws://", "wss://")):
        return cdp_url
    with urllib.request.urlopen(f"{cdp_url.rstrip('/')}/json/version", timeout=2) as response:
        payload = json.load(response)
    value = payload.get("webSocketDebuggerUrl")
    if not isinstance(value, str):
        raise RuntimeError("Chrome did not publish a browser CDP WebSocket URL")
    return value
