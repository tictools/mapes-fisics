# Groups

The group of a feature sets its colour, its distinguishing mark, the kind of geometry it accepts and
where to look for it in Natural Earth. Use the group names exactly as written here (with accents).
New regions list their groups in the order of this table (it becomes the tray order).

The last column is where to search and which Natural Earth classes are an acceptable match.

| Group | Key (CSS/JS) | Colour | Mark | `kind` | Natural Earth: layer (accepted classes) |
|---|---|---|---|---|---|
| Rius | `rivers` | blue `#1E6FE0` | highlighted course | `river` | `rivers` (River, Lake Centerline: segments through lakes) |
| Serralades | `mountains` | red `#C62828` | triangle pattern | `area`, `peak` | `regions` (Range/mtn) |
| Mars | `seas` | turquoise `#00A5B5` | dotted edge | `area` | `marine` (sea); inland seas also in `lakes` (Lake) |
| Penínsules | `peninsulas` | purple `#7B1FA2` | dashed edge | `area` | `regions` (Peninsula, Pen/cape); else `countries` (Admin-0 country, with `largest`) |
| Illes | `islands` | green `#2E7D32` | | `area` | `regions` (Island); else `countries` (one part, with `within`) |
| Planes | `plains` | yellow `#D9A300` | | `area` | `regions` (Plain, Lowland, Basin) |
| Llacs | `lakes` | navy blue `#1A237E` | | `area` | `lakes` (Lake, Alkaline Lake; a lake can have several parts, e.g. Lake Eyre North + South) |
| Deserts | `deserts` | orange `#EF6C00` | | `area` | `regions` (Desert) |
| Estrets | `straits` | black `#111111` | | `line` (manual) | none: a short line across the strait, by hand |
| Golfs | `gulfs` | pink `#E8558A` | dotted edge | `area` | `marine` (gulf, bay) |
| Arxipèlegs | `archipelagos` | brown `#795548` | | `area` | `regions` (Island group) |

Kinds:
- `area`: polygon(s) from `source`; highlighted with fill and edge.
- `river`: lines from `source` (layer `rivers`); the dot snaps to the river.
- `line`: hand-drawn line from `coords` (straits); needs `"manual": true`.
- `peak`: a triangle at `dot` (summits, e.g. Everest inside Serralades); needs `"manual": true`.

Drawing order on the map (bottom to top): peninsulas; plains and deserts; seas and gulfs; ranges,
islands and archipelagos; lakes; rivers; straits (`LAYER_ORDER` in `js/app.js`).

## Adding a group

Only with the user's agreement on the name, colour and mark. Then update, together:
- `tools/generate_maps.py`: `GROUPS` (name and allowed kinds).
- `js/app.js`: `GROUP_KEYS` (Catalan name → English key), `GROUP_COLOURS` and `LAYER_ORDER`.
- `css/styles.css`: the `--colour-<key>` variable, and `.hl--<key>`, `.group__swatch--<key>` or
  `.pill--<key>` rules if it has a distinguishing mark.
- `README.md`: the group colours table; and this file.
