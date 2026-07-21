---
layout: archive
title: "PB Demo"
permalink: /demo/
author_profile: false
demo: true
mathjax: true
---

<section class="demo" data-collarai-demo data-api-url="{{ site.collarai_api_url | default: '' }}">
  <form class="demo__form" id="collarai-query-form" novalidate>
    <label for="collarai-query">Research question</label>
    <textarea id="collarai-query" name="query" rows="4" maxlength="500" placeholder="What is Nvidia's average debt raised to date?" required></textarea>
    <div class="demo__access" id="collarai-access" hidden>
      <label for="collarai-access-key">Demo access key</label>
      <input id="collarai-access-key" name="access-key" type="password" autocomplete="off" spellcheck="false" placeholder="Paste your invitation key">
      <span>Kept only for this browser tab.</span>
    </div>
    <div class="demo__form-footer">
      <p>Debt, equity financing, refinancing, IPO, and grant amounts are currently supported.</p>
      <button type="submit">Run research <span aria-hidden="true">↗</span></button>
    </div>
  </form>

  <div class="demo__status" id="collarai-status" role="status" aria-live="polite" data-state="ready">
    <span>Ready</span>
    <p>Enter a complete question or choose an example.</p>
  </div>

  <div class="demo__examples" aria-labelledby="collarai-examples-title">
    <p id="collarai-examples-title">Try an example</p>
    <div class="demo__example-list">
      <button type="button" data-query="What is OpenAI's total grant amount?">
        <span>01</span> What is OpenAI's total grant amount?
      </button>
      <button type="button" data-query="What is Nvidia's total debt raised to date?">
        <span>02</span> What is Nvidia's total debt raised to date?
      </button>
      <button type="button" data-query="What is Nvidia's average debt raised to date?">
        <span>03</span> What is Nvidia's average debt raised to date?
      </button>
      <button type="button" data-query="What is Nvidia's total equity financing transaction amount?">
        <span>04</span> What is Nvidia's total equity financing transaction amount?
      </button>
      <button type="button" data-query="What is Nvidia's IPO amount?">
        <span>05</span> What is Nvidia's IPO amount?
      </button>
    </div>
  </div>

  <article class="demo__result" id="collarai-result" aria-live="polite" hidden>
    <header><span>Result</span><span id="collarai-result-time"></span></header>
    <div class="demo__markdown" id="collarai-result-content"></div>
  </article>

  <footer class="demo__footnote">
    <span>Scope</span>
    <p>This proof of concept performs read-only research. It does not provide investment advice, and missing transaction values are never treated as zero.</p>
  </footer>
</section>
