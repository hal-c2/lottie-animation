"""Build the HAL-C2 avatar Grease Pencil animations and export them to Lottie.

blender -b --factory-startup --python build_avatar_animations.py -- <dance|genie> <out_dir>

(ANIM=<dance|genie> OUT=<out_dir> in the environment work too.)

`mise run build version1 <dance|genie>` runs this with the environment below
checked first:
  LOTTIE_GP_SCRIPTS        folder holding the bx_gp helper module
  LOTTIE_EXPORT_ADDON_DIR  folder holding the io_lottie_export add-on, unless
                           Blender already imports it
  HAL_C2_AVATAR_SVG        hal-c2-avatar.svg from hal-c2/hal-c2 assets/brand
  LOTTIE_WORK_DIR          review renders (default: <temp dir>/hal-c2-lottie);
                           REVIEW still overrides it

The avatar is imported from SVG as Bezier fills, split into layers by graphic
role, and every frame is a "sculpted" copy of the rest drawing (same strokes,
same points), so the Lottie exporter writes one path key per frame per shape.
"""
import bpy, sys, os, math, tempfile
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
for var in ("LOTTIE_GP_SCRIPTS", "LOTTIE_EXPORT_ADDON_DIR"):
    if os.environ.get(var):
        sys.path.append(os.path.expanduser(os.environ[var]))
sys.path.append(HERE)
import bx_gp as G

ARGS = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
ANIM = ARGS[0] if ARGS else os.environ.get("ANIM", "")
OUT = ARGS[1] if len(ARGS) > 1 else os.environ.get("OUT", "")
if ANIM not in ("dance", "genie") or not OUT:
    sys.exit("usage: blender -b --factory-startup --python build_avatar_animations.py -- <dance|genie> <out_dir>")
WORK = os.environ.get("LOTTIE_WORK_DIR") or os.path.join(tempfile.gettempdir(), "hal-c2-lottie")
REVIEW = os.environ.get("REVIEW", os.path.join(WORK, "version1"))
SVG = os.path.expanduser(os.environ.get("HAL_C2_AVATAR_SVG", ""))
if not os.path.isfile(SVG):
    sys.exit("HAL_C2_AVATAR_SVG must name hal-c2-avatar.svg (hal-c2/hal-c2, assets/brand)")
os.makedirs(OUT, exist_ok=True)

PALETTE = {  # the avatar's own SVG fills, one material per paint bucket
    "Ink": "#010104", "Paper": "#f6f1f1", "Tangerine": "#fba919", "Grape": "#ac75fa",
    "Periwinkle": "#768efb", "Pink": "#f76eb8", "Navy": "#4e5f89",
}
LAYERS = ("Puffs", "Bubble", "Accents", "Screen", "Face", "Sparkles")  # bottom -> top


def lin2srgb(c):
    return 12.92 * c if c <= 0.0031308 else 1.055 * c ** (1 / 2.4) - 0.055


def nearest_bucket(rgb_linear):
    srgb = [lin2srgb(c) for c in rgb_linear]
    def dist(h):
        t = [int(h[i:i + 2], 16) / 255 for i in (1, 3, 5)]
        return sum((a - b) ** 2 for a, b in zip(srgb, t))
    return min(PALETTE, key=lambda k: dist(PALETTE[k]))


# ---------------------------------------------------------------- import rest pose
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.wm.grease_pencil_import_svg(
    filepath=SVG, directory=os.path.dirname(SVG) + "/", files=[{"name": os.path.basename(SVG)}])
src_ob = bpy.data.objects[0]
src = src_ob.data.layers[0].frames[0].drawing
fill_color = src.attributes["fill_color"]  # SVG colors arrive per stroke; the exporter reads materials
rest = []  # one dict per SVG stroke, in SVG draw order
for i, s in enumerate(src.strokes):
    rest.append(dict(
        P=np.array([tuple(p.position) for p in s.points])[:, [0, 2]],
        HL=np.array([tuple(p.handle_left.position) for p in s.points])[:, [0, 2]],
        HR=np.array([tuple(p.handle_right.position) for p in s.points])[:, [0, 2]],
        fill_id=s.fill_id, bezier=True,
        bucket=nearest_bucket(fill_color.data[i].color[:3]),
    ))
bpy.data.objects.remove(src_ob)

# Which SVG strokes belong to which layer (by what they are in the drawing).
ROLE = {"Bubble": [0, 1, 2], "Accents": [3, 5, 6, 8, 12], "Screen": [4, 7, 13, 14], "Face": [9, 10, 11]}
outer = rest[2]["P"]
TAIL = outer[np.argmin(outer[:, 1])].copy()          # tip of the speech-bubble tail
XMIN, XMAX = outer[:, 0].min(), outer[:, 0].max()
ZTOP = outer[:, 1].max()
CX = 0.5 * (XMIN + XMAX)
BASE_Z = rest[1]["P"][:, 1].min() - 0.04               # bottom of the bubble body, above the tail


def centroid(ids):
    pts = np.concatenate([rest[i]["P"] for i in ids])
    return 0.5 * (pts.min(0) + pts.max(0))


# ---------------------------------------------------------------- stage
FPS = 24
FRAMES = {"dance": (1, 24), "genie": (1, 48)}[ANIM]
RES = 512
cam = G.scene_2d(res=(RES, RES), fps=FPS, frame_range=FRAMES, ortho_scale=3.4, background="#ffffff")
cam.location.z = 0.1
ob = G.new_object("HAL", layers=LAYERS)
MAT = {name: G.material(ob, name, fill=hexc) for name, hexc in PALETTE.items()}
for m in ob.data.materials:  # fill-only art: the Lottie exporter writes a stroke item for every
    m.grease_pencil.color[3] = 0.0  # shape and takes its alpha from the material stroke color


def write(d, shapes):
    """shapes: list of dict(P, HL, HR (N,2 xz arrays), fill_id, bucket, bezier, opacity)."""
    if not shapes:
        return
    d.add_strokes([len(s["P"]) for s in shapes])
    bez = [i for i, s in enumerate(shapes) if s["bezier"]]
    if bez:
        d.set_types(type="BEZIER", indices=bez)
    for s, st in zip(shapes, d.strokes):
        st.cyclic = True
        st.fill_id = s["fill_id"]
        st.hide_stroke = True
        st.material_index = MAT[s["bucket"]]
        st.fill_opacity = s.get("opacity", 1.0)
        for j, p in enumerate(st.points):
            p.position = (s["P"][j, 0], 0.0, s["P"][j, 1])
            p.radius = 0.004
            if s["bezier"]:
                p.handle_left.position = (s["HL"][j, 0], 0.0, s["HL"][j, 1])
                p.handle_right.position = (s["HR"][j, 0], 0.0, s["HR"][j, 1])
    d.tag_positions_changed()


def shaped(ids, fn):
    """Rest strokes `ids` with every control point and handle mapped through fn((N,2))."""
    return [dict(rest[i], P=fn(rest[i]["P"]), HL=fn(rest[i]["HL"]), HR=fn(rest[i]["HR"])) for i in ids]


def smoothstep(a, b, x):
    t = np.clip((x - a) / (b - a), 0.0, 1.0)
    return t * t * (3 - 2 * t)


# ---------------------------------------------------------------- dance
def dance():
    """Side-to-side lean like the reference GIF: the tail stays planted, the body bends
    over it, snappy with a short hold at each side. 24 frames = one seamless loop."""
    A = math.radians(14)
    def lean(f):
        s = math.sin(2 * math.pi * (f - 1) / 24)
        return math.copysign(abs(s) ** 0.55, s)

    def bend(amount):
        def fn(P):
            h = np.clip((P[:, 1] - BASE_Z) / (ZTOP - BASE_Z), 0, 1)
            ang = A * amount * h ** 1.3                          # positive: top leans right
            stretch = 1 + 0.035 * abs(amount) * h                # reach up a little at the sides
            above = P[:, 1] > BASE_Z
            dz = (P[:, 1] - BASE_Z) * np.where(above, stretch, 1)
            dx = P[:, 0] - CX
            c, s = np.cos(ang), np.sin(ang)
            out = np.stack([CX + dx * c + dz * s, BASE_Z - dx * s + dz * c], 1)
            return np.where(above[:, None], out, P)
        return fn

    for f in range(FRAMES[0], FRAMES[1] + 1):
        for layer, lag in (("Bubble", 0), ("Accents", 0.5), ("Screen", 0.8), ("Face", 1.4)):
            # overlapping action: the drawing inside the screen trails the body slightly
            write(G.key(ob, layer, f), shaped(ROLE[layer], bend(lean(f - lag))))
    for layer in ("Puffs", "Sparkles"):
        G.key(ob, layer, FRAMES[0])


# ---------------------------------------------------------------- genie
def spring(t, w=9.0, z=0.42):
    """Unit step response of an underdamped spring: 0 -> overshoot -> 1."""
    if t <= 0:
        return 0.0
    wd = w * math.sqrt(1 - z * z)
    return 1 - math.exp(-z * w * t) * (math.cos(wd * t) + z / math.sqrt(1 - z * z) * math.sin(wd * t))


def star(center, r, ang):
    k = np.arange(8)
    rr = np.where(k % 2 == 0, r, r * 0.3)
    a = ang + k * math.pi / 4
    return center + np.stack([rr * np.sin(a), rr * np.cos(a)], 1)


def circle(center, r, n=16):
    a = np.linspace(0, 2 * math.pi, n, endpoint=False)
    return center + np.stack([r * np.cos(a), r * np.sin(a)], 1)


def genie():
    """The avatar pours out of its own speech-bubble tail like a genie from a lamp:
    a narrow swaying wisp rises, twirls, springs open, then the face pops in and
    the code lines type across the screen, with sparkles."""
    H = ZTOP - TAIL[1]
    face_c = centroid(ROLE["Face"])

    def rest_axis(u):  # the centre line from the tail tip up into the body
        return TAIL[0] + (CX - TAIL[0]) * smoothstep(0.0, 0.35, u)

    def body(f):
        t = (f - 1) / FPS
        V = spring(t)                                   # height leads ...
        W = spring(t - 0.09)                            # ... width follows: stretch, then squash
        p = min(1.0, (f - 1) / 26)
        q = smoothstep(0.2, 0.9, p)
        twirl = math.cos(2 * math.pi * (1 - smoothstep(0.0, 0.62, p)))  # one decelerating turn

        def fn(P):
            u = np.clip((P[:, 1] - TAIL[1]) / H, 0, 1)
            funnel = (0.12 + 0.88 * u ** 1.4) * (1 - q) + q
            sway = 0.4 * V * (1 - q) ** 1.3 * u ** 1.2 * np.sin(2 * math.pi * (1.1 * u - 1.7 * p))
            ax = rest_axis(u)
            x = ax + sway + (P[:, 0] - ax) * funnel * W * (twirl if p < 0.62 else 1.0)
            z = TAIL[1] + (P[:, 1] - TAIL[1]) * V
            return np.stack([x, z], 1)
        return fn

    def local_scale(center, s, sx=None):
        def fn(P):
            return center + (P - center) * np.array([sx if sx is not None else s, s])
        return fn

    def compose(*fns):
        def fn(P):
            for g in fns:
                P = g(P)
            return P
        return fn

    PUFFS_END = 1 + 2 * 6 + 16
    SPARKS = (17, 29 + 13)
    for f in range(FRAMES[0], FRAMES[1] + 1):
        t = (f - 1) / FPS
        B = body(f)
        write(G.key(ob, "Bubble", f), shaped(ROLE["Bubble"], B))
        write(G.key(ob, "Accents", f), shaped(ROLE["Accents"], B))

        # Every layer keeps the same strokes on every key of a phase (the exporter tracks
        # shapes by stroke index); parts that are not out yet are collapsed, not removed.
        # Face pops in once the body has opened.
        fs = max(0.0, spring(t - 0.62, w=14, z=0.35))
        write(G.key(ob, "Face", f), shaped(ROLE["Face"], compose(local_scale(face_c, fs), B)))

        # Code lines type in left to right, staggered.
        lines = []
        for k, i in enumerate(sorted(ROLE["Screen"], key=lambda i: -rest[i]["P"][:, 1].max())):
            g = float(smoothstep(0.0, 1.0, (t - 0.72 - 0.07 * k) / 0.22))
            left = np.array([rest[i]["P"][:, 0].min(), rest[i]["P"][:, 1].mean()])
            lines += shaped([i], compose(local_scale(left, g if g < 0.3 else 1.0, sx=g), B))
        write(G.key(ob, "Screen", f), sorted(lines, key=lambda s: s["fill_id"]))

        # Smoke puffs billow out of the tail tip at the start and fade.
        puffs = []
        for k in range(7):
            life = min(max((f - 1 - 2 * k) / 16, 0.0), 1.0)
            if True:
                side = 1 if k % 2 else -1
                c = TAIL + np.array([side * (0.12 + 0.35 * life) + 0.1 * math.sin(k * 2.1),
                                     0.05 + (0.5 + 0.12 * k) * life ** 0.7])
                puffs.append(dict(P=circle(c, 0.07 + 0.22 * life ** 0.6), HL=None, HR=None, bezier=False,
                                  fill_id=100 + k, bucket=("Grape", "Periwinkle", "Pink")[k % 3],
                                  opacity=0.85 * (1 - life) ** 1.4 if 0 < life < 1 else 0.0))
                if not 0 < life < 1:
                    puffs[-1]["P"] = circle(TAIL, 0.0005)
        if f <= PUFFS_END:
            write(G.key(ob, "Puffs", f), puffs)
        elif f == PUFFS_END + 1:
            G.key(ob, "Puffs", f)                   # blank key ends the smoke

        # Sparkles twinkle around the finished avatar.
        spark = []
        for k, (c, r, start, bucket) in enumerate((
                ((-1.38, 0.95), 0.16, 17, "Tangerine"), ((1.35, 1.12), 0.13, 20, "Pink"),
                ((1.42, -0.42), 0.15, 23, "Periwinkle"), ((-1.36, -0.62), 0.12, 26, "Grape"),
                ((0.42, 1.38), 0.1, 29, "Tangerine"))):
            life = min(max((f - start) / 13, 0.0), 1.0)
            spark.append(dict(P=star(np.array(c), max(5e-4, r * math.sin(math.pi * life) ** 0.8), life * math.pi / 2),
                              HL=None, HR=None, bezier=False, fill_id=200 + k, bucket=bucket))
        if f == 1 or f == SPARKS[1] + 1:
            G.key(ob, "Sparkles", f)                # blank before and after the twinkle
        elif SPARKS[0] <= f <= SPARKS[1]:
            write(G.key(ob, "Sparkles", f), spark)


{"dance": dance, "genie": genie}[ANIM]()

# ---------------------------------------------------------------- review + deliver
print(ob.name, G.verdict(G.report(ob)))
sc = bpy.context.scene
sc.render.image_settings.file_format = "PNG"
for f in range(FRAMES[0], FRAMES[1] + 1):
    sc.frame_set(f)
    sc.render.filepath = f"{REVIEW}/{ANIM}/f{f:03d}.png"
    bpy.ops.render.render(write_still=True)

sc.frame_set(FRAMES[0])
bpy.ops.wm.save_as_mainfile(filepath=f"{OUT}/hal-c2-{ANIM}.blend")

import io_lottie_export
io_lottie_export.register()
for fmt, ext in (("JSON", "json"), ("LOTTIE", "lottie")):
    print(bpy.ops.lottie_exporter.gp_vector(
        filepath=f"{OUT}/hal-c2-{ANIM}.{ext}", format=fmt, float_precision=1,
        optimize_stroke_keys=True))
