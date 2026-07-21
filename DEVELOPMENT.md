# Development

This is a Jekyll site with a deliberately small custom layer on top of Academic Pages.

## Structure

- `_pages/`, `_posts/`, and the collection directories contain content.
- `_layouts/` defines page structure. Reusable fragments belong in `_includes/`.
- `assets/js/site.js` is the global JavaScript entry point.
- `assets/js/theme-toggle.js` is a standalone classic script so theme switching remains independent of the module graph.
- `assets/js/post.js` is loaded only on blog posts.
- `assets/js/modules/` contains one dependency-free ES module per behavior.
- `_sass/_frank.scss` is the custom style entry point.
- `_sass/frank/` contains design tokens and responsibility-based style partials.
- `_includes/footer/custom.html` conditionally loads large third-party libraries only on pages that use them.

The responsive navigation breakpoint is `760px` in SCSS and `761px` for the matching JavaScript desktop query. Keep those values synchronized.

## Checks

```sh
npm run check
docker run --rm -v "$PWD":/src -w /src jekyll-site \
  bundle exec jekyll build --destination /tmp/frank-site --trace
```

For a local preview:

```sh
docker run --rm -p 4000:4000 -v "$PWD":/src -w /src jekyll-site \
  bundle exec jekyll serve -H 0.0.0.0
```

Prefer native browser APIs and existing design tokens. Add a dependency only when it replaces enough custom code to justify its maintenance and download cost.

## CollarAI demo

The `/demo/` page is dependency-free and uses the site's existing monochrome tokens. During local
development it calls `http://127.0.0.1:8787`; start the worker from `CollarAI/` with
`uv run --no-editable collarai-api`. Production uses the protected HTTPS endpoint configured as
`collarai_api_url` in `_config.yml`. Hosted requests require the separate invitation key stored in
the operating system vault; see `CollarAI/docs/WEB_DEMO.md`.

The Pages workflow runs the same JavaScript checks before every production build.
