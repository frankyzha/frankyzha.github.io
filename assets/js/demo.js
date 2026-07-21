const root = typeof document === "undefined" ? null : document.querySelector("[data-collarai-demo]");

if (root) {
  const form = root.querySelector("#collarai-query-form");
  const input = root.querySelector("#collarai-query");
  const status = root.querySelector("#collarai-status");
  const result = root.querySelector("#collarai-result");
  const resultContent = root.querySelector("#collarai-result-content");
  const resultTime = root.querySelector("#collarai-result-time");
  const accessPanel = root.querySelector("#collarai-access");
  const accessInput = root.querySelector("#collarai-access-key");
  const submit = form.querySelector("button[type='submit']");
  const configuredApi = root.dataset.apiUrl.trim().replace(/\/$/, "");
  const localHost = ["localhost", "127.0.0.1"].includes(window.location.hostname);
  const api = configuredApi || (localHost ? "http://127.0.0.1:8787" : "");
  const requiresAccessKey = Boolean(configuredApi);
  let activeRequest;

  if (requiresAccessKey) {
    accessPanel.hidden = false;
    accessInput.value = readAccessKey();
  }

  root.querySelectorAll("[data-query]").forEach((button) => {
    button.addEventListener("click", () => {
      input.value = button.dataset.query;
      input.focus();
      setStatus("ready", "Ready", "Example loaded. Submit it when ready.");
    });
  });

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    const query = input.value.replace(/\s+/g, " ").trim();
    const rejection = validateQuery(query);
    if (rejection) {
      showRejection(rejection.code, rejection.message);
      return;
    }
    if (!api) {
      showRejection(
        "Not connected",
        "The research worker is not configured for this deployment yet. The interface is ready; an HTTPS API endpoint still needs to be attached."
      );
      return;
    }
    const accessKey = accessInput.value.trim();
    if (requiresAccessKey && !accessKey) {
      showRejection("Access required", "Enter the invitation key for this private demo.");
      accessInput.focus();
      return;
    }

    if (activeRequest) activeRequest.abort();
    activeRequest = new AbortController();
    setBusy(true);
    setStatus("working", "Researching", "Navigating the authenticated data surface…");
    result.hidden = true;

    try {
      const response = await fetch(`${api}/api/query`, {
        method: "POST",
        credentials: "include",
        headers: {
          "Content-Type": "application/json",
          ...(accessKey ? { Authorization: `Bearer ${accessKey}` } : {})
        },
        body: JSON.stringify({ query }),
        signal: activeRequest.signal,
      });
      const payload = await response.json();
      if (!response.ok) {
        const error = payload.error || {};
        if (response.status === 401) {
          forgetAccessKey();
          accessInput.value = "";
        }
        showRejection(error.code || "Request failed", error.message || "The query did not complete.");
        return;
      }
      if (accessKey) rememberAccessKey(accessKey);
      resultContent.innerHTML = renderMarkdown(payload.markdown);
      resultTime.textContent = `${(payload.elapsed_ms / 1000).toFixed(2)}s`;
      result.hidden = false;
      setStatus("complete", "Complete", "The result and evidence metadata are shown below.");
      if (window.MathJax?.typesetPromise) await window.MathJax.typesetPromise([resultContent]);
      result.scrollIntoView({ behavior: "smooth", block: "start" });
    } catch (error) {
      if (error.name !== "AbortError") {
        showRejection("Connection error", "The research worker could not be reached. Try again shortly.");
      }
    } finally {
      setBusy(false);
      activeRequest = undefined;
    }
  });

  function showRejection(code, message) {
    result.hidden = true;
    setStatus("rejected", code, message);
    input.focus();
  }

  function setBusy(busy) {
    submit.disabled = busy;
    submit.textContent = busy ? "Researching…" : "Run research ↗";
  }

  function setStatus(state, label, message) {
    status.dataset.state = state;
    status.querySelector("span").textContent = label;
    status.querySelector("p").textContent = message;
  }
}

function readAccessKey() {
  try {
    return sessionStorage.getItem("collarai-demo-access") || "";
  } catch {
    return "";
  }
}

function rememberAccessKey(value) {
  try {
    sessionStorage.setItem("collarai-demo-access", value);
  } catch {
    // Storage can be unavailable in private browsing; the current input still works.
  }
}

function forgetAccessKey() {
  try {
    sessionStorage.removeItem("collarai-demo-access");
  } catch {
    // Nothing else to revoke in this tab.
  }
}

export function validateQuery(query) {
  if (query.length < 12) {
    return { code: "Incomplete", message: "Write one complete company-financing question." };
  }
  if (!/\b(debt|equity|financ\w*|refinanc\w*|ipo|raised)\b/i.test(query)) {
    return { code: "Irrelevant", message: "This demo only handles supported company-financing questions." };
  }
  const namesCompany = /\bfor\s+[^,]{1,80},|\bwhat(?:'s|’s|\s+is|\s+was)\s+[^?]{1,80}['’]s\s+|\bhow\s+much\s+did\s+.{1,80}\s+raise\b/i;
  if (!namesCompany.test(query)) {
    return { code: "Incomplete", message: "Name one company and ask for a specific financing measure." };
  }
  if (!/\b(total|sum|average|mean|minimum|min|max|maximum|latest|amount|size|to date|how much)\b/i.test(query)) {
    return { code: "Incomplete", message: "Specify the total, average, minimum, maximum, latest value, or IPO amount." };
  }
  return null;
}

export function renderMarkdown(markdown) {
  const lines = markdown.split("\n");
  const blocks = [];
  for (let index = 0; index < lines.length;) {
    const line = lines[index];
    if (!line.trim()) {
      index += 1;
      continue;
    }
    if (/^##\s+/.test(line)) {
      blocks.push(`<h2>${renderInline(line.replace(/^##\s+/, ""))}</h2>`);
      index += 1;
      continue;
    }
    if (isTableRow(line) && index + 1 < lines.length && isTableDivider(lines[index + 1])) {
      const headers = tableCells(line);
      index += 2;
      const rows = [];
      while (index < lines.length && isTableRow(lines[index])) {
        rows.push(tableCells(lines[index]));
        index += 1;
      }
      blocks.push(
        `<table><thead><tr>${headers.map((cell) => `<th>${renderInline(cell)}</th>`).join("")}</tr></thead>` +
        `<tbody>${rows.map((row) => `<tr>${row.map((cell) => `<td>${renderInline(cell)}</td>`).join("")}</tr>`).join("")}</tbody></table>`
      );
      continue;
    }
    const paragraph = [line];
    index += 1;
    while (index < lines.length && lines[index].trim() && !/^##\s+/.test(lines[index])) {
      if (isTableRow(lines[index]) && index + 1 < lines.length && isTableDivider(lines[index + 1])) break;
      paragraph.push(lines[index]);
      index += 1;
    }
    blocks.push(`<p>${renderInline(paragraph.join(" "))}</p>`);
  }
  return blocks.join("");
}

function renderInline(value) {
  return escapeHtml(value)
    .replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>")
    .replace(/`([^`]+)`/g, "<code>$1</code>");
}

function escapeHtml(value) {
  return value
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function isTableRow(line) {
  return /^\s*\|.*\|\s*$/.test(line);
}

function isTableDivider(line) {
  return /^\s*\|(?:\s*:?-+:?\s*\|)+\s*$/.test(line);
}

function tableCells(line) {
  return line.trim().replace(/^\||\|$/g, "").split("|").map((cell) => cell.trim());
}
