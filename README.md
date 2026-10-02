# danielgordon10.github.io

The personal site for **Daniel Gordon** — publications, projects, roles and
background, built as a static site and published with GitHub Pages.

Live site: <https://danielgordon10.github.io/>

The site is generated from the YAML files in [`data/`](data). There is no
hand-written HTML to keep in sync: every page is produced by
[`sitegen/`](sitegen) and written to `dist/`, and `dist/` can be deleted at any
time and rebuilt from scratch.

## Quick start

```sh
uv sync                 # Python dependencies
npm ci                  # esbuild + typescript, for the client

uv run site check       # validate the content in data/
npm run typecheck       # type-check the TypeScript in strict mode
uv run site build       # generate dist/
uv run site serve       # preview dist/ at http://localhost:8000
```

`uv run site build` compiles `assets/ts/site.ts`, renders every page, copies
the assets that are actually referenced, and then re-reads the generated HTML
to confirm every internal link resolves. A build with a broken link fails
rather than shipping.

While working on the stylesheet or the client:

```sh
npm run watch           # rebuild assets/js/site.js on save
```

## Editing content

Nearly everything on the site comes from one of these files, and nothing is
duplicated between them.

| File | What it controls |
| --- | --- |
| [`data/person.yaml`](data/person.yaml) | Name, headline, bio, contact links, socials, CV, portrait |
| [`data/site.yaml`](data/site.yaml) | Site title, description, navigation, theme, SEO, analytics |
| [`data/items/*.yaml`](data/items) | One file per publication, position, course, talk or project |
| [`data/tags.yaml`](data/tags.yaml) | The tag vocabulary and how tags are grouped |
| [`data/education.yaml`](data/education.yaml) | Degrees shown on the about page |
| [`data/gallery.yaml`](data/gallery.yaml) | Image gallery on the about page |

### Adding a paper

1. Create `data/items/<slug>.yaml` — copy an existing one as a starting point.
2. Fill in the fields. `uv run site check` will tell you about anything missing
   or misspelled, including tags that are not in `data/tags.yaml`.
3. Give it a `bibtex` block and a `paper` link so it can be cited and copied.
4. Rebuild. The home page, the work index, the sitemap and the search index all
   pick it up with no further edits.

The schemas are strict: an unknown key is an error, not a silent no-op. That way
a typo such as `athtors` fails the build instead of quietly dropping a field.

### Positions

A `position` item needs `date` and, if the role has ended, `end`. An item with no
`end` is treated as current, is sorted to the top of the experience timeline, and
is badged "Current".

```yaml
id: apple
type: position
title: "Apple Maps 3DV"
org: "Apple"
role: "Senior Machine Learning Engineer"
date: 2024-04-01
# no `end` - this is the current role
```

### Images

Put files in [`static/`](static) and refer to them from `data/` with a
root-relative path such as `/images/projects/vince.jpg`. Anything under
`static/` that no item references is left out of the build, so
`uv run site check` lists unused files rather than silently copying them.

## Front end

- `assets/css/site.css` — the whole design system, light and dark, no framework
- `assets/ts/site.ts` — the only JavaScript: theme toggle, mobile nav, filtering,
  search, scroll reveals, video facade, copy buttons
- `templates/` — Jinja templates; `base.html` holds the document shell
- `static/fonts/` — self-hosted Inter and Newsreader

The site works with JavaScript disabled: all 18 items are listed on `/work/`,
every page is reachable, and the only things lost are the filter, the search box
and the theme toggle. Nothing that carries content depends on the script.

Two details worth knowing:

- The theme is applied by a small inline script in `<head>` **before** the
  stylesheet loads, so a returning visitor never sees a flash of the wrong
  theme. The choice is stored in `localStorage` under `theme`.
- YouTube embeds are a poster with a play button. No request is made to Google
  until the video is actually started, and the embed uses `youtube-nocookie.com`.

## Auditing

Two browser-driven checks are available. They need a real Chrome and a served
build. Start the preview in one terminal and point the audits at it:

```sh
uv run site build --force
uv run site serve &
```

```sh
# layout: overflow, clipped text, tap targets, images, fonts, heading order,
#         and WCAG AA text contrast in both light and dark
uv run --with playwright python tools/audit_layout.py http://localhost:8000

# behavior: theme persistence, filtering, search, video facade, copy buttons
uv run --with playwright python tools/audit_behavior.py http://localhost:8000
```

Both exit non-zero on failure, so they can be wired into a pre-commit hook or CI
if you want them to run automatically. The contrast check skips elements that sit
on a gradient or an image, since a ratio cannot be reduced to a single color
there.

## Deployment

[`.github/workflows/pages.yml`](.github/workflows/pages.yml) validates the data,
builds `dist/`, and deploys it to GitHub Pages on every push to `master`.

The first deployment needs a one-time setting in the repository:
**Settings → Pages → Build and deployment → Source → GitHub Actions**. Until
that is changed, GitHub Pages keeps serving the repository root and the
hand-written legacy pages.

Because of that, the legacy files at the repository root have deliberately been
left in place. They can be removed once the new site is live and verified.
