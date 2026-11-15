#!/usr/bin/env python3
"""
Searches the Natural Earth layers used by generate_maps.py, to find the source of a feature.

Usage:
    python3 tools/find_ne.py alps                       # every layer
    python3 tools/find_ne.py "black sea" --layer marine
    python3 tools/find_ne.py gulf --layer marine --near 50,27 --limit 5

The search is case- and accent-insensitive and matches a substring of any name field
(name, alternative names, English and Spanish names). Each result shows the value to copy
into the region config ({"layer": .., "name": ..}), its Natural Earth class, the centre of its
bounding box (lon, lat) and the bounding box itself. With --near, results are sorted by distance
to that point. With --name-catalan, it also looks the query up in tools/regions/names.json.
No dependencies (only the Python standard library).
"""
import argparse
import json
import math
import os
import re
import unicodedata

HERE = os.path.dirname(os.path.abspath(__file__))
NE = os.environ.get('NE_DIR', os.path.join(HERE, 'natural-earth-vector', 'geojson'))

# Same keys as generate_maps.LAYERS: config name -> (file, property used as "name" in the config)
LAYERS = {
    'regions': ('ne_10m_geography_regions_polys', 'NAME'),
    'marine': ('ne_50m_geography_marine_polys', 'name'),
    'lakes': ('ne_50m_lakes', 'name'),
    'countries': ('ne_50m_admin_0_countries', 'NAME'),
    'rivers': ('ne_10m_rivers_lake_centerlines', 'name'),
}
SEARCH_KEYS = ('NAME', 'name', 'NAMEALT', 'namealt', 'name_alt', 'NAME_ALT', 'NAME_EN', 'name_en', 'NAME_ES',
               'name_es', 'LABEL', 'label')


def norm(s):
    s = unicodedata.normalize('NFD', str(s or ''))
    return ''.join(c for c in s if unicodedata.category(c) != 'Mn').lower().replace('’', "'")


def coords(g):
    """Every [lon, lat] of a geometry."""
    t, c = g['type'], g['coordinates']
    if t == 'Point':
        return [c]
    if t in ('LineString', 'MultiPoint'):
        return c
    if t in ('Polygon', 'MultiLineString'):
        return [p for part in c for p in part]
    if t == 'MultiPolygon':
        return [p for poly in c for ring in poly for p in ring]
    return []


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('query')
    ap.add_argument('--layer', choices=LAYERS)
    ap.add_argument('--near', help='lon,lat: sort by distance to this point')
    ap.add_argument('--word', action='store_true', help='match whole words only')
    ap.add_argument('--limit', type=int, default=15)
    a = ap.parse_args()

    q = norm(a.query)
    if a.word:
        pat = re.compile(r'(?<![a-z0-9])' + re.escape(q) + r'(?![a-z0-9])')
        match = lambda v: bool(pat.search(norm(v)))  # noqa: E731
    else:
        match = lambda v: q in norm(v)  # noqa: E731

    names_path = os.path.join(HERE, 'regions', 'names.json')
    if os.path.exists(names_path):
        with open(names_path, encoding='utf-8') as fh:
            known = json.load(fh)
        for ca, entry in known.items():
            if match(ca):
                print(f'names.json: {ca!r} -> {json.dumps(entry, ensure_ascii=False)}')

    # (layer, name) -> merged info of every feature with that name
    groups = {}
    for layer, (file, key) in LAYERS.items():
        if a.layer and layer != a.layer:
            continue
        with open(os.path.join(NE, file + '.geojson'), encoding='utf-8') as fh:
            feats = json.load(fh)['features']
        for f in feats:
            p = f['properties']
            if not any(match(p.get(k)) for k in SEARCH_KEYS):
                continue
            pts = coords(f['geometry'])
            if not pts:
                continue
            g = groups.setdefault((layer, p.get(key)), {'n': 0, 'classes': set(), 'en': set(), 'lons': [], 'lats': []})
            g['n'] += 1
            g['classes'].add(p.get('FEATURECLA') or p.get('featurecla'))
            en = p.get('NAME_EN') or p.get('name_en')
            if en:
                g['en'].add(en)
            g['lons'] += [x[0] for x in pts]
            g['lats'] += [x[1] for x in pts]

    hits = []
    for (layer, name), g in groups.items():
        lons = g['lons']
        if max(lons) - min(lons) > 180:  # crosses the antimeridian: use 0..360
            lons = [x + 360 if x < 0 else x for x in lons]
        bbox = (min(lons), min(g['lats']), max(lons), max(g['lats']))
        centre = ((bbox[0] + bbox[2]) / 2, (bbox[1] + bbox[3]) / 2)
        hits.append((layer, name, g, centre, bbox))

    if a.near:
        lon, lat = map(float, a.near.split(','))

        def dist(h):
            dl = (h[3][0] - lon + 180) % 360 - 180
            return math.hypot(dl * math.cos(math.radians(lat)), h[3][1] - lat)
        hits.sort(key=dist)

    for i, (layer, name, g, centre, bbox) in enumerate(hits):
        if i >= a.limit:
            print(f'... {len(hits) - a.limit} more results; narrow with --layer, --near or --word (limit {a.limit})')
            break
        parts = f' ({g["n"]} parts)' if g['n'] > 1 else ''
        print(f'{layer:9} {json.dumps(name, ensure_ascii=False):34} {"/".join(sorted(map(str, g["classes"]))):20} '
              f'en={"/".join(sorted(g["en"]))!r:28} centre=({centre[0]:.1f}, {centre[1]:.1f}) '
              f'bbox=({bbox[0]:.1f}, {bbox[1]:.1f}, {bbox[2]:.1f}, {bbox[3]:.1f}){parts}')
    if not hits:
        print('No results. Try an English name, a shorter query or another layer.')


if __name__ == '__main__':
    main()
