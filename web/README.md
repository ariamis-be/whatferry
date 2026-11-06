# whatferry wizard page

The page `whatferry ui` serves: React, Tailwind and shadcn/ui, built with
Vite. The build lands in `../src/whatferry/ui/static/` and is committed, so
running whatferry needs only Python; Node is only for changing this page.

```sh
mise exec -- pnpm install
mise exec -- pnpm build    # type-check, then write ../src/whatferry/ui/static/
```

Every word on the page lives in `src/locales/`, one file per language.
English (`en.tsx`) sets the shape; the other languages are typed against it,
so a missing string fails the build. `src/i18n.tsx` lists the languages:
each one's own name, its BCP 47 tag, the browser languages that pick it, and
whether it reads right to left. Use start/end classes (`ms-`, `ps-`,
`text-start`, `start-`), never left/right, so right-to-left pages mirror,
and flip arrow icons with `rtl:-scale-x-100`.

To add a language: copy `src/locales/en.tsx`, translate it (menu names as
WhatsApp, Android and Apple show them in that language), add a row to
`src/i18n.tsx`, and add its id to `LANGS` in
`../src/whatferry/ui/wizard.py`. `tests/test_ui.py` checks the two lists
match.

Add shadcn components with `mise exec -- pnpm dlx shadcn@4.22.1 add <name>`.

The server's Content-Security-Policy allows only the page's own script, style
and fonts: no inline `<script>` or `<style>`, no CDN. `tests/test_ui.py`
checks the built page against that.
