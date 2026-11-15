# Physical maps · Europe, Asia, Africa and the Americas

An interactive activity for placing geographical features on a blank map. Drag each name to its position on the map:

- **If you get it right**, the name disappears from the tray and the area or river is highlighted on the map in its group colour, together with its name.
- **If you get it wrong**, the name returns to its place and an error is counted.

Each map also has a **reference map** (*Mapa de consulta*) with every feature already placed, highlighted and labelled. Its legend lets you hide or show each group and focus on a single feature. You can switch between the activity and the reference map from the top bar.

It works on **computers and tablets**. On a mobile phone it shows a notice, as the screen is too small for the activity.

## Structure

```
index.html          Single page: start screen (one card per region), activity, reference map and notices
css/styles.css      Styles and group colours (CSS variables at the top)
js/app.js           Logic: navigation, SVG map (shared by both modes), drag and drop, legend
data/europa.js      Blank map + features of Europe (generated)
data/asia.js        Blank map + features of Asia (generated)
data/africa.js      Blank map + features of Africa (generated)
data/america.js     Blank map + features of the Americas (generated)
tools/regions/*.json     Config of each map: features, framing and projection
tools/regions/names.json Catalan feature names → Natural Earth sources, reusable between regions
tools/generate_maps.py   Script that generates data/<region>.js from its config and Natural Earth
tools/find_ne.py         Searches the Natural Earth layers for a feature
.claude/skills/generar-mapa/  Step-by-step guide for agents to add or change regions (see AGENTS.md)
```

Routes: `#/<id>` (`europa`, `asia`, `africa`, `america`) opens the activity; `#/<id>/consulta` opens the reference map.

It is plain HTML, CSS and JavaScript with no dependencies or build step. Dragging uses Pointer Events, which work with both mouse and touchscreen.

## Running locally

Open `index.html` directly in the browser, or:

```bash
npx serve .          # or: python3 -m http.server 8000
```

## Changing features or map framing

Each map is defined in `tools/regions/<region>.json`: its title, projection, framing (`extent`) and features (name, group, Natural Earth source, answer point and label position). The schema is documented at the top of `tools/generate_maps.py`, and the generated data format at the top of `js/app.js`. Never edit `data/*.js` by hand. To regenerate the data:

```bash
git clone --depth 1 --filter=blob:none --sparse https://github.com/nvkelso/natural-earth-vector tools/natural-earth-vector
cd tools/natural-earth-vector && git sparse-checkout set --no-cone '/geojson/ne_50m_land.geojson' \
  '/geojson/ne_50m_lakes.geojson' '/geojson/ne_10m_rivers_lake_centerlines.geojson' \
  '/geojson/ne_10m_geography_regions_polys.geojson' '/geojson/ne_50m_geography_marine_polys.geojson' \
  '/geojson/ne_50m_admin_0_countries.geojson' && cd ../..
python3 tools/generate_maps.py --check    # validate configs and sources (requires numpy)
python3 tools/generate_maps.py            # every region; or: python3 tools/generate_maps.py europa
```

## Group colours

| Group | Colour | Distinguishing mark |
|---|---|---|
| Rivers | blue `#1E6FE0` | highlighted course |
| Mountain ranges | red `#C62828` | triangle pattern |
| Seas | turquoise `#00A5B5` | dotted edge |
| Peninsulas | purple `#7B1FA2` | dashed edge |
| Islands | green `#2E7D32` | |
| Plains | yellow `#D9A300` | |
| Lakes | navy blue `#1A237E` | |
| Deserts | orange `#EF6C00` | |
| Straits | black `#111111` | |
| Gulfs | pink `#E8558A` | dotted edge |
| Archipelagos | brown `#795548` | |

Cartographic data: [Natural Earth](https://www.naturalearthdata.com/) (public domain).
