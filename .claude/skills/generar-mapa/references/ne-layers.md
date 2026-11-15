# Natural Earth layers

The generator reads these GeoJSON files from `tools/natural-earth-vector/geojson/` (see SKILL.md,
step 1). The config refers to them by the short layer name and matches the `name` value exactly.

| Layer (config) | File | Name field | Contents |
|---|---|---|---|
| `regions` | `ne_10m_geography_regions_polys` | `NAME` | Physical regions: ranges, peninsulas, islands, plains, deserts, plateaus… |
| `marine` | `ne_50m_geography_marine_polys` | `name` | Oceans, seas, gulfs, bays, straits, channels |
| `lakes` | `ne_50m_lakes` | `name` | Lakes and reservoirs |
| `countries` | `ne_50m_admin_0_countries` | `NAME` | Countries (for peninsulas that coincide with countries) |
| `rivers` | `ne_10m_rivers_lake_centerlines` | `name` | Rivers, in many segments |

Also used for the blank base map (not as feature sources): `ne_50m_land`, and the Plateau and
Range/mtn classes of `regions` as relief shading.

Search with `python3 tools/find_ne.py "<query>" [--layer <layer>] [--near lon,lat]`. It matches the
name, alternative names, English and Spanish names, ignoring case and accents, and prints the value
to copy into `source`. None of the layers has Catalan names: `tools/regions/names.json` is the
Catalan → Natural Earth table, so update it with every new feature.

## Classes (`FEATURECLA` / `featurecla`)

- `regions`: Range/mtn, Peninsula, Pen/cape, Island, Island group, Plain, Lowland, Basin, Desert,
  Plateau, Depression, Delta, Valley, Wetlands, Tundra, Isthmus, Gorge, Foothills, Coast, Geoarea…
- `marine`: ocean, sea, gulf, bay, strait, channel, sound, reef, river.
- `lakes`: Lake, Alkaline Lake, Reservoir.
- `rivers`: River, Lake Centerline.

## Known pitfalls

- **Name style varies.** Large regions are in capitals (`ALPS`, `HIMALAYAS`, `BALKAN PEN.`), smaller
  ones are not (`Balkan Mts.`, `Corse`, `Sicilia`), and some use local names or typographic
  apostrophes (`RUB’ AL KHALI`). Always copy the name from `find_ne.py`.
- **A region can be bigger or smaller than the feature.** Compare the bounding box with the feature;
  if it does not fit, it is ambiguous: ask. Some features need several refs (Carpathians =
  `CARPATHIAN MOUNTAINS` + `Transylvanian Alps`).
- **Seas are split into sub-seas.** The Mediterranean is `Mediterranean Sea` plus `Tyrrhenian Sea`,
  `Adriatic Sea`, `Ionian Sea`, `Aegean Sea`, `Balearic Sea`, `Golfe du Lion`; the Baltic includes
  `Gulf of Bothnia` and `Gulf of Finland`. Search with `--near` and include every part.
- **Inland seas** can be in `marine` or `lakes`: the Caspian Sea is in `marine` in the current data.
- **Rivers are many segments, sometimes with different names** (e.g. `Danube` and `Donau`, `Yangtze`
  and `Chang Jiang`). Search by English name and by local name with `--near`, and list every name of
  the course you want in `source`. Check in the browser that the whole course is highlighted.
- **Peninsulas** are not always in `regions`. When a peninsula is a country (Italy) or two (Iberia:
  Spain + Portugal), use `countries` with `"largest": true` to drop islands and overseas territories.
- **Straits** are not drawn from `marine` (the polygons are too small at this scale): use `kind`
  `line` with two points across the strait, from coordinates the user confirms.
- **Coverage** is incomplete at this scale: small features may be missing. Report them as not found.
