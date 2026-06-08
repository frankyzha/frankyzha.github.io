---
permalink: /
title: "Yulin (Frank) Zhang"
author_profile: true
redirect_from:
  - /about/
  - /about.html
---

<section class="home-intro">
  <p class="home-eyebrow">Duke University | Computer Science + Mathematics</p>
  <p class="home-title">Building interpretable, reliable AI systems.</p>
  <p class="home-lede">I work across machine learning, NLP, interpretability, AI safety, and secure software systems, with a focus on understanding how intelligent systems reason, search, and fail.</p>
  <div class="home-actions">
    <a class="home-button home-button--primary" href="/files/Frank_Zhang_resume.pdf">Resume</a>
    <a class="home-button" href="/publications/">Publications</a>
    <a class="home-button" href="/blog/">Blog</a>
  </div>
</section>

<section class="home-snapshot">
  <div>
    <span>Current</span>
    <strong>Duke CS + Math</strong>
  </div>
  <div>
    <span>Research</span>
    <strong>NLP, interpretability, AI safety</strong>
  </div>
  <div>
    <span>Engineering</span>
    <strong>ML systems, security, backend tools</strong>
  </div>
</section>

I am an undergraduate at Duke University studying Computer Science and Mathematics, with an expected graduation date of May 2028. I am currently involved in research at DukeNLP, the Interpretable Machine Learning Lab, and the CS+ Program. Recent work includes evaluating AI search agents under search-time contamination, studying internal concept representations in large language models, and designing interpretable multiway-split decision trees.

Before Duke, I studied Computer Science and Mathematics in the Honors Program at the University of Michigan. I have also worked on Android app security and malware detection with the Michigan Institute for Data and AI in Society, computational modeling in the Living Systems Research Lab, casualty prediction research with Columbia University's Data Science Institute, and NLP-powered productivity tools at Cal Poly Pomona's SoftCom Lab.

## Publications

<div class="paper-grid">
{% assign homepage_publications = site.publications | sort: "date" | reverse %}
{% for paper in homepage_publications %}
  <article class="paper-card">
    <p class="paper-meta">{% if paper.status %}{{ paper.status }}{% else %}Published{% endif %}{% if paper.venue %} | {{ paper.venue }}{% endif %}</p>
    <h3><a href="{{ paper.url | relative_url }}">{{ paper.title }}</a></h3>
    {% if paper.excerpt %}<p>{{ paper.excerpt | markdownify | strip_html }}</p>{% endif %}
  </article>
{% endfor %}
</div>

## In-Progress Work

<div class="work-grid">
  <article class="work-card">
    <span>LLM internals</span>
    <h3>Callable concept representations</h3>
    <p>Studying how large language models form internal concept representations, with an eye toward mechanistic explanations of grokking and compression.</p>
  </article>
  <article class="work-card">
    <span>AI search agents</span>
    <h3>Search-time contamination</h3>
    <p>Evaluating whether search agents rely on shallow retrieved artifacts instead of grounding answers in the right evidence.</p>
  </article>
  <article class="work-card">
    <span>Interpretable ML</span>
    <h3>Multiway-split decision trees</h3>
    <p>Designing decision-tree algorithms that reduce depth and decision sparsity while preserving accuracy, expressivity, and clarity.</p>
  </article>
</div>

## Selected Projects

<div class="work-grid">
  <article class="work-card">
    <span>MHacks 2024</span>
    <h3>MentalAI</h3>
    <p>Led a team of 4 to fine-tune GPT-4o mini for mental health support, with a React, TypeScript, Tailwind CSS, MongoDB, and OpenAI API stack.</p>
  </article>
  <article class="work-card">
    <span>Open source</span>
    <h3>Email automation service</h3>
    <p>Built a timed email delivery service with 25K+ downloads, attachment support, embedded images, custom fonts, and lower SMTP latency.</p>
  </article>
</div>

## Latest Blog Note

<div class="blog-teaser-grid">
{% for post in site.posts limit:1 %}
  <article class="blog-teaser">
    <p class="paper-meta">{{ post.date | date: "%B %-d, %Y" }}</p>
    <h3><a href="{{ post.url | relative_url }}">{{ post.title }}</a></h3>
    {% if post.excerpt %}<p>{{ post.excerpt | markdownify | strip_html }}</p>{% endif %}
  </article>
{% endfor %}
</div>
