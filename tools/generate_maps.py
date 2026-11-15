#!/usr/bin/env python3
"""
Generates the map data (data/<region>.js) from the region configs in tools/regions/ and Natural Earth.

Usage:
    python3 tools/generate_maps.py              # every region in tools/regions/
    python3 tools/generate_maps.py europa asia  # only these regions
    python3 tools/generate_maps.py --check      # validate configs, sources and layout, write nothing

Natural Earth is read from tools/natural-earth-vector/geojson (override with NE_DIR=...).
Only needs re-running to change features, base colours or the map framing.
The site doesn't need this script to work (the data files are already generated).
Requirements: Python 3 + numpy.

Region config (tools/regions/<id>.json):
    id, title          map id (route #/<id>, file data/<id>.js) and title shown in the page
    projection         {"type": "laea", "lon0": .., "lat0": ..}  Lambert azimuthal equal-area centre
    extent             [[lon, lat], ...]  points that must fit in the map; the bounding box sets the framing
    graticule          optional {"meridian_lats": [a, b], "parallels": [a, b], "parallel_lons": [a, b]}
    features           list, in tray order; each one:
        id, name, group    identifier (ascii), name shown in the page, group (see GROUPS)
        kind               area | river | line | peak
        source             area/river: [{"layer": .., "name": .., "largest": bool}, ...]  (see LAYERS)
        coords             line: [[lon, lat], ...]  (drawn by hand, "manual": true)
        dot                [lon, lat]  answer point (rivers snap it to the river)
        label              optional [lon, lat]  label position (default: just above the dot)
        manual             true when the geometry is not taken from Natural Earth
"""
import glob
import json
import os
import re
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, '..', 'data')
REGIONS = os.path.join(HERE, 'regions')
NE = os.environ.get('NE_DIR', os.path.join(HERE, 'natural-earth-vector', 'geojson'))

# Natural Earth layers a feature can come from: config name -> (file, property holding the name)
LAYERS = {
    'regions': ('ne_10m_geography_regions_polys', 'NAME'),
    'marine': ('ne_50m_geography_marine_polys', 'name'),
    'lakes': ('ne_50m_lakes', 'name'),
    'countries': ('ne_50m_admin_0_countries', 'NAME'),
    'rivers': ('ne_10m_rivers_lake_centerlines', 'name'),
}
# Groups known by the page (js/app.js GROUP_COLORS, css/styles.css) and the kinds each one accepts
GROUPS = {
    'Rius': {'river'}, 'Serralades': {'area', 'peak'}, 'Mars': {'area'}, 'Penínsules': {'area'},
    'Illes': {'area'}, 'Planes': {'area'}, 'Llacs': {'area'}, 'Deserts': {'area'}, 'Estrets': {'line'},
    'Golfs': {'area'}, 'Arxipèlegs': {'area'},
}

_cache = {}


def load(n):
    if n not in _cache:
        with open(os.path.join(NE, n + '.geojson'), encoding='utf-8') as fh:
            _cache[n] = json.load(fh)['features']
    return _cache[n]


W = 1600  # viewBox width


# ---------------------------------------------------------------- projection
class LAEA:
    """Lambert azimuthal equal-area projection (km)."""

    def __init__(self, lon0, lat0):
        self.l0, self.p0 = np.radians(lon0), np.radians(lat0)

    def __call__(self, lon, lat):
        lon, lat = np.radians(np.asarray(lon, float)), np.radians(np.asarray(lat, float))
        dl = lon - self.l0
        k = np.sqrt(2 / (1 + np.sin(self.p0) * np.sin(lat) + np.cos(self.p0) * np.cos(lat) * np.cos(dl)))
        return (k * np.cos(lat) * np.sin(dl) * 6371,
                k * (np.cos(self.p0) * np.sin(lat) - np.sin(self.p0) * np.cos(lat) * np.cos(dl)) * 6371)


class Frame:
    """Projection + conversion to viewBox coordinates."""

    def __init__(self, lon0, lat0, extent):
        self.P = LAEA(lon0, lat0)
        xs, ys = self.P([e[0] for e in extent], [e[1] for e in extent])
        self.x0, self.x1, self.y0, self.y1 = xs.min(), xs.max(), ys.min(), ys.max()
        self.k = W / (self.x1 - self.x0)
        self.H = round((self.y1 - self.y0) * self.k)

    def xy(self, lon, lat):
        x, y = self.P(lon, lat)
        return (x - self.x0) * self.k, (self.y1 - y) * self.k

    def pt(self, ll):
        x, y = self.xy(ll[0], ll[1])
        return [round(float(x), 1), round(float(y), 1)]


# ---------------------------------------------------------------- geometry
def polys(g):
    if g['type'] == 'Polygon':
        return [g['coordinates']]
    return g['coordinates'] if g['type'] == 'MultiPolygon' else []


def lines(g):
    if g['type'] == 'LineString':
        return [g['coordinates']]
    return g['coordinates'] if g['type'] == 'MultiLineString' else []


def simplify(a, tol):
    """Iterative Ramer–Douglas–Peucker."""
    if len(a) < 3:
        return a
    keep = np.zeros(len(a), bool)
    keep[0] = keep[-1] = True
    stack = [(0, len(a) - 1)]
    while stack:
        i, j = stack.pop()
        if j <= i + 1:
            continue
        p, q = a[i], a[j]
        seg = a[i + 1:j]
        d = q - p
        n = np.hypot(*d)
        if n == 0:
            dist = np.hypot(*(seg - p).T)
        else:
            dist = np.abs(d[0] * (seg[:, 1] - p[1]) - d[1] * (seg[:, 0] - p[0])) / n
        m = int(np.argmax(dist))
        if dist[m] > tol:
            k = i + 1 + m
            keep[k] = True
            stack += [(i, k), (k, j)]
    return a[keep]


def fmt(a):
    return 'M' + 'L'.join(f'{x:.1f},{y:.1f}' for x, y in a)


def in_view(frame, a, pad=60):
    return not (a[:, 0].max() < -pad or a[:, 0].min() > W + pad
                or a[:, 1].max() < -pad or a[:, 1].min() > frame.H + pad)


def poly_d(frame, plist, tol=0.6, min_area=0):
    out = []
    for poly in plist:
        for ri, ring in enumerate(poly):
            r = np.array(ring)[:, :2]
            x, y = frame.xy(r[:, 0], r[:, 1])
            a = np.column_stack([x, y])
            if not in_view(frame, a):
                continue
            if ri == 0 and min_area:
                area = abs(np.sum(a[:-1, 0] * a[1:, 1] - a[1:, 0] * a[:-1, 1])) / 2
                if area < min_area:
                    break
            a = simplify(a, tol)
            if len(a) >= 3:
                out.append(fmt(a) + 'Z')
    return ''.join(out)


def line_d(frame, lst, tol=0.5):
    out = []
    for ln in lst:
        r = np.array(ln)[:, :2]
        x, y = frame.xy(r[:, 0], r[:, 1])
        a = np.column_stack([x, y])
        if not in_view(frame, a):
            continue
        a = simplify(a, tol)
        if len(a) >= 2:
            out.append(fmt(a))
    return ''.join(out)


def ring_area(r):
    a = np.array(r)
    return abs(np.sum(a[:-1, 0] * a[1:, 1] - a[1:, 0] * a[:-1, 1])) / 2


def source_polys(refs):
    """Polygons of an area feature, in the order of its source refs."""
    out = []
    for ref in refs:
        file, key = LAYERS[ref['layer']]
        found = [p for f in load(file) if f['properties'].get(key) == ref['name'] for p in polys(f['geometry'])]
        if not found:
            raise SystemExit(f"Not found in Natural Earth: {ref['layer']} {ref['name']!r}")
        out += [max(found, key=lambda p: ring_area(p[0]))] if ref.get('largest') else found
    return out


def river_lines(refs):
    file, key = LAYERS['rivers']
    names = {r['name'] for r in refs}
    found = [ln for f in load(file) if f['properties'].get(key) in names for ln in lines(f['geometry'])]
    if not found:
        raise SystemExit(f'River not found in Natural Earth: {sorted(names)}')
    return found


def snap_to_lines(frame, lls, ll):
    """Point on the line (river) closest to the reference point."""
    best, bd = None, 1e18
    tx, ty = frame.xy(*ll)
    for ln in lls:
        r = np.array(ln)[:, :2]
        x, y = frame.xy(r[:, 0], r[:, 1])
        d = (x - tx) ** 2 + (y - ty) ** 2
        i = int(np.argmin(d))
        if d[i] < bd:
            bd, best = d[i], [round(float(x[i]), 1), round(float(y[i]), 1)]
    return best


# ---------------------------------------------------------------- base layer (blank map)
def base_layers(frame, grat_cfg=None):
    g = {'meridian_lats': [-30, 85], 'parallels': [-20, 80], 'parallel_lons': [-60, 250], **(grat_cfg or {})}
    LAND, LAKES, REG = load('ne_50m_land'), load('ne_50m_lakes'), load(LAYERS['regions'][0])
    RIVERS = load(LAYERS['rivers'][0])
    land = ''.join(poly_d(frame, polys(f['geometry']), 0.6, 2) for f in LAND)
    plat = ''.join(poly_d(frame, polys(f['geometry']), 1.0, 20)
                   for f in REG if f['properties']['FEATURECLA'] == 'Plateau')
    mtn = ''.join(poly_d(frame, polys(f['geometry']), 1.0, 20)
                  for f in REG if f['properties']['FEATURECLA'] == 'Range/mtn')
    lakes = ''.join(poly_d(frame, polys(f['geometry']), 0.6, 4) for f in LAKES)
    minor = ''.join(line_d(frame, lines(f['geometry']), 0.8)
                    for f in RIVERS if f['properties'].get('scalerank', 9) <= 4)
    grat = []
    for lon in range(-180, 181, 10):
        la = np.linspace(*g['meridian_lats'], 120)
        x, y = frame.xy(np.full_like(la, lon), la)
        a = np.column_stack([x, y])
        grat.append(fmt(simplify(a, 0.5)))
    for lat in range(g['parallels'][0], g['parallels'][1] + 1, 10):
        lo = np.linspace(*g['parallel_lons'], 400)
        x, y = frame.xy(lo, np.full_like(lo, lat))
        a = np.column_stack([x, y])
        a = a[(a[:, 0] > -300) & (a[:, 0] < W + 300)]
        if len(a) > 1:
            grat.append(fmt(simplify(a, 0.5)))
    return {'graticule': ''.join(grat), 'land': land, 'plateaus': plat, 'mountains': mtn, 'lakes': lakes,
            'rivers': minor}


# ---------------------------------------------------------------- features
def build(frame, features):
    feats = []
    for c in features:
        f = {'id': c['id'], 'name': c['name'], 'group': c['group'], 'kind': c['kind']}
        kind = c['kind']
        if kind == 'area':
            f['d'] = poly_d(frame, source_polys(c['source']), 0.5)
            f['dot'] = frame.pt(c['dot'])
        elif kind == 'river':
            lls = river_lines(c['source'])
            f['d'] = line_d(frame, lls, 0.4)
            f['dot'] = snap_to_lines(frame, lls, c['dot'])
        elif kind == 'line':  # strait
            a = np.array([frame.xy(*p) for p in c['coords']])
            f['d'] = fmt(a)
            f['dot'] = frame.pt(c['dot'])
        elif kind == 'peak':
            f['dot'] = frame.pt(c['dot'])
        lab = c.get('label')
        f['label'] = frame.pt(lab) if lab else [f['dot'][0], round(f['dot'][1] - 22, 1)]
        feats.append(f)
    return feats


# ---------------------------------------------------------------- region configs
def validate(cfg):
    """Returns a list of problems in a region config (empty if it is valid)."""
    errs = []
    for k in ('id', 'title', 'projection', 'extent', 'features'):
        if k not in cfg:
            errs.append(f'missing key {k!r}')
    if errs:
        return errs
    if cfg['projection'].get('type') != 'laea':
        errs.append('projection.type must be "laea"')
    ids, names = set(), set()
    for i, c in enumerate(cfg['features']):
        where = f"feature {i} ({c.get('id', '?')})"
        for k in ('id', 'name', 'group', 'kind', 'dot'):
            if k not in c:
                errs.append(f'{where}: missing {k!r}')
        if c.get('id') in ids:
            errs.append(f'{where}: duplicate id')
        if c.get('name') in names:
            errs.append(f'{where}: duplicate name')
        ids.add(c.get('id'))
        names.add(c.get('name'))
        if not re.fullmatch(r'[a-z0-9_]+', str(c.get('id', ''))):
            errs.append(f'{where}: id must be lowercase ascii letters, digits or _')
        group, kind = c.get('group'), c.get('kind')
        if group not in GROUPS:
            errs.append(f'{where}: unknown group {group!r} (known: {", ".join(GROUPS)})')
        elif kind not in GROUPS[group]:
            errs.append(f'{where}: kind {kind!r} not allowed for {group} (allowed: {sorted(GROUPS[group])})')
        if kind in ('area', 'river'):
            refs = c.get('source') or []
            if not refs:
                errs.append(f'{where}: {kind} needs a non-empty source')
            for r in refs:
                if r.get('layer') not in LAYERS:
                    errs.append(f"{where}: unknown layer {r.get('layer')!r} (known: {', '.join(LAYERS)})")
                elif (kind == 'river') != (r['layer'] == 'rivers'):
                    errs.append(f"{where}: {kind} cannot use layer {r['layer']!r}")
        if kind == 'line' and len(c.get('coords') or []) < 2:
            errs.append(f'{where}: line needs at least two coords')
        if kind in ('line', 'peak') and not c.get('manual'):
            errs.append(f'{where}: {kind} geometry is drawn by hand; mark it "manual": true')
    return errs


def split_label(name):
    """Same rule as splitLabel() in js/app.js: names over 17 characters go on two lines."""
    if len(name) <= 17:
        return [name]
    mid = len(name) / 2
    spaces = [i for i, ch in enumerate(name) if ch == ' ']
    if not spaces:
        return [name]
    best = min(spaces, key=lambda i: abs(i - mid))
    return [name[:best], name[best + 1:]]


def label_box(f):
    """Approximate label box in viewBox units (24 px bold text, about 12 px per character; approximate, confirm in the browser)."""
    lines = split_label(f['name'])
    w = max(len(ln) for ln in lines) * 12 + 6
    h = len(lines) * 27 + 6
    x, y = f['label']
    return x - w / 2, y - h / 2, x + w / 2, y + h / 2


def layout_warnings(data):
    """Labels that overlap, and dots or labels outside the map."""
    out = []
    W_, H_ = data['viewBox'][2], data['viewBox'][3]
    feats = data['features']
    boxes = [label_box(f) for f in feats]
    for f, b in zip(feats, boxes):
        x, y = f['dot']
        if not (0 <= x <= W_ and 0 <= y <= H_):
            out.append(f"{f['id']}: dot outside the map ({x}, {y})")
        if b[0] < 0 or b[1] < 0 or b[2] > W_ or b[3] > H_:
            out.append(f"{f['id']}: label partly outside the map")
        if not f.get('d') and f['kind'] != 'peak':
            out.append(f"{f['id']}: empty geometry (is the feature inside the extent?)")
    for i in range(len(feats)):
        for j in range(i + 1, len(feats)):
            a, b = boxes[i], boxes[j]
            if a[0] < b[2] and b[0] < a[2] and a[1] < b[3] and b[1] < a[3]:
                out.append(f"{feats[i]['id']} / {feats[j]['id']}: labels overlap")
    return out


def region_paths(ids):
    if ids:
        return [os.path.join(REGIONS, i + '.json') for i in ids]
    return sorted(p for p in glob.glob(os.path.join(REGIONS, '*.json')) if os.path.basename(p) != 'names.json')


def frame_of(cfg):
    pr = cfg['projection']
    return Frame(pr['lon0'], pr['lat0'], cfg['extent'])


def report(path, data):
    warns = layout_warnings(data)
    status = 'OK' if not warns else f'{len(warns)} warning(s)'
    print(f"{os.path.relpath(path)}: {status} ({len(data['features'])} accidents)", *warns, sep='\n  - ')


def build_region(cfg):
    frame = frame_of(cfg)
    key = cfg['id']
    data = {'id': key, 'title': cfg['title'], 'viewBox': [0, 0, W, frame.H],
            'base': base_layers(frame, cfg.get('graticule')), 'features': build(frame, cfg['features'])}
    return data


def save(data):
    key = data['id']
    os.makedirs(OUT, exist_ok=True)
    # Saved as a script (not JSON) so the page also works when opening index.html without a server.
    p = os.path.join(OUT, key + '.js')
    with open(p, 'w', encoding='utf-8') as fh:
        fh.write('// Generated by tools/generate_maps.py — do not edit by hand.\n')
        fh.write('window.MAP_DATA = window.MAP_DATA || {};\n')
        fh.write(f'window.MAP_DATA[{json.dumps(key)}] = ')
        json.dump(data, fh, ensure_ascii=False, separators=(',', ':'))
        fh.write(';\n')
    print(f'  wrote {os.path.relpath(p)} ({round(os.path.getsize(p) / 1024)} KB)')


def main(argv):
    check = '--check' in argv
    ids = [a for a in argv if not a.startswith('--')]
    failed = False
    for path in region_paths(ids):
        with open(path, encoding='utf-8') as fh:
            cfg = json.load(fh)
        errs = validate(cfg)
        if cfg.get('id') != os.path.splitext(os.path.basename(path))[0]:
            errs.append('id must match the file name')
        if errs:
            failed = True
            print(f'{os.path.relpath(path)}:', *errs, sep='\n  - ')
            continue
        data = build_region(cfg)  # fails if a source is not in Natural Earth
        report(path, data)
        if not check:
            save(data)
    return 1 if failed else 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
