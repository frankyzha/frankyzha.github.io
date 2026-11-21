---
layout: default
title: "CV"
permalink: /cv/
redirect_from:
  - /resume
---

{% assign cv_pdf = '/files/Frank_Zhang_resume.pdf' | relative_url %}
{% assign asset_version = site.github.build_revision | default: site.time | url_encode %}
<main class="cv-pdf-page">
  <object class="cv-pdf-viewer" data="{{ cv_pdf }}?v={{ asset_version }}#view=FitH&amp;toolbar=1&amp;navpanes=0" type="application/pdf" aria-label="Yulin (Frank) Zhang résumé">
    <div class="cv-pdf-fallback">
      <p>This browser cannot display the résumé inline.</p>
      <a href="{{ cv_pdf }}?v={{ asset_version }}">Open the PDF</a>
    </div>
  </object>
</main>
