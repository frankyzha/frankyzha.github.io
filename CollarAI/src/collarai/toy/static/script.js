const loginPanel = document.querySelector("#login-panel");
const screenPanel = document.querySelector("#screen-panel");
const loginForm = document.querySelector("#login-form");
const screenForm = document.querySelector("#screen-form");
const results = document.querySelector("#results");

const api = async (path, options = {}) => {
  const response = await fetch(path, {
    ...options,
    headers: { "Content-Type": "application/json", ...(options.headers || {}) },
  });
  const body = await response.json();
  if (!response.ok) throw new Error(body.detail || `Request failed (${response.status})`);
  return body;
};

const showAuthenticated = (authenticated) => {
  loginPanel.hidden = authenticated;
  screenPanel.hidden = !authenticated;
};

loginForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const message = document.querySelector("#login-message");
  message.textContent = "";
  try {
    await api("/api/login", {
      method: "POST",
      body: JSON.stringify({
        email: document.querySelector("#email").value,
        password: document.querySelector("#password").value,
      }),
    });
    showAuthenticated(true);
  } catch (error) {
    message.textContent = error.message;
  }
});

screenForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  results.dataset.state = "loading";
  document.querySelector("#search-message").textContent = "";
  const selected = (selector) =>
    Array.from(document.querySelector(selector).selectedOptions, (option) => option.value);
  const stages = Array.from(
    document.querySelectorAll('input[name="funding-stage"]:checked'),
    (input) => input.value,
  );
  const numberOrNull = (selector) => {
    const value = document.querySelector(selector).value;
    return value ? Number(value) : null;
  };
  const query = {
    platform: "toy",
    countries: selected("#countries"),
    industries: selected("#industries"),
    founded_year_min: numberOrNull("#founded-year-min"),
    funding_stages: stages,
    total_raised_usd_lt: numberOrNull("#raised-less-than"),
    limit: Number(document.querySelector("#result-limit").value),
  };
  try {
    const body = await api("/api/search", { method: "POST", body: JSON.stringify(query) });
    render(body);
    results.dataset.state = "complete";
  } catch (error) {
    document.querySelector("#search-message").textContent = error.message;
    results.dataset.state = "error";
  }
});

const render = ({ companies, filters }) => {
  const chips = [
    ...filters.countries,
    ...filters.industries,
    ...filters.funding_stages,
    ...(filters.founded_year_min ? [`Founded ≥ ${filters.founded_year_min}`] : []),
    ...(filters.total_raised_usd_lt
      ? [`Raised < $${filters.total_raised_usd_lt.toLocaleString("en-US")}`]
      : []),
  ];
  document.querySelector('[data-testid="active-filters"]').innerHTML = chips.length
    ? chips.map((value) => `<span class="chip">${escapeHtml(value)}</span>`).join("")
    : "None";
  document.querySelector('[data-testid="result-count"]').textContent = companies.length;
  document.querySelector("#company-rows").innerHTML = companies
    .map(
      (company) => `
        <tr data-company data-founded-year="${company.founded_year}"
            data-total-raised-usd="${company.total_raised_usd}"
            data-source-url="${escapeHtml(company.source_url)}">
          <td class="company-name">${escapeHtml(company.name)}</td>
          <td class="company-country">${escapeHtml(company.country)}</td>
          <td class="company-industry">${escapeHtml(company.industry)}</td>
          <td>${company.founded_year}</td>
          <td class="company-stage">${escapeHtml(company.funding_stage)}</td>
          <td>$${company.total_raised_usd.toLocaleString("en-US")}</td>
        </tr>`,
    )
    .join("");
};

const escapeHtml = (value) =>
  String(value).replace(
    /[&<>'"]/g,
    (character) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", "'": "&#39;", '"': "&quot;" })[
      character
    ],
  );

api("/api/session")
  .then(({ authenticated }) => showAuthenticated(authenticated))
  .finally(() => {
    document.body.dataset.ready = "true";
  });
