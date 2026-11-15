# Instructions for agents

Interactive physical maps (plain HTML, CSS and JS, no build step). See `README.md` for the structure.

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

## Conventions

- User-facing text is Catalan; code, comments and docs are British English.
- `js/app.js` is type-checked with `// @ts-check`; the data schema is documented at its top.
