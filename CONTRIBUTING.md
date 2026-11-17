# Contributing

Thanks for helping. whatferry moves people's private chats, so two rules come
before everything else:

- **Never attach a real backup, database, key or screenshot of chats** to an
  issue or pull request. The wizard's Results page has a summary made for
  sharing: counts, versions and file locations, with phone numbers masked.
  `whatferry schema check <database>` prints a database's layout and nothing
  it stores.
- **Nothing may write to a phone or to a backup the user made** unless the
  user asked for that step and confirmed it. Every change keeps that true.

## Setting up

```sh
mise install            # Python, uv, Node and pnpm, at the pinned versions
mise exec -- uv sync
mise exec -- uv run pytest
```

The tests need no phone: they build real `.crypt15` files and Finder-format
backups, encrypted the way iOS encrypts them, and stand in for the phones.
CI runs them on Linux; run them yourself on macOS or Windows when a change
touches what differs by system.

## The wizard page

The page lives in `web/` and is built into `src/whatferry/ui/static/`, which
is committed. After changing it:

```sh
cd web
mise exec -- pnpm install --frozen-lockfile
mise exec -- pnpm lint
mise exec -- pnpm build
```

and commit the rebuilt `static/` folder with the change. CI fails when the
committed build doesn't match `web/`. [`web/README.md`](web/README.md) says
how to add or fix a translation.

## After a WhatsApp update

When WhatsApp changes its database, follow
[`src/whatferry/schemas/CHANGES.md`](src/whatferry/schemas/CHANGES.md):
`whatferry schema check` sorts the changes, and `whatferry schema capture`
records the new layout. A pull request with a new snapshot is very welcome.

## The test kit

[`harness/`](harness/README.md) runs real transfers both ways on two
dedicated test phones. It is not in the package and needs its own kit; you
don't need it to contribute.

## Style

- Plain words in messages and docs: say what happens to the user's phone or
  files.
- The terminal and reports show counts, table names and paths, never message
  text, names or phone numbers.
- Keep changes focused, with a test for what they fix or add.

By contributing, you agree that your contribution is licensed under
GPL-3.0-or-later, as the rest of whatferry is.
