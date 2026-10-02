# Design review checklist

Running list of requested changes. Checked off only once verified in `dist/`.
Rebuild with `uv run site build --force`, then refresh.

**How this file works:** every request gets a line here before or as it is
started, and gets checked off only after the change is verified in a built
page. If a request is not on this list it has not been asked for; if it is on
this list unchecked it is still owed. When this file and reality disagree,
reality wins and the file is wrong.

Last verified: build green, 25 files / 79 total; behaviour 94/94; layout 8
problems (About lab tap targets only). Metrics above are from the tag work; the
blur change below is built and measured but **not yet audited**.

## Open

### In progress, do not treat as done
- [ ] Featured/Experience heads get the top bar's glass. The head was
      `background: var(--bg)` — fully opaque — while the bar above it ramps to
      52% fill / 20px blur / 160% saturate. Rows passing under the head cut off
      at a hard edge, and the head read as a second, heavier bar.
      Done so far: `site.ts` writes `--header-veil` / `--header-blur` /
      `--header-sat` to `:root` instead of the header element, so the head and
      the bar read one source and cannot drift; the head consumes the same three
      properties. Head and bar now compute identically in light and dark
      (`oklab(... / 0.52)`, `saturate(1.6) blur(20px)`).
      **Still owed:** behaviour + layout audits after the change, and a look at
      the rendered screenshots in both themes. One trap worth recording — the
      new properties were inserted above the existing declarations, leaving a
      second `background: var(--bg)` at the bottom of the rule that won as the
      later declaration. Computed style showed the head fully opaque while the
      blur still applied, which looks like the blur failing rather than a
      cascade-order bug. Removed.
- [ ] Head defaults are the ramp's ceiling (52% / 20px / 160%), not its floor.
      A head only becomes visible long after RANGE, so it is always stuck by the
      time it is seen; the fallback only matters with JS off, where a 0% fill
      would let rows show through unguarded. Needs a no-JS check.

### From this session
- [ ] Fix the 8 About tap-target warnings — "RAIVN Lab" and "RSE Lab" render
      20–21px tall against a 24px minimum. Inline prose links inside a
      paragraph, so the fix is vertical padding on the anchor, not a block.
- [ ] Confirm homepage CTA reads "All Work", not "All work".
- [ ] Decide whether IQA's two-sentence summary should be one sentence.
- [ ] Rename `_check_featured_order` in `sitegen/data.py` — the name no longer
      matches what it does.
- [ ] Decide whether to delete the now-dead gallery code. Apple was the last
      item with a gallery, so `templates/item.html:122` and `.gallery` in
      `site.css:1688` are unreferenced, and the behaviour audit has no gallery
      coverage left to regress.

### Carried over, not yet done
- [ ] Verify the header nav link colour change (`--text-2` → `--text`) for
      contrast in both themes. The change is in; the measurement was invalid
      and has not been redone.
- [ ] Reduce the work-row gap between the title/content column and the date
      column. Measured 32px at 1440 and 26px at 900, but the perceived slack is
      larger than the grid gap suggests.
- [ ] Darken the homepage intro slightly. Measured 6.36:1 in light and 10.07:1
      in dark, which is why it was left alone, but the request stands.
- [ ] Match the `/work/` filter bar to the same glass. Still its own constants
      (86% fill, 14px blur, 180% saturate), untouched by the `:root` change.
- [ ] Add a dark-theme favicon variant. Currently `favicon.svg`, `.ico`,
      32/32, apple-touch and safari-pinned-tab, no dark variant.
- [ ] Delete the unreferenced files in `static/`, mostly
      `static/images/homepage/` and `static/images/info_images/`. They are
      carried over from the old site and referenced by nothing. The count was
      24 files / 19.6 MB; removing the Apple gallery took it to 27 files,
      because `apple_maps1.jpg`, `apple_maps2.png` and `apple_maps3.png` are now
      unreferenced too. `site check` passes either way — it reports these but
      does not fail on them.

## Recently done

### Item pages
- [x] Semantic Scholar is now a real per-paper link, not a title search.
      Ids came from the author's own Scholar profile
      (`author/152462964/papers`), not title search, because search results
      are relevance-ordered and a same-titled paper by another group can
      outrank yours. Stored as `semantic_scholar` in the item yaml, validated
      as 40 hex chars so a bad paste fails the build.
- [x] 13 of 14 publications have the link. `thesis` does not — it is not on
      the Scholar profile, so there is no id and inventing one would 404.
- [x] The Scholar button moved up to the button row, last, so it reads
      Paper, Code, Semantic Scholar. It was a small link beside the
      copy-BibTeX button.
- [x] Google Scholar removed entirely.
- [x] Lecture-notes spacing 165px → 36px: nested `<section>` swapped for
      `.item-section`, because the global `section` rule reserves page padding.
- [x] Sidebar restored to a sticky 21rem track; type badges link to filtered
      index views.
- [ ] DL-class item page: the list row shows no date where the item page shows
      "Sep 2019 - Dec 2019" correctly. Verified as correct on the item page, so
      the remaining question is whether the list row is meant to show it at all.
      Earlier marked open as "decide the date"; the date itself is not the bug.

### Chrome
- [x] Header words share a baseline with the name. `align-items: center` was
      lining the boxes up within half a pixel while the baselines sat ~2px
      apart. `.site-header .wrap` and `.nav` now use `baseline`; `.brand` too,
      because a flex container takes its baseline from its first child and
      that was the mark, not the name. `.icon-btn` opts out with
      `align-self: center` — a fixed-size square has no text baseline.
- [x] Nav links `--text-2` → `--text`.
- [x] Backdrop-filter seam fixed: fill, blur and saturation now all ramp from
      a true no-op at scrollY 0 over 140px. The constant `saturate(160%)` was
      what made the top of the bar visibly different from the page.
- [x] Hero pulled up under the sticky header, so its image starts at y=0
      instead of leaving a bare-background seam.
- [x] Featured/Experience title padding: +20px above and below, then the bottom
      was walked back to 0.85rem at the user's request. Top is 31.2px, bottom
      13.6px. The top needed care — the head pairs positive padding with an
      equally negative margin so its box is full-bleed, and an exactly matching
      negative margin swallows every added pixel and moves nothing. The margin
      stays at `-0.7rem` while the padding grows past it, so the 20px reads as
      space above the title and the fill still starts above the section.
      Bottom ended asymmetric on purpose: the 20px there made the fill tall
      enough to park the sticky head for most of the section's scroll, which is
      what made the hand-off to Experience feel late.
- [x] Profile photo: rounded corners via CSS crop. The source JPEG has a baked-in
      teal border ~6% wide, so `.contact-card__frame` clips a `scale(1.12)`
      image inside `overflow: hidden`. The file itself is untouched. Card, frame
      and photo all compute 14px; corner scans find zero frame-background
      slivers at 1440 and 390.
- [x] "DG" mark nudged `-0.1em` to stay on the name's optical centre under
      baseline alignment.

### Work index and rows
- [x] Filter chips sort by item count, descending, with a lowercase-label
      tiebreak. They were alphabetical, which read as arbitrary: "Computer
      Vision" with 15 sat between "Datasets & Benchmarks" with 3 and "Embodied
      AI" with 10, scattering the biggest choices through the bar. Sorting lives
      in `sitegen/data.py:tag_groups` via a new `_tag_use` helper, so ties stay
      stable when two tags are equally common.
- [x] Apple: gallery removed, main image only. `apple_maps1.jpg`,
      `apple_maps2.png` and `apple_maps3.png` were images 2–4 in DOM order. The
      gallery is optional and `templates/item.html` guards on it, so no empty
      `.gallery` container is left behind. Verified at 1440 and 390: one image,
      16:9 box held, no overflow. Build dropped 82 files / 74.6 MB → 79 / 69.6 MB.
- [x] Tag edits: `vision-language` added to Apple, `robotics` removed from VSP,
      `planning` and `representation-learning` added to IQA. Robotics 6 → 5,
      Planning 5 → 6, Representation Learning 4 → 5, Vision & Language 4 → 5.
      The Robotics filter now returns 5 items with VSP absent from it.
- [ ] IQA is a judgment call, flagged rather than resolved: it now carries 9 of
      the site's 10 tags, the most of any item. Fine if the tags describe the
      work, but they have stopped discriminating — Computer Vision, Embodied AI,
      Reinforcement Learning, Representation Learning, Vision & Language and
      Open Source all return IQA.
- [x] Tag filters are OR, not AND. Reinforcement learning 5, robotics 4, union
      9. Regression-tested.
- [x] Mobile rows stack: full-width 16:9 media above full-width title, content
      and date. Abstracts stay hidden. No overflow at 360/390/480/640.
- [x] Desktop media centred, landscape 4:3, `clamp(224px, 24vw, 360px)`.
- [x] Date column sizes to the widest range, 45px inset, vertically centred.
- [x] Apple badge spacing to the timeline `Current` badge: 14px.
- [x] Singapore DCE link removed from Apple Maps 3DV.

### Content and data
- [x] New CV picked up and served. The site serves `static/cv.pdf`; the root
      `cv.pdf` is the one you edit and nothing in the build read it, so a new
      version dropped there silently left the old PDF live. Now copied across
      (MD5 `13c4d62f…`, 216,323 bytes) and `site check` errors if the two ever
      diverge again.
- [x] DL-class: Daniel Gordon listed first among collaborators, rendered
      through the shared `authors()` macro. Instructor line reads
      `Instructor Ali Farhadi · With Daniel Gordon, Aaron Walsman, ...`.
- [x] DL-class dates Sep–Dec 2019; same-year ranges now show both months.
- [x] Stale site-wide Featured/Experience gap removed.

### Cleanup
- [x] Deleted the legacy hand-written site: 6 root HTML files, `papers/` and
      `other/` (24 files), 4 one-off Python scripts, `featured_projects.json`,
      `export_website.sh`, the old CSS/JS/font assets under `assets/`, and
      `images/` + `pdfs/`. `cv.docx` and `cv.odt` kept deliberately.
      The new generator reads none of it.
- [x] Behaviour audit's portrait check now measures the frame, so the
      deliberate scale-crop is not counted as dead space.
- [ ] The audit's portrait check and the layout audit have not been re-run since
      the gallery removal and the blur change. Both passed at 94/94 and 8
      problems immediately before the blur work.

## Standing constraints

- Do not commit or push without explicit authorisation.
- Deployment still needs Pages switched from branch source to GitHub Actions.
  Until that happens the live site is served from the repository root, which
  no longer contains any HTML.
- Regular hyphens in site text, never em or en dashes.
- Do not remove tags unless explicitly identified as wrong.
- Semantic Scholar links use stored per-paper ids. Do not fall back to title
  search: search is relevance-ordered and a same-titled paper by another group
  can outrank yours. Google Scholar is removed entirely.
- Keep the responsive portrait `srcset`, static-reference checks, contact-card
  parity between `/` and `/about/`, unreferenced legacy assets, numeric-entity
  email encoding and Unicode-escaped JSON-LD.
