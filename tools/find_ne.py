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
    ap.add_argument('--limit', type=int, default=15)
    a = ap.parse_args()

    q = norm(a.query)
    names_path = os.path.join(HERE, 'regions', 'names.json')
    if os.path.exists(names_path):
        with open(names_path, encoding='utf-8') as fh:
            known = json.load(fh)
        for ca, entry in known.items():
            if q in norm(ca):
                print(f'names.json: {ca!r} -> {json.dumps(entry, ensure_ascii=False)}')

    hits = []
    for layer, (file, key) in LAYERS.items():
        if a.layer and layer != a.layer:
            continue
        with open(os.path.join(NE, file + '.geojson'), encoding='utf-8') as fh:
            feats = json.load(fh)['features']
        for f in feats:
            p = f['properties']
            if not any(q in norm(p.get(k)) for k in SEARCH_KEYS):
                continue
            pts = coords(f['geometry'])
            if not pts:
                continue
            lons, lats = [x[0] for x in pts], [x[1] for x in pts]
            bbox = (min(lons), min(lats), max(lons), max(lats))
            centre = ((bbox[0] + bbox[2]) / 2, (bbox[1] + bbox[3]) / 2)
            cla = p.get('FEATURECLA') or p.get('featurecla')
            alt = p.get('NAME_EN') or p.get('name_en') or ''
            hits.append((layer, p.get(key), cla, alt, centre, bbox))

    if a.near:
        lon, lat = map(float, a.near.split(','))
        hits.sort(key=lambda h: math.hypot((h[4][0] - lon) * math.cos(math.radians(lat)), h[4][1] - lat))

    # Rivers are split in many segments with the same name: show each name once
    seen, shown = set(), 0
    for layer, name, cla, alt, centre, bbox in hits:
        if (layer, name) in seen:
            continue
        seen.add((layer, name))
        print(f'{layer:9} {json.dumps(name, ensure_ascii=False):34} {cla:16} en={alt!r:28} '
              f'centre=({centre[0]:.1f}, {centre[1]:.1f}) bbox=({bbox[0]:.1f}, {bbox[1]:.1f}, {bbox[2]:.1f}, {bbox[3]:.1f})')
        shown += 1
        if shown >= a.limit:
            print(f'... more results; narrow with --layer or --near (limit {a.limit})')
            break
    if not hits:
        print('No results. Try an English name, a shorter query or another layer.')


if __name__ == '__main__':
    main()
