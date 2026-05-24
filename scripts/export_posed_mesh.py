# export_posed_mesh.py
# Run via mcp__Blender__execute_blender_code.
#
# Exports the posed mesh back to an OBJ that ZBrush re-imports onto the TPoseMesh subtool.
# Validates topology against the import fingerprint FIRST and refuses to export on mismatch.
#
# METHOD (memory-safe, scale-robust): evaluate the armature-deformed mesh into a temp mesh
# in the object's LOCAL space (new_from_object). Local space excludes any parent scale-
# empty, so coordinates come out at the ORIGINAL ZBrush scale automatically. The temp
# object gets only the importer's axis rotation and scale 1; exporting with axes mirroring
# the import reverses the conversion back to ZBrush's frame.
#
# This is the programmatic equivalent of Gareth's GUI sequence (duplicate -> Visual
# Geometry to Mesh -> Clear Parent Keep Transform -> reset scale to 1 -> export Selection
# Only), but WITHOUT duplicating a multi-million-vert object (which risks OOM). It bakes
# the armature deformation, drops the scale-empty, and leaves the rigged original untouched.
#
# TESTED: verified live on a 13M-poly posed mesh -- exported v/f counts matched the source.

# ====================== CONFIG (edit me) ======================
SOURCE_OBJECT_NAME = ""   # "" = active object (the rigged, posed mesh)
OUTPUT_PATH        = r"C:\full\path\to\pose_mesh_POSED.obj"
FORWARD_AXIS       = "NEGATIVE_Z"   # MUST match import_pose_mesh.py
UP_AXIS            = "Y"
# ==============================================================

import bpy, struct, hashlib, os
from array import array

def topology_fingerprint(mesh):
    n_loops = len(mesh.loops); n_poly = len(mesh.polygons)
    loop_v = array('i', [0]) * n_loops; mesh.loops.foreach_get("vertex_index", loop_v)
    ploop  = array('i', [0]) * n_poly;  mesh.polygons.foreach_get("loop_total", ploop)
    h = hashlib.sha1()
    h.update(struct.pack("<QQQQ", len(mesh.vertices), len(mesh.edges), n_poly, n_loops))
    h.update(loop_v.tobytes()); h.update(ploop.tobytes())
    return (len(mesh.vertices), len(mesh.edges), n_poly, n_loops, h.hexdigest())

src = bpy.data.objects.get(SOURCE_OBJECT_NAME) if SOURCE_OBJECT_NAME else bpy.context.active_object
assert src and src.type == 'MESH', "Select the rigged posed mesh (or set SOURCE_OBJECT_NAME)."
for k in ("zb_vcount", "zb_conhash"):
    assert k in src, "Missing fingerprint -- import with import_pose_mesh.py."

bpy.ops.object.mode_set(mode='OBJECT')

# 1) evaluate armature-deformed mesh in LOCAL space (modifiers applied, scale-empty excluded)
deps = bpy.context.evaluated_depsgraph_get()
ev   = src.evaluated_get(deps)
tmp_me = bpy.data.meshes.new_from_object(ev)            # owns its data; local coords

# 2) validate BEFORE writing: topology must equal the import fingerprint (C1)
vc, ec, pc, lc, h = topology_fingerprint(tmp_me)
ok = (vc == src["zb_vcount"] and ec == src["zb_ecount"] and pc == src["zb_pcount"]
      and lc == src["zb_lcount"] and h == src["zb_conhash"])
print("PRE-EXPORT VALIDATION:", "PASS" if ok else "FAIL",
      "(v=%d e=%d p=%d l=%d)" % (vc, ec, pc, lc))
if not ok:
    bpy.data.meshes.remove(tmp_me)
    raise RuntimeError("Export aborted: topology differs from import (C1). Do NOT send a "
                       "corrupt OBJ to ZBrush.")

# 3) temp object carrying ONLY the importer axis rotation + scale 1 (no parent, no empty)
tmp_obj = bpy.data.objects.new(src.name + "_export", tmp_me)
bpy.context.scene.collection.objects.link(tmp_obj)
tmp_obj.location = (0, 0, 0)
tmp_obj.scale = (1, 1, 1)
tmp_obj.rotation_euler = src.rotation_euler        # the Y->Z conversion rotation from import

bpy.ops.object.select_all(action='DESELECT')
tmp_obj.select_set(True); bpy.context.view_layer.objects.active = tmp_obj

# 4) export Selection Only, no triangulation, axes mirroring import (C6)
if os.path.exists(OUTPUT_PATH):
    try: os.remove(OUTPUT_PATH)
    except: pass
bpy.ops.wm.obj_export(
    filepath=OUTPUT_PATH, export_selected_objects=True, apply_modifiers=False,
    export_triangulated_mesh=False, forward_axis=FORWARD_AXIS, up_axis=UP_AXIS,
    export_uv=True, export_normals=True, export_materials=False)

# 5) cleanup temp; rigged original is untouched and still posable
bpy.data.objects.remove(tmp_obj, do_unlink=True)
bpy.data.meshes.remove(tmp_me)

print("Exported posed mesh -> %s (%s bytes)"
      % (OUTPUT_PATH, os.path.getsize(OUTPUT_PATH) if os.path.exists(OUTPUT_PATH) else "?"))
print("Next (ZBrush): select the TPoseMesh subtool -> Tool>Import this OBJ -> Transpose "
      "Master 'TPose>Mesh'. A large file is just float precision/normals, not a topology change.")
