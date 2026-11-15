# Instructions for agents

Interactive physical maps (plain HTML, CSS and JS, no build step). See `README.md` for the structure.

## Workflow

- **Never commit without the engineer's explicit authorisation.** Leave the changes in the
  working tree, summarise them and ask. An authorisation covers only the commit it was given for,
  never later ones; a plan or a skill that says "commit" is not an authorisation. The same applies
  to `git push`, merging, rebasing, amending, tagging and opening pull requests.
- Do not touch uncommitted changes you did not make: leave them out of your commits and mention them.

## Generating or changing maps

To add a region, change the features of a region or change a map's framing, follow
`.claude/skills/generar-mapa/SKILL.md` (with its `references/`). In short:

- Each map is defined in `tools/regions/<id>.json` and generated into `data/<id>.js` by
  `tools/generate_maps.py` from Natural Earth. Never edit `data/*.js` by hand.
- `python3 tools/find_ne.py "<name>"` finds a feature in the Natural Earth layers;
  `tools/regions/names.json` maps Catalan names to their sources.
- `python3 tools/generate_maps.py --check` validates every config before generating.
- Never invent coordinates: ask the user about ambiguous or missing features.
- Do not commit `tools/natural-earth-vector/`.

## Clean code (JavaScript and Python)

- **No literals in the logic: extract them as named constants** at the top of the file (or of the
  section that owns them), grouped by meaning. This covers numbers (sizes, distances, timings,
  tolerances), user-facing texts, CSS classes, element ids and selectors, routes, storage keys,
  file names and any value with a meaning of its own.
  Exempt: `0`, `1`, `-1`, `''` and booleans used as themselves (first item, increment, empty);
  DOM and SVG vocabulary (tag, attribute and event names such as `'div'`, `'d'`, `'click'`);
  and the data in `tools/regions/*.json`.
- **No mental mapping: name every variable for what it holds.** `segment => segment.foo`, never
  `s => s.foo`; `feature`, `group`, `pill`, `rect`, `event`, not `f`, `g`, `p`, `r`, `e`.
  Exempt: `i`/`j` as loop indexes, `x`/`y` for coordinates and `lon`/`lat`.
- Keep `js/app.js` passing `tsc --noEmit --allowJs --checkJs --strict` (see below).

## Checks before handing back JS or Python changes

```bash
npx -y -p typescript@5.6.3 tsc --noEmit --allowJs --checkJs --strict --target es2022 --lib es2022,dom,dom.iterable js/app.js
python3 tools/generate_maps.py --check && python3 tools/generate_maps.py && git diff --stat data/
```

`data/*.js` must not change unless the change was intended. Then check both modes in the browser.

## Conventions

- User-facing text is Catalan; code, comments and docs are British English.
- `js/app.js` is type-checked with `// @ts-check`; the data schema is documented at its top.
- No build step: the files in the repo are the files that are served (JS is not minified; the
  host compresses it).
