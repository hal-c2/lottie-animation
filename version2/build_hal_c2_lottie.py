"""Build the HAL-C2 avatar Grease Pencil animations and export them to Lottie.

blender -b --factory-startup --python build_hal_c2_lottie.py -- <dance|genie> <out_dir>

`mise run build version2 <dance|genie>` runs this with the environment below
checked first:
  LOTTIE_GP_SCRIPTS        folder holding the bx_gp helper module
  LOTTIE_EXPORT_ADDON_DIR  folder holding the io_lottie_export add-on, unless
                           Blender already imports it
  HAL_C2_AVATAR_SVG        hal-c2-avatar.svg from hal-c2/hal-c2 assets/brand
  LOTTIE_WORK_DIR          review renders (default: <temp dir>/hal-c2-lottie)

The avatar is imported from SVG as Bezier fill strokes, split into layers by
graphic role, and every animated frame is a sculpted copy of the rest pose
(same strokes, same points), so the Lottie paths keep one topology.
"""

import math
import os
import sys
import tempfile

import bpy
import numpy as np

for var in ("LOTTIE_GP_SCRIPTS", "LOTTIE_EXPORT_ADDON_DIR"):
    if os.environ.get(var):
        sys.path.append(os.path.expanduser(os.environ[var]))
import bx_gp as G  # noqa: E402
import io_lottie_export  # noqa: E402

MODE, OUT = sys.argv[sys.argv.index("--") + 1:][:2]
if MODE not in ("dance", "genie"):
    sys.exit(f"unknown animation {MODE!r}: expected dance or genie")
SVG = os.path.expanduser(os.environ.get("HAL_C2_AVATAR_SVG", ""))
if not os.path.isfile(SVG):
    sys.exit("HAL_C2_AVATAR_SVG must name hal-c2-avatar.svg (hal-c2/hal-c2, assets/brand)")
WORK = os.path.join(os.environ.get("LOTTIE_WORK_DIR") or os.path.join(tempfile.gettempdir(), "hal-c2-lottie"), "version2")
os.makedirs(OUT, exist_ok=True)

PALETTE = {
    "Ink": "#010104",
    "Paper": "#f6f1f1",
    "Tangerine": "#fba919",
    "Grape": "#ac75fa",
    "Periwinkle": "#768efb",
    "Pink": "#f76eb8",
    "Navy": "#4e5f89",
    "Lilac": "#dccbfd",
    "Mist": "#cdd6fd",
}
# imported stroke index -> (layer, material), bottom -> top inside each layer
PARTS = {
    "Bubble": [(0, "Ink"), (1, "Paper"), (2, "Paper")],
    "Accents": [(8, "Tangerine"), (12, "Tangerine"), (5, "Grape"), (6, "Periwinkle"), (3, "Pink")],
    "Screen": [(13, "Navy"), (7, "Tangerine"), (4, "Pink"), (14, "Navy")],
    "Face": [(9, "Tangerine"), (10, "Tangerine"), (11, "Tangerine")],
}

bpy.ops.wm.read_factory_settings(use_empty=True)
io_lottie_export.register()
sc = bpy.context.scene
G.scene_2d(res=(512, 512), fps=24, frame_range=(1, 24 if MODE == "dance" else 48),
           ortho_scale=3.6, background="#ffffff")


# ---------------------------------------------------------------- read the SVG

def _get(d, name, domain_len, width, key):
    a = d.attributes[name]
    buf = np.zeros(domain_len * width, dtype=np.float32 if key != "value" or a.data_type.startswith("FLOAT") else np.int32)
    a.data.foreach_get(key, buf)
    return buf.reshape(domain_len, width) if width > 1 else buf


bpy.ops.wm.grease_pencil_import_svg(filepath=SVG, directory=os.path.dirname(SVG),
                                    files=[{"name": os.path.basename(SVG)}])
src = next(o for o in bpy.data.objects if o.type == "GREASEPENCIL")
sd = src.data.layers[0].frames[0].drawing
npts = sum(len(s.points) for s in sd.strokes)
nstr = len(sd.strokes)
offs = [0]
for s in sd.strokes:
    offs.append(offs[-1] + len(s.points))
P = _get(sd, "position", npts, 3, "vector")
HL = _get(sd, "handle_left", npts, 3, "vector")
HR = _get(sd, "handle_right", npts, 3, "vector")
FID = _get(sd, "fill_id", nstr, 1, "value")
SRC = [dict(pos=P[offs[i]:offs[i + 1]].copy(), hl=HL[offs[i]:offs[i + 1]].copy(),
            hr=HR[offs[i]:offs[i + 1]].copy(), fill_id=int(FID[i])) for i in range(nstr)]
bpy.data.objects.remove(src)
for m in list(bpy.data.materials):
    bpy.data.materials.remove(m)

# rest-pose landmarks (metres, XZ plane)
outer = SRC[2]["pos"]
TAIL = outer[np.argmin(outer[:, 2])][[0, 2]]           # tip of the speech-bubble tail
TOP = float(P[:, 2].max())
BASE_Z = -0.78                                         # bottom of the bubble body; the tail hangs below
CX = 0.0
print("tail tip", TAIL, "top", TOP)


# ---------------------------------------------------------------- write drawings

def stroke(pos, hl, hr, mat, fill_id, fill_opacity=1.0):
    return dict(pos=pos, hl=hl, hr=hr, mat=mat, fill_id=fill_id, fo=fill_opacity)


def write(d, strokes):
    """Fill-only Bezier strokes. Point opacity 0 keeps the exporter's (ignored)
    hide_stroke outline invisible in the Lottie."""
    d.add_strokes([len(s["pos"]) for s in strokes])
    d.set_types(type="BEZIER")
    A = d.attributes

    def attr(name, dtype, domain):
        return A.get(name) or A.new(name, dtype, domain)

    cat = lambda k: np.concatenate([np.asarray(s[k], dtype=np.float32) for s in strokes]).ravel()
    A["position"].data.foreach_set("vector", cat("pos"))
    attr("handle_left", "FLOAT_VECTOR", "POINT").data.foreach_set("vector", cat("hl"))
    attr("handle_right", "FLOAT_VECTOR", "POINT").data.foreach_set("vector", cat("hr"))
    n = len(A["position"].data)
    attr("handle_type_left", "INT8", "POINT").data.foreach_set("value", np.zeros(n, np.int32))
    attr("handle_type_right", "INT8", "POINT").data.foreach_set("value", np.zeros(n, np.int32))
    attr("radius", "FLOAT", "POINT").data.foreach_set("value", np.full(n, 0.002, np.float32))
    attr("opacity", "FLOAT", "POINT").data.foreach_set("value", np.zeros(n, np.float32))
    m = len(strokes)
    attr("material_index", "INT", "CURVE").data.foreach_set("value", np.array([s["mat"] for s in strokes], np.int32))
    attr("fill_id", "INT", "CURVE").data.foreach_set("value", np.array([s["fill_id"] for s in strokes], np.int32))
    attr("cyclic", "BOOLEAN", "CURVE").data.foreach_set("value", np.ones(m, bool))
    attr("hide_stroke", "BOOLEAN", "CURVE").data.foreach_set("value", np.ones(m, bool))
    attr("fill_opacity", "FLOAT", "CURVE").data.foreach_set("value", np.array([s["fo"] for s in strokes], np.float32))
    d.tag_positions_changed()


hal = G.new_object("HAL", layers=("Smoke", "Bubble", "Accents", "Screen", "Face", "Sparkles"))
MAT = {name: G.material(hal, name, stroke=hexc, fill=hexc) for name, hexc in PALETTE.items()}

REST = {  # layer -> list of rest strokes (dicts with pos/hl/hr/mat/fill_id)
    lay: [stroke(SRC[i]["pos"], SRC[i]["hl"], SRC[i]["hr"], MAT[mat], SRC[i]["fill_id"]) for i, mat in parts]
    for lay, parts in PARTS.items()
}


def deformed(strokes, fn):
    """Apply fn(xz: (N,2)) -> (N,2) to points and handles alike (FREE handles)."""
    out = []
    for s in strokes:
        t = dict(s)
        for k in ("pos", "hl", "hr"):
            a = np.array(s[k], dtype=np.float64)
            xz = fn(a[:, [0, 2]])
            a[:, 0], a[:, 2] = xz[:, 0], xz[:, 1]
            t[k] = a
        out.append(t)
    return out


def key(layer, frame, strokes):
    write(hal.data.layers[layer].frames.new(frame).drawing, strokes)


# ---------------------------------------------------------------- motion helpers

def smoothstep(a, b, x):
    t = np.clip((x - a) / (b - a), 0.0, 1.0)
    return t * t * (3 - 2 * t)


def ease_out_back(p, c1=1.70158):
    p = np.clip(p, 0.0, 1.0)
    c3 = c1 + 1
    return 1 + c3 * (p - 1) ** 3 + c1 * (p - 1) ** 2


def rotate(xz, pivot, ang):
    c, s = np.cos(ang), np.sin(ang)
    d = xz - pivot
    return np.stack([pivot[0] + d[:, 0] * c - d[:, 1] * s, pivot[1] + d[:, 0] * s + d[:, 1] * c], axis=1)


def scale_about(xz, pivot, sx, sz):
    return np.stack([pivot[0] + (xz[:, 0] - pivot[0]) * sx, pivot[1] + (xz[:, 1] - pivot[1]) * sz], axis=1)


def centroid(strokes):
    pts = np.concatenate([s["pos"] for s in strokes])
    return np.array([(pts[:, 0].min() + pts[:, 0].max()) / 2, (pts[:, 2].min() + pts[:, 2].max()) / 2])


# ---------------------------------------------------------------- dance

def lean(t):
    """Side-to-side lean in [-1, 1]: snappy through the middle, settling at the sides."""
    s = math.sin(2 * math.pi * t)
    return math.copysign(abs(s) ** 0.55, s)


def bend(xz, theta, squash):
    """Planted base, top leans: a shear that grows with height keeps the base flat
    and bows the sides, and a turn about the base tilts the top. At the extremes
    the body squats a little."""
    pivot = np.array([CX, BASE_Z])
    xz = scale_about(xz, pivot, 1 + 0.03 * squash, 1 - 0.05 * squash)
    h = np.clip((xz[:, 1] - BASE_Z) / (TOP - BASE_Z), 0, 1)
    xz = np.stack([xz[:, 0] + math.tan(theta) * (xz[:, 1] - BASE_Z) * h, xz[:, 1]], axis=1)
    c, s = np.cos(-0.9 * theta * h * h), np.sin(-0.9 * theta * h * h)
    d = xz - pivot
    return np.stack([pivot[0] + d[:, 0] * c - d[:, 1] * s, pivot[1] + d[:, 0] * s + d[:, 1] * c], axis=1)


def build_dance():
    loop = 24                                          # one left-right cycle per second
    amp = math.radians(12)
    # frame 25 repeats frame 1: the exporter writes op = frame_end, which
    # lottie-web treats as exclusive, so 1..24 play and loop seamlessly
    sc.frame_end = loop + 1
    for f in range(1, loop + 2):
        t = (f - 1) / loop
        body = lean(t)
        face = lean(t - 1.0 / loop)                    # the face drags a frame behind the body
        for lay, strokes in REST.items():
            l = face if lay in ("Face", "Screen") else body
            key(lay, f, deformed(strokes, lambda xz, l=l: bend(xz, amp * l, abs(l))))
    for lay in ("Smoke", "Sparkles"):
        hal.data.layers.remove(hal.data.layers[lay])


# ---------------------------------------------------------------- genie

def genie(xz, p):
    """Rise out of the bubble's tail tip like smoke from a lamp: a narrow twisting
    wisp that stretches up, widens with overshoot and settles on the rest pose."""
    tx, tz = TAIL
    u = np.clip((xz[:, 1] - tz) / (TOP - tz), 0, 1)
    rise = ease_out_back(p / 0.85)                     # height leads ...
    width = ease_out_back((p - 0.12) / 0.88, 2.2)      # ... width follows: stretch, then squash
    k = smoothstep(0.25, 0.95, p)                      # how far the funnel has opened
    funnel = (0.12 + 0.88 * u ** 1.6) * (1 - k) + k
    axis = (tx * (1 - u) + CX * u) * (1 - k) + CX * k
    sway = 0.28 * (1 - smoothstep(0.0, 0.9, p)) * np.sin(2 * math.pi * (0.8 * u - 1.4 * p)) * u ** 1.5
    x = axis + (xz[:, 0] - CX) * funnel * width + sway
    z = tz + (xz[:, 1] - tz) * rise
    return np.stack([x, z], axis=1)


def astroid(center, r, ang, n=36):
    t = np.linspace(0, 2 * math.pi, n, endpoint=False)
    x, z = r * np.cos(t) ** 3, r * np.sin(t) ** 3
    c, s = math.cos(ang), math.sin(ang)
    pts = np.stack([center[0] + x * c - z * s, np.zeros(n), center[1] + x * s + z * c], axis=1)
    return pts


def disc(center, r, n=24):
    t = np.linspace(0, 2 * math.pi, n, endpoint=False)
    return np.stack([center[0] + r * np.cos(t), np.zeros(n), center[1] + r * np.sin(t)], axis=1)


def poly(pts, mat, fid, fo=1.0):
    return stroke(pts, pts.copy(), pts.copy(), mat, fid, fo)


SPARKS = [  # centre, radius, colour, birth frame
    ((-1.30, 0.95), 0.20, "Tangerine", 17),
    ((1.35, 1.05), 0.16, "Pink", 20),
    ((1.45, -0.35), 0.22, "Periwinkle", 23),
    ((-1.42, -0.30), 0.15, "Grape", 26),
    ((0.25, 1.38), 0.13, "Tangerine", 29),
]
SPARK_LIFE = 12
PUFFS = [  # drift direction, colour, delay
    ((-0.55, 0.35), "Lilac", 0),
    ((0.45, 0.45), "Mist", 1),
    ((-0.15, 0.70), "Lilac", 3),
    ((0.65, 0.10), "Mist", 4),
]


def build_genie():
    body_frames = 30                                   # emerge over 1.25 s, then hold
    face_c = centroid(REST["Face"])
    screen_c = centroid(REST["Bubble"][:1])

    def screen_grow(f):
        """The screen (and the bubble's hole around it) opens once the white wisp
        has formed, so the genie starts as solid smoke rather than a black squiggle."""
        q = max(float(ease_out_back(((f - 1) / body_frames - 0.3) / 0.55, 1.4)), 0.006)  # a point-sized hole breaks fill triangulation
        return lambda xz: scale_about(xz, screen_c, q, q)

    for f in range(1, body_frames + 2):
        p = (f - 1) / body_frames
        g = lambda xz, p=p: genie(xz, p)
        screen, hole, ring = REST["Bubble"]
        key("Bubble", f, deformed(deformed([screen, hole], screen_grow(f)) + [ring], g))
        key("Accents", f, deformed(REST["Accents"], g))
    # the code lines write on left to right, one after another
    for f in range(1, 40):
        lines = []
        for i, s in enumerate(REST["Screen"]):
            q = ease_out_back((f - 20 - 3 * i) / 7, 1.2)
            left = np.array([s["pos"][:, 0].min(), s["pos"][:, 2].mean()])
            lines += deformed(deformed([s], lambda xz, q=q, left=left: scale_about(xz, left, max(q, 0.0), 1.0)), screen_grow(min(f, body_frames + 1)))
        g = lambda xz, p=min((f - 1) / body_frames, 1.0): genie(xz, p)
        key("Screen", f, deformed(lines, g))
    # the face pops in once the body has its shape
    for f in range(1, 40):
        q = ease_out_back((f - 24) / 8, 3.0)
        g = lambda xz, p=min((f - 1) / body_frames, 1.0): genie(xz, p)
        face = deformed(REST["Face"], lambda xz, q=q: scale_about(xz, face_c, max(q, 0.0), max(q, 0.0)))
        key("Face", f, deformed(deformed(face, screen_grow(min(f, body_frames + 1))), g))
    # smoke puffs from the tail tip, drifting and fading
    for f in range(1, 20):
        puffs = []
        for i, (drift, col, delay) in enumerate(PUFFS):
            a = np.clip((f - 1 - delay) / 14, 0, 1)
            r = 0.04 + 0.13 * math.sin(math.pi * min(a * 1.2, 1.0)) if a > 0 else 0.0
            c = (TAIL[0] + drift[0] * a ** 0.7, TAIL[1] + 0.02 + drift[1] * a ** 0.7)
            puffs.append(poly(disc(c, r), MAT[col], 100 + i, fo=float(1 - a ** 2) if a > 0 else 0.0))
        key("Smoke", f, puffs)
    G.end_exposure(hal, "Smoke", 20)
    # sparkles twinkle around the genie as it lands
    last = max(b for *_, b in SPARKS) + SPARK_LIFE
    for f in range(SPARKS[0][3], last + 1):
        stars = []
        for i, (c, r, col, birth) in enumerate(SPARKS):
            a = (f - birth) / SPARK_LIFE
            s = math.sin(math.pi * a) ** 0.8 if 0 < a < 1 else 0.0
            stars.append(poly(astroid(c, r * s, math.radians(90 * a)), MAT[col], 200 + i, fo=1.0 if s > 0 else 0.0))
        key("Sparkles", f, stars)
    G.end_exposure(hal, "Sparkles", last + 1)
    G.key(hal, "Sparkles", 1, mode="blank")            # nothing to show before the first sparkle


(build_dance if MODE == "dance" else build_genie)()

for lay in hal.data.layers:
    print(lay.name, [f.frame_number for f in sorted(lay.frames, key=lambda f: f.frame_number)][:6], "...", len(lay.frames), "keys")
print(G.verdict(G.report(hal)))

bpy.ops.wm.save_as_mainfile(filepath=os.path.join(OUT, f"hal-c2-{MODE}.blend"))

# review renders (Blender) and the Lottie export through the add-on's operator
sc.render.image_settings.file_format = "PNG"
sc.render.filepath = os.path.join(WORK, f"frames-{MODE}", "")
bpy.ops.render.render(animation=True)
for fmt, ext in (("JSON", "json"), ("LOTTIE", "lottie")):
    bpy.ops.lottie_exporter.gp_vector(filepath=os.path.join(OUT, f"hal-c2-{MODE}.{ext}"),
                                      format=fmt, float_precision=1, optimize_stroke_keys=True,
                                      export_scope="ALL")
