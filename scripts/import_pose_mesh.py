# import_pose_mesh.py
# Run via mcp__Blender__execute_blender_code (Blender's Python / bpy).
#
# Imports a ZBrush Transpose-Master "TPoseMesh" OBJ, stamps a topology fingerprint onto
# the object (so we can prove later that nothing changed), and sets up the
# non-destructive scale workaround ONLY if the model imported at an unworkable size.
#
# WHY: ZBrush re-projects by vertex index. We must preserve vertex count + connectivity
# and must NOT bake any transform into the mesh's coordinates. See
# references/round-trip-constraints.md (C1, C2).
#
# TESTED: validated end-to-end on a 13M-poly mesh. The vectorized fingerprint below is
# essential -- a per-polygon Python loop hangs at that scale.

# ====================== CONFIG (edit me) ======================
OBJ_PATH     = r"C:\full\path\to\pose_mesh.obj"   # the TPoseMesh OBJ from ZBrush
TARGET_SIZE  = 2.0          # desired working size (max dim) if a rescale is needed
FORCE_EMPTY  = None         # None = auto (add empty only if scale is unworkable);
                            #   or set a float to force an empty at that scale.
FORWARD_AXIS = "NEGATIVE_Z" # keep the SAME axes on export
UP_AXIS      = "Y"
WARN_VERTS   = 1500000      # warn above this: too heavy to weight-bind via the connector
# ==============================================================

import bpy, struct, os, hashlib
from array import array
import mathutils

def topology_fingerprint(mesh):
    n_loops = len(mesh.loops); n_poly = len(mesh.polygons)
    loop_v = array('i', [0]) * n_loops; mesh.loops.foreach_get("vertex_index", loop_v)
    ploop  = array('i', [0]) * n_poly;  mesh.polygons.foreach_get("loop_total", ploop)
    h = hashlib.sha1()
    h.update(struct.pack("<QQQQ", len(mesh.vertices), len(mesh.edges), n_poly, n_loops))
    h.update(loop_v.tobytes()); h.update(ploop.tobytes())
    return (len(mesh.vertices), len(mesh.edges), n_poly, n_loops, h.hexdigest())

def _obj_import(path):
    before = set(bpy.data.objects)
    if hasattr(bpy.ops.wm, "obj_import"):            # Blender 3.3+/4.x/5.x
        bpy.ops.wm.obj_import(filepath=path, forward_axis=FORWARD_AXIS, up_axis=UP_AXIS)
    else:
        bpy.ops.import_scene.obj(filepath=path)
    new = [o for o in bpy.data.objects if o not in before and o.type == 'MESH']
    if not new:
        raise RuntimeError("OBJ import produced no mesh object: %s" % path)
    if len(new) > 1:
        print("WARNING: import created %d mesh objects. A TPoseMesh must stay ONE mesh "
              "with one vertex-index space (C4). Check your Transpose Master export." % len(new))
    return new[0]

assert os.path.exists(OBJ_PATH), "OBJ_PATH does not exist: %s" % OBJ_PATH
obj = _obj_import(OBJ_PATH)
me  = obj.data

vc, ec, pc, lc, h = topology_fingerprint(me)
obj["zb_vcount"]=vc; obj["zb_ecount"]=ec; obj["zb_pcount"]=pc; obj["zb_lcount"]=lc
obj["zb_conhash"]=h; obj["zb_source"]=os.path.basename(OBJ_PATH)

# world-space size (cheap, from the 8 bound-box corners)
mat = obj.matrix_world
corners = [mat @ mathutils.Vector(c) for c in obj.bound_box]
xs=[c.x for c in corners]; ys=[c.y for c in corners]; zs=[c.z for c in corners]
max_dim = max(max(xs)-min(xs), max(ys)-min(ys), max(zs)-min(zs))

# conditional scale-empty: only if the model is unworkably huge/tiny (C2)
empty = None
need_empty = (FORCE_EMPTY is not None) or not (0.05 <= max_dim <= 200.0)
if need_empty:
    s = FORCE_EMPTY if FORCE_EMPTY is not None else (TARGET_SIZE / max_dim if max_dim else 1.0)
    empty = bpy.data.objects.new("zb_scale_root", None)
    bpy.context.scene.collection.objects.link(empty)
    obj.parent = empty
    obj.matrix_parent_inverse = empty.matrix_world.inverted()
    empty.scale = (s, s, s)
    obj["zb_has_scale_empty"] = True
else:
    obj["zb_has_scale_empty"] = False

assert tuple(round(v, 6) for v in obj.scale) == (1.0, 1.0, 1.0), \
    "Mesh object scale must stay 1.0 -- scale the empty, never the mesh (C2)!"

print("Imported: %s  verts=%d polys=%d  conhash=%s" % (obj.name, vc, pc, h))
print("World max dimension = %.4f" % max_dim)
if empty:
    print("Added scale empty '%s' (scale=%.5f); mesh scale stays 1.0." % (empty.name, empty.scale[0]))
else:
    print("Model already at a workable scale; no empty needed (mesh scale stays 1.0).")
if vc > WARN_VERTS:
    print("WARNING: %d verts is very heavy. This is almost certainly NOT a lowest-"
          "subdivision TPoseMesh (C3). Weight-binding this via the connector will exceed "
          "the request timeout (the op still finishes in Blender -- fire it, accept the "
          "timeout, then poll). For real work, export the LOWEST subdiv level from ZBrush "
          "instead -- binding is then fast and weights are usable." % vc)
print("DO NOT enter Edit Mode or apply transforms on this mesh. Only the armature may "
      "move its vertices. Run validate_roundtrip.py before exporting.")
