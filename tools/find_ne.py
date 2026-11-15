#!/usr/bin/env python3
"""
Searches the Natural Earth layers used by generate_maps.py, to find the source of a feature.

Usage:
    python3 tools/find_ne.py alps                       # every layer
    python3 tools/find_ne.py "black sea" --layer marine
    python3 tools/find_ne.py gulf --layer marine --near 50,27 --limit 5
    python3 tools/find_ne.py iberia --word               # whole words only (not Siberia)

The search is case- and accent-insensitive and matches a substring of any name field
(name, alternative names, English and Spanish names); --word matches whole words only.
Each result is one name of one layer, i.e. the value to copy into the region config
({"layer": .., "name": ..}). Several Natural Earth features can share a name (river segments,
reef parts): the result merges them and shows how many there are, their classes, the centre of
the merged bounding box (lon, lat) and the box itself. Boxes that cross the antimeridian are given
with lon > 180. With --near, results are sorted by distance to that point. The query is also looked
up in the Catalan names of tools/regions/names.json (lines starting with "names.json:").
No dependencies (only the Python standard library). Reads NE_DIR like generate_maps.py.
"""
import argparse
import json
import math
import os
import re
import unicodedata

# ================================================================ constants
HERE = os.path.dirname(os.path.abspath(__file__))
NE_DIR = os.environ.get('NE_DIR', os.path.join(HERE, 'natural-earth-vector', 'geojson'))
NAMES_PATH = os.path.join(HERE, 'regions', 'names.json')
GEOJSON_EXT = '.geojson'
ENCODING = 'utf-8'

# Same keys as generate_maps.LAYERS: config name -> (file, property used as "name" in the config).
# Duplicated on purpose: this tool must not need numpy, which generate_maps.py imports.
LAYERS = {
    'regions': ('ne_10m_geography_regions_polys', 'NAME'),
    'marine': ('ne_50m_geography_marine_polys', 'name'),
    'lakes': ('ne_50m_lakes', 'name'),
    'countries': ('ne_50m_admin_0_countries', 'NAME'),
    'rivers': ('ne_10m_rivers_lake_centerlines', 'name'),
}
SEARCH_KEYS = ('NAME', 'name', 'NAMEALT', 'namealt', 'name_alt', 'NAME_ALT', 'NAME_EN', 'name_en', 'NAME_ES',
               'name_es', 'LABEL', 'label')
CLASS_KEYS = ('FEATURECLA', 'featurecla')
ENGLISH_NAME_KEYS = ('NAME_EN', 'name_en')

DEFAULT_LIMIT = 15
HALF_TURN_DEG = 180
FULL_TURN_DEG = 360
NEAR_SEPARATOR = ','
NAMES_PREFIX = 'names.json:'
LIST_SEPARATOR = '/'

NFD = 'NFD'
NONSPACING_MARK = 'Mn'
TYPOGRAPHIC_APOSTROPHE, APOSTROPHE = '’', "'"
WORD_BOUNDARY_BEFORE, WORD_BOUNDARY_AFTER = r'(?<![a-z0-9])', r'(?![a-z0-9])'

NO_RESULTS = 'No results. Try an English name, a shorter query or another layer.'


# ================================================================ helpers
def normalise(value):
    """Lowercase, without accents, with straight apostrophes."""
    decomposed = unicodedata.normalize(NFD, str(value or ''))
    plain = ''.join(char for char in decomposed if unicodedata.category(char) != NONSPACING_MARK)
    return plain.lower().replace(TYPOGRAPHIC_APOSTROPHE, APOSTROPHE)


def coordinates(geometry):
    """Every [lon, lat] of a geometry."""
    geometry_type, nested = geometry['type'], geometry['coordinates']
    if geometry_type == 'Point':
        return [nested]
    if geometry_type in ('LineString', 'MultiPoint'):
        return nested
    if geometry_type in ('Polygon', 'MultiLineString'):
        return [point for part in nested for point in part]
    if geometry_type == 'MultiPolygon':
        return [point for polygon in nested for ring in polygon for point in ring]
    return []


def first_value(properties, keys):
    """First non-empty property among keys (Natural Earth layers spell them differently)."""
    return next((properties[key] for key in keys if properties.get(key)), None)


def matcher(query, whole_words):
    normalised_query = normalise(query)
    if whole_words:
        pattern = re.compile(WORD_BOUNDARY_BEFORE + re.escape(normalised_query) + WORD_BOUNDARY_AFTER)
        return lambda value: bool(pattern.search(normalise(value)))
    return lambda value: normalised_query in normalise(value)


def print_known_names(matches):
    """Catalan names already resolved in tools/regions/names.json."""
    if not os.path.exists(NAMES_PATH):
        return
    with open(NAMES_PATH, encoding=ENCODING) as handle:
        known = json.load(handle)
    for catalan_name, entry in known.items():
        if matches(catalan_name):
            print(f'{NAMES_PREFIX} {catalan_name!r} -> {json.dumps(entry, ensure_ascii=False)}')


def collect(matches, only_layer):
    """(layer, name) -> merged info of every Natural Earth feature with that name."""
    merged = {}
    for layer, (file_name, name_key) in LAYERS.items():
        if only_layer and layer != only_layer:
            continue
        with open(os.path.join(NE_DIR, file_name + GEOJSON_EXT), encoding=ENCODING) as handle:
            ne_features = json.load(handle)['features']
        for ne_feature in ne_features:
            properties = ne_feature['properties']
            if not any(matches(properties.get(key)) for key in SEARCH_KEYS):
                continue
            points = coordinates(ne_feature['geometry'])
            if not points:
                continue
            info = merged.setdefault((layer, properties.get(name_key)),
                                     {'parts': 0, 'classes': set(), 'english': set(), 'lons': [], 'lats': []})
            info['parts'] += 1
            info['classes'].add(first_value(properties, CLASS_KEYS))
            english = first_value(properties, ENGLISH_NAME_KEYS)
            if english:
                info['english'].add(english)
            info['lons'] += [point[0] for point in points]
            info['lats'] += [point[1] for point in points]
    return merged


def bounding_box(info):
    """(west, south, east, north) and centre; across the antimeridian, longitudes go 0..360."""
    lons = info['lons']
    if max(lons) - min(lons) > HALF_TURN_DEG:
        lons = [lon + FULL_TURN_DEG if lon < 0 else lon for lon in lons]
    box = (min(lons), min(info['lats']), max(lons), max(info['lats']))
    centre = ((box[0] + box[2]) / 2, (box[1] + box[3]) / 2)
    return box, centre


def distance_deg(centre, near):
    """Approximate distance in degrees, wrapping longitudes."""
    lon, lat = near
    delta_lon = (centre[0] - lon + HALF_TURN_DEG) % FULL_TURN_DEG - HALF_TURN_DEG
    return math.hypot(delta_lon * math.cos(math.radians(lat)), centre[1] - lat)


# ================================================================ main
def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('query')
    parser.add_argument('--layer', choices=LAYERS)
    parser.add_argument('--near', help='lon,lat: sort by distance to this point')
    parser.add_argument('--word', action='store_true', help='match whole words only')
    parser.add_argument('--limit', type=int, default=DEFAULT_LIMIT)
    args = parser.parse_args()

    matches = matcher(args.query, args.word)
    print_known_names(matches)

    hits = []
    for (layer, name), info in collect(matches, args.layer).items():
        box, centre = bounding_box(info)
        hits.append((layer, name, info, centre, box))
    if args.near:
        near = tuple(map(float, args.near.split(NEAR_SEPARATOR)))
        hits.sort(key=lambda hit: distance_deg(hit[3], near))

    for index, (layer, name, info, centre, box) in enumerate(hits):
        if index >= args.limit:
            print(f'... {len(hits) - args.limit} more results; narrow with --layer, --near or --word '
                  f'(limit {args.limit})')
            break
        parts = f' ({info["parts"]} parts)' if info['parts'] > 1 else ''
        classes = LIST_SEPARATOR.join(sorted(map(str, info['classes'])))
        english = LIST_SEPARATOR.join(sorted(info['english']))
        print(f'{layer:9} {json.dumps(name, ensure_ascii=False):34} {classes:20} '
              f'en={english!r:28} centre=({centre[0]:.1f}, {centre[1]:.1f}) '
              f'bbox=({box[0]:.1f}, {box[1]:.1f}, {box[2]:.1f}, {box[3]:.1f}){parts}')
    if not hits:
        print(NO_RESULTS)


if __name__ == '__main__':
    main()
