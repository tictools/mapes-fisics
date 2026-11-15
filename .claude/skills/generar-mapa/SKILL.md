---
name: generar-mapa
description: Generate or change the physical maps of this project (mapes-fisics) from a list of geographical features. Use it to add a new region (e.g. Àfrica, Amèrica, Oceania), to add, remove or change features of an existing region from a list, or to change a map's framing. Covers both output modes (drag-and-drop activity and reference map), which share the same data.
---

# generar-mapa

Each map is a **region config** (`tools/regions/<id>.json`) turned into `data/<id>.js` by
`tools/generate_maps.py`, using Natural Earth geometry. The page (`index.html`, `js/app.js`) draws the
same data in two modes: the activity (`#/<id>`) and the reference map (`#/<id>/consulta`). So a
region only has to be generated once to get both modes.

Read before starting:
- `references/groups.md`: groups, colours, which kind and Natural Earth layer each group uses.
- `references/ne-layers.md`: the Natural Earth layers, how their names look, and known pitfalls.
- The config schema at the top of `tools/generate_maps.py`.

## When to use it

- Add a new region from a list of features.
- Add, remove, rename or move features of an existing region.
- Change a map's framing (projection centre or extent).

## Input: the list of features

A table or CSV, one feature per row:

| Column | Required | Meaning |
|---|---|---|
| `nom` | yes | Catalan name, exactly as it must appear in the tray and on the label (e.g. `Mar Mediterrani`) |
| `grup` | yes | One of the groups in `references/groups.md` (e.g. `Rius`, `Serralades`) |
| `regió` | yes | The map it belongs to (e.g. `Àfrica`) |
| `name_en` / identifier | no | Natural Earth name or English name, to skip the search |
| `pista` | no | Position hint ("north of X", "the one in Y"), to disambiguate |

## Step by step

### 1. Prepare the tools (once per checkout)

```bash
python3 -c "import numpy" || python3 -m pip install numpy   # or use a virtualenv
test -d tools/natural-earth-vector/geojson || (
  git clone --depth 1 --filter=blob:none --sparse https://github.com/nvkelso/natural-earth-vector tools/natural-earth-vector &&
  cd tools/natural-earth-vector && git sparse-checkout set --no-cone '/geojson/ne_50m_land.geojson' \
    '/geojson/ne_50m_lakes.geojson' '/geojson/ne_10m_rivers_lake_centerlines.geojson' \
    '/geojson/ne_10m_geography_regions_polys.geojson' '/geojson/ne_50m_geography_marine_polys.geojson' \
    '/geojson/ne_50m_admin_0_countries.geojson')
python3 tools/generate_maps.py --check    # baseline: existing regions must report OK
```

`tools/natural-earth-vector/` is git-ignored: never commit it.

### 2. Validate the list

Before searching anything, check and report to the user:
- every group is a known group (`references/groups.md`). A new group needs the user's decision
  (name, colour, mark) and the changes listed in "Adding a group" in that file;
- no duplicate names within a region;
- the region exists, or the user wants a new one (ask for its id and title if unclear).

### 3. Resolve each feature against Natural Earth

For each row, in this order:
1. Look it up in `tools/regions/names.json` (Catalan name → source). If it is there, reuse it.
2. Otherwise search the layer of its group (`references/groups.md`), with the English name:
   ```bash
   python3 tools/find_ne.py "<english name>" --layer <layer> [--near <lon>,<lat>]
   ```
   The output gives the exact `name` to put in the config, the Natural Earth class, the centre and
   the bounding box. Try alternatives (shorter query, local name, other layer from the table) before
   giving up.
3. Classify it:
   - **trobat** (found): exactly one sensible match, of the expected class, in the expected place;
   - **ambigu** (ambiguous): several plausible matches, or the match covers more or less than the
     feature (e.g. a region that includes neighbouring ranges);
   - **no trobat** (not found): no match in any suitable layer.

Ask the user about every ambiguous and not-found feature, in one message, listing the candidates
with their centre and bounding box. **Never invent coordinates or geometry.** A feature without a
Natural Earth equivalent (a strait, a peak, a small area) is defined by hand only with coordinates
the user gives or confirms, and is marked `"manual": true` (see `kind` `line` and `peak`).

### 4. Write `tools/regions/<id>.json`

Copy the layout of `tools/regions/europa.json`: one feature per line, so diffs stay readable.
- `id`: lowercase ascii, used in the route and file name; `title`: Catalan title of the map.
- `projection`: `{"type": "laea", "lon0": .., "lat0": ..}` near the centre of the region.
- `extent`: points (lon, lat) that must be inside the map: corners and the farthest points of the
  region, plus a small margin so labels fit. The map is 1600 units wide; its height follows the extent.
- `graticule` (optional): the defaults (`meridian_lats [-30, 85]`, `parallels [-20, 80]`,
  `parallel_lons [-60, 250]`) only cover Europe and Asia. For regions in the western or southern
  hemisphere set ranges that cover the extent, e.g. Americas: `{"meridian_lats": [-60, 85],
  "parallels": [-60, 80], "parallel_lons": [-180, -20]}`.
- Features, in tray order: grouped by group, groups in the order of `references/groups.md`.
  - `id`: ascii slug of the Catalan name (`Mar Bàltic` → `baltic`; drop "mar", "illes", "península"
    when the rest is unique in the region, as the existing configs do); unique within the region.
  - `source`: list of `{"layer", "name"}` refs; several refs are merged (a sea made of sub-seas, a
    peninsula made of two countries). `"largest": true` keeps only the largest polygon (a country
    without its islands).
  - `dot` (lon, lat): the answer point, well inside the area (not on the edge). Start from the centre
    given by `find_ne.py` and move it if the area is concave. For rivers give a point near the
    middle of the course: it snaps to the river.
  - `label` (lon, lat): where the name goes. Put it beside the area, over the sea or empty land, so
    it does not cover other dots; a leader line is drawn when it is more than 30 units from the dot.
    Without `label`, it goes just above the dot.

### 5. Generate and check

```bash
python3 tools/generate_maps.py --check <id>   # schema, sources and layout; writes nothing
python3 tools/generate_maps.py <id>           # writes data/<id>.js
git diff --stat data/                          # only the regions you meant to change
```

`--check` reports overlapping labels, labels or dots outside the map and empty geometries. The
label size is an estimate: fix every warning by moving labels, then confirm in the browser (step 7).
If you changed the generator, regenerate every region and make sure the other `data/*.js` files
do not change.

### 6. Register the region (only for a new region)

- `js/app.js`: add the id to `MAPS`.
- `index.html`: add a `map-card` to the landing page (title, number of features, links to `#/<id>`
  and `#/<id>/consulta`), and update `<title>` and the meta description if they list the regions.
- `js/app.js` `showLanding()` sets the landing page title: keep it consistent with `index.html`.
- `README.md`: structure section and title if they list the regions.
- `tools/regions/names.json`: add every new Catalan name with its source (same format as the
  existing entries), so other regions can reuse it.

### 7. Verify in the browser

Serve the folder (`python3 -m http.server 8000`) and, at desktop size and at tablet size in portrait
(768×1024):
- `#/<id>/consulta`: every feature is highlighted where it should be, with its own geometry (not a
  neighbour's), and no label covers another label or a dot; toggling each group works.
- `#/<id>`: the tray lists every feature; drop one correctly and one wrongly; the counters change.
- No console errors. Existing regions still load.

### 8. Report to the user

- Features per group (count), and the region total.
- Manual features (with the coordinates used and where they came from).
- Ambiguous / not found features and how each was resolved.
- Anything left to decide or check.

## Conventions

- Groups, colours and distinguishing marks: `references/groups.md`. Do not reuse a colour.
- Choice of Natural Earth layer per group: `references/groups.md` and `references/ne-layers.md`.
- Feature names are Catalan and are shown as given; names over 17 characters wrap onto two lines.
- Ids: lowercase ascii, digits and `_` only.

## Validation checklist

- [ ] `python3 tools/generate_maps.py --check` reports OK for every region.
- [ ] No overlapping labels (checked in the browser, desktop and tablet).
- [ ] Every feature has geometry (or is a manual `line`/`peak`).
- [ ] No duplicate names or ids; every group is known.
- [ ] Unrelated `data/*.js` files are unchanged.
- [ ] Both modes load at desktop and tablet size, without console errors.

## What not to do

- Do not edit `data/*.js` by hand: change the config and regenerate.
- Do not commit `tools/natural-earth-vector/` or a virtualenv.
- Do not invent coordinates, geometry or Natural Earth names: search, then ask.
- Do not change another region's output as a side effect.
