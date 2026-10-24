# whatferry wizard page

The page `whatferry ui` serves: React, Tailwind and shadcn/ui, built with
Vite. The build lands in `../src/whatferry/ui/static/` and is committed, so
running whatferry needs only Python; Node is only for changing this page.

```sh
mise exec -- pnpm install
mise exec -- pnpm build    # type-check, then write ../src/whatferry/ui/static/
```

Every word on the page lives in `src/i18n.tsx`. English sets the shape; the
other languages are typed against it, so a missing string fails the build.

Add shadcn components with `mise exec -- pnpm dlx shadcn@4.22.1 add <name>`.

The server's Content-Security-Policy allows only the page's own script, style
and fonts: no inline `<script>` or `<style>`, no CDN. `tests/test_ui.py`
checks the built page against that.
