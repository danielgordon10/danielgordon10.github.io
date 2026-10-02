# Design review checklist

Running list of requested changes. Checked off only once verified in `dist/`.
Rebuild with `uv run site build --force`, then refresh.

**How this file works:** every request gets a line here before or as it is
started, and gets checked off only after the change is verified in a built
page. If a request is not on this list it has not been asked for; if it is on
this list unchecked it is still owed. When this file and reality disagree,
reality wins and the file is wrong.

Last verified: build green, 25 files / 81 total / 119.5 MB; behaviour 94/94;
layout 8 problems (About lab tap targets only). Also swept 8 pages across both
themes at 1440 and 390 for broken images, unrendered Jinja, console errors and
failed requests: none. Typecheck clean.

## Open

### DO THIS FIRST — sticky bars
- [x] **Sticky bars are now opaque. Done, verified, asked for three times.**
      - `assets/ts/site.ts` — `MAX_VEIL` raised **52 → 100**. The ramp itself is
        kept: `--header-veil` measures 0% at scrollY 0, 28.6% at 40, 57.1% at 80,
        85.7% at 120, 100% by 160. So the hero image still runs under the header
        untouched at the top of the page, and the bar is a solid slab once
        scrolled. Only the resting state stays see-through.
      - `assets/css/site.css` `.section-head--sticky` — was reading the header's
        three ramped properties off `:root` for its glass fill; now plain
        `background: var(--bg)`, `backdrop-filter` deleted. Computed:
        `backdrop=none`, bg `rgb(251,251,253)` light / `rgb(10,12,18)` dark.
      - `assets/css/site.css` `.filters` (the `/work/` bar) — was `86%` +
        `blur(14px) saturate(180%)`; now plain `background: var(--bg)`.
      - The `--header-veil` / `--header-blur` / `--header-sat` custom properties
        are still written to `:root` because the header hairline scales its
        alpha with `--header-veil`. The heads no longer read them.
      Measured at the header/head boundary, both themes, `/` and `/work/`: the
      only remaining step is the header's own 1px `border-bottom` hairline, and
      the bars on either side of it now paint the **identical** colour, so there
      is no material change any more — just the intentional divider.
      Verified with JS disabled: heads and filters both render opaque
      (`rgb(10,12,18)`, `backdrop=none`) without needing a fallback fill, which
      the glass version required.
      Behaviour 94/94, typecheck clean. Layout still 18 — all pre-existing
      tap-target warnings, unchanged by this.

### In progress, do not treat as done
- [x] ~~Reversal~~ — superseded by the DO THIS FIRST item above, which carries
      the full detail and exact line references. The original verdict stands:
      the shared glass on the section heads left a visible line between the two
      bars, so the direction reversed to **both fully opaque**, with the top bar
      still ramping but topping out at 100% so it meets the opaque section head
      cleanly.
- [x] Pruned unused content out of the YAML and the code that served only it.
      Verified unused first — no reference anywhere in `templates/`, `sitegen/`
      or `tools/` — then removed together with its model field.
      Data: all 10 tag `description:` values; both `education.yaml` `detail:`
      blocks; `site.short_title` and `site.footer_note`; `person.pronouns`,
      `social.id` and `hero:` on all five socials; `featured: false` in
      `apple.yaml` and `splitnet.yaml` (already the default); `tags: []` in
      `dlip.yaml`. The two `education.detail` blocks were the only place the PhD
      advisor and the undergrad GPA / class rank were written down, and the tag
      descriptions were unused copy — both removed at the user's instruction to
      delete everything unused.
      Dead code: `Tag.description`, `Education.detail`, `Site.short_title`,
      `Site.footer_note`, `Person.pronouns`, `Social.id`, `Social.hero`,
      `Item.year`, `Item.primary_link`, `TypeMeta.plural`, `Link.is_external`,
      `Link.target_blank`, `Data.type_counts`, `Data.years` (passed to
      `work.html`, which never read it), and `GalleryEntry` in `data.py`, an
      unused duplicate of `GalleryImage`.
      `LinkKind` cut from ten members to the five in use (`paper`, `code`,
      `demo`, `project`, `course`). `other` went with them and `Link.kind` is
      now required with no default: every link in the data declares one, so the
      default only masked a forgotten field behind a generic chain-link icon.
      16 unreferenced icons removed, 38 → 22. `extra="forbid"` means a stale
      YAML key is a build error, so the data edits could not silently rot.
      Kept, flagged rather than deleted: `venue` on the two positions reads as
      the item-page badge; `authors: [Daniel Gordon]` on `thesis`/`tetris`/`dlip`
      renders your own name as the byline.
- [x] Fixed the stale `apple.yaml` header comment — it claimed the card "is
      filtered by the `industry` and `3d-perception` tags", and neither tag has
      ever existed in `tags.yaml`.

### From this session
- [ ] **NEEDS CLARIFICATION — "compressed view" does not exist in this codebase.**
      Asked for: "for the titles in the compressed view, add some top padding to
      the titles, and reduce padding of the name, pub, date sections, except for
      bottom padding before tags", then "switch to the compressed view at 840px".
      Grepped `compact|compress|dense` across css/templates/data. The only real
      match is `.contact-card--compact` (a contact-card modifier, unrelated).
      The word maps loosely onto the `<=640px` mobile `.row` treatment, which is
      the one place titles/sub/venue/date/chips are re-spaced and re-ordered —
      but "name, pub, date" does not match that markup either (it has
      `.row__sub`, `.row__venue`, `.row__when`). Do not guess at this. Ask which
      element is meant before touching spacing.
- [x] Dark-mode seam where the hero meets Featured — **fixed, cause was the
      grain, not the hero image or the tint.** `.hero` carries `.grain`, and
      `.grain::after` is `inset: 0` with `mix-blend-mode: overlay`, so it stopped
      dead at the hero's bottom edge. Overlay is not neutral on every backdrop:
      against dark `--bg` (#0a0c12) it *lifted* the pixels, so the last row
      inside the hero painted `(17,18,24)` — lighter than the `(9,12,20)`
      background it was meant to blend into — then the overlay vanished and bg
      took over at full strength. Measured delta 8/channel. On light `--bg`
      (#fbfbfd) the same blend is near a no-op, which is exactly why this only
      ever appeared in dark mode.
      Ruled out first, with measurements: `.hero__glow` (ends 469px *above* the
      hero's bottom edge, cannot touch the boundary — my first hypothesis was
      wrong), and `--hero-tint` (does end on `var(--bg)`). Removing the grain
      alone took the step to 3, and the tint was innocent.
      Fix: `mask-image: linear-gradient(180deg, #000 0 75%, transparent 100%)`
      on `.grain::after`, fading the overlay over the bottom quarter. Verified
      after rebuild — dark `(10,12,17)` → bg `(9,12,20)`, worst step **8 → 3**;
      light 4 → 3; mobile 390px both themes step 3.
- [x] Linked "Apple" and "Third Wave Automation" in the homepage description
      (`data/person.yaml` `intro`, rendered by `home.html:20` and `about.html:21`
      through the same `md` filter). Markdown links, so they inherit the existing
      external-link handling in `sitegen/render.py:56-63` —
      `target="_blank" rel="noopener noreferrer"`. Kept inside the existing
      `**bold**`. URLs: apple.com, thirdwave.ai (the latter matching the existing
      "Company" link on `data/items/thirdwave.yaml:38`). Verified visible in both
      themes, accent-coloured, 49x21 and 195x21.
- [x] Removed the unused `Person.headline` field and its copy — "I build
      perception systems that turn messy real-world imagery into usable 3D
      understanding…". Confirmed zero template reads; the only other `headline`
      hits are `sitegen/build.py:307` (`item.title` in JSON-LD) and a CSS comment
      on `.hero__glow`. Deleted from `data/person.yaml`, `sitegen/models.py:418`,
      and from the `_markdown_ok` validator list at `models.py:465`. Rendered
      output byte-identical, as expected.
- [x] 18 tap-target warnings, all the same one thing: inline prose links inside
      a running paragraph, 20–21px tall against a 24px minimum. Ten are the
      Apple / Third Wave Automation links in the hero intro, eight are "RAIVN
      Lab" / "RSE Lab" in About. All are inside a sentence with text on both
      sides, which is the case WCAG explicitly exempts (2.5.8 exempts targets
      "in a sentence or block of text"). Padding a paragraph to reach 24px would
      cost line height and break the rhythm of the text it is meant to protect,
      so the audit now skips them instead. Layout audit is 18 → **0**.
      The exemption is `isInlineInText()` in `tools/audit_layout.py`: it needs
      `display: inline`/`inline-block`, walks up to the nearest block text
      container (the walk is needed because `authors()` wraps names in
      `<span class="me">`), requires that container to hold more text than the
      link does, and bails on any link wrapping an `img`/`svg`. Verified against
      a fixture page with the real rule, so it is not a blanket suppression: prose
      link, link inside `<strong>`, and link in a text list item are all skipped,
      while a `display: block` link at 18px, a 16px `<button>`, and 16x16 icon and
      image anchors are all still caught.
- [x] Confirm homepage CTA reads "All Work", not "All work".
- [x] IQA summary: award sentence removed. It read "Received the NVIDIA
      Pioneering Research Award at CVPR 2018" — the award belongs in the venue
      line's CVPR 2018 context, not restated in the description, and the second
      sentence was pure credential. The list row now reads as one sentence about
      what IQA is.
- [ ] Rename `_check_featured_order` in `sitegen/data.py` — the name no longer
      matches what it does.
- [ ] Decide whether to delete the now-dead gallery code. Apple was the last
      item with a gallery, so `templates/item.html:122` and `.gallery` in
      `site.css:1688` are unreferenced, and the behaviour audit has no gallery
      coverage left to regress.

### This round: hero contrast, thesis, mobile spacing
- [x] Light-mode hero text was unreadable over the photo, and the links were
      worse than the prose. Measured across every pixel the intro covers at
      1440px, rather than against a flat swatch:

      | colour | role | mean | p05 | worst |
      | --- | --- | --- | --- | --- |
      | `--text-2` #4a5162 | intro prose (was) | 4.63 | 2.58 | 2.44 |
      | `--accent` #4a56d2 | links (was) | 3.45 | 1.92 | **1.81** |
      | `#1e2230` | intro prose (now) | 9.23 | 5.15 | 4.85 |
      | `#191e58` | links (now) | 8.95 | 5.00 | 4.71 |

      Both now clear AA (4.5) at the worst pixel in the block, where neither
      previously got near it. Scoped to `[data-theme="light"] .hero__intro` and
      its links only — the accent is fine on flat surfaces, and dark mode was
      left untouched at the user's request (dark intro measures mean 6.66).
- [x] `thesis.jpg` finally wired up: `media.image` with alt text, so the Thesis
      page shows the image the way every other publication does — no video. The
      28th and last unreferenced static file is gone from the list. Still 1.1MB
      at 1832x1600; downscaling is the obvious next win but is an image edit.
- [ ] Thesis image alt text is written but unverified — I cannot see the image,
      so the alt is a description of what I was told it shows. Needs a real look.
- [x] Thesis "Thesis record" button relabelled "Publication".
- [x] Thesis Semantic Scholar link added, id
      `c7529d985f272227f8f7435b9afa0f5813dd5701`, built by the same
      `semantic_scholar_url` property every other paper uses. The id-only form
      `/paper/<id>` is what the site already generates and what Semantic Scholar
      redirects, so it matches the existing convention rather than the longer
      slugged URL pasted in. All 14 publications now have the link.
- [x] Mobile date→tags gap: 5px → 17px. The gap is declared as
      `margin-bottom` on `.row__when` rather than `margin-top` on the chips, so
      it reads as "end of the entry" instead of "start of the tags". Everything
      above the date stays packed tight, leaving exactly one clear division in
      the row — the same role the break plays on the desktop row.
- [x] Homepage CTA confirmed as "All Work".
- [ ] Remaining open from this round: 18 inline-prose tap targets (see above,
      wants a decision), DL-class is closed, IQA is closed, hero contrast is
      closed, thesis image needs a real alt text check.

### This round: header logo alignment
- [x] The "DG" mark sat top-aligned against the theme switcher and the hamburger
      rather than centred, because it was 30px and both buttons are 34px — the
      buttons hung 3px below it (measured at 390px: mark centre 28.0, buttons
      31.0). It looked like a logo pinned to the top of the bar.
      Fixed by growing the mark to **38px** rather than shrinking the buttons,
      which keeps their 34px tap targets.
      38px is not arbitrary: the header `.wrap` is baseline-aligned, so the line
      box is as tall as its tallest item. At 34px the nav links' 36px boxes still
      set the height and the buttons, centring in that box, left the mark 0.6px
      high. At 38px the mark is the tallest item and everything centres on one
      line. Measured, light and dark, at 1440 / 1024 / 768 / 390:

      | pair | before | after |
      | --- | --- | --- |
      | mark ↔ name centre | +0.0 | +0.0 |
      | mark ↔ theme switcher centre | +3.3 (390px) | +0.0 |
      | mark ↔ hamburger centre | +3.0 (390px) | +0.0 |

      `.brand` moved from `align-items: baseline` to `center`, with the mark on
      `align-self: center` so it no longer contributes the brand's baseline.
      Baseline alignment was only ever holding the mark and name together by
      coincidence at 30px; at 38px it hangs the mark off the name's baseline and
      pushes the name low inside the square.
- [x] Restored the name↔nav baseline that growing the mark cost. The taller mark
      moved the brand's baseline up and left the nav 1.2px high of the name
      (+1.00px → +2.19px against the value this site tuned to). `.nav` takes
      `position: relative; top: 1.2px`, which returns it to +1.00px exactly while
      leaving the mark and name perfectly centred. Nudge measured, not guessed:
      0.6px → +1.59, 1.0px → +1.19, 1.2px → +1.00.
      The residual +1.00px is the original one and is deliberate — the name is
      17px and the nav 14px, so they cannot share a baseline *and* be centred.
- [ ] Not verified visually: the model has no image input, so the screenshots of
      the resized logo (`hdr-desktop.png`, `hdr-mobile.png`) were captured but
      never actually looked at. Everything above is measured geometry. Worth a
      glance to confirm 38px doesn't crowd the name.

### Carried over, not yet done
- [ ] Verify the header nav link colour change (`--text-2` → `--text`) for
      contrast in both themes. The change is in; the measurement was invalid
      and has not been redone.
- [ ] Reduce the work-row gap between the title/content column and the date
      column. Measured 32px at 1440 and 26px at 900, but the perceived slack is
      larger than the grid gap suggests.
- [ ] Darken the homepage intro slightly. Measured 6.36:1 in light and 10.07:1
      in dark, which is why it was left alone, but the request stands.
- [ ] Match the `/work/` filter bar to whatever the top bar settles on. Still
      its own constants (86% fill, 14px blur, 180% saturate). Folded into the
      reversal above rather than tracked twice.
- [ ] Fix the dark-theme favicon. Currently `favicon.svg`, `.ico`, 32/32,
      apple-touch and safari-pinned-tab, no dark variant.
- [ ] Add a no-JS check for the sticky heads if the glass change survives the
      reversal. Dropped as a separate item: with both bars opaque there is no
      fill to fall back on, so the question goes away.
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
- [x] Google Scholar removed from item pages — the per-paper title-search link
      is gone, replaced by the stored Semantic Scholar id. **Correction:** the
      author-level Google Scholar profile is still in `person.yaml` socials and
      still renders in the contact card and footer. That was always intended to
      stay; "removed entirely" in this file was wrong and is what made the item
      and person cases look contradictory.
- [x] Lecture-notes spacing 165px → 36px: nested `<section>` swapped for
      `.item-section`, because the global `section` rule reserves page padding.
- [x] Sidebar restored to a sticky 21rem track; type badges link to filtered
      index views.
- [x] DL-class: the difference was never the date. The list row did show
      "Sep 2019 - Dec 2019". What made this entry unlike every other one was
      that it had no `authors:` at all — it carried `instructor:` plus
      `collaborators:`, which rendered as a second "Instructor / With" line
      below the role instead of the shared author line every other entry uses.
      Converted to a real author list (Ali Farhadi first, then the TAs) and
      dropped the now-redundant `instructor:` field. List row now reads
      "Ali Farhadi, Daniel Gordon, Aaron Walsman+8 more" with the date beneath,
      matching the other entries.

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
      what made the hand-off to Experience feel late. Padding is unaffected by
      the glass reversal and stands.
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
- [x] Muscles: video and project page added. The button row reads Paper, Code &
      Data, Project page, Semantic Scholar. The video needed a vendored poster
      frame at `static/images/video/89r7NkKvUuA.jpg` — every video item has
      one, and without it the build failed on the missing reference. Pulled the
      1280x720 still from `i.ytimg.com` to match the others; that is a
      one-time authoring fetch, not a page-load request. Verified zero YouTube
      requests on load and the iframe appearing only after a click.
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
- [x] DL-class: now a real `authors:` list rendered through the shared
      `authors()` macro — Ali Farhadi, then Daniel Gordon, then the nine TAs.
      Superseded the earlier "Instructor / With" two-line treatment, which made
      this the only entry on the site not using the shared author line.
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
      the gallery removal and the glass experiment. Both passed at 94/94 and 8
      problems immediately before the glass work.
- [ ] One trap worth keeping: the glass experiment inserted its declarations
      above the existing ones and left a second `background: var(--bg)` at the
      bottom of the rule, which won as the later declaration. Computed style
      showed the head fully opaque while the blur still applied, which reads as
      the blur failing rather than as a cascade-order bug. Not a live issue now
      that the glass is being reverted, but the failure mode was silent.

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
