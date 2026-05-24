# validate_roundtrip.py
# Run via mcp__Blender__execute_blender_code.
#
# Proves the round-trip contract for an object: its current topology (vertex count +
# connectivity) is byte-identical to what was stamped at import, and its object scale is
# back to 1.0 ready for export. See references/round-trip-constraints.md.
#
# You can validate the LIVE rigged mesh directly (no duplicate needed): pass
# USE_EVALUATED=True to fingerprint the armature-deformed (posed) result via the
# depsgraph — this confirms posing changed only positions. This is what proved integrity
# on a 13M-poly test mesh without writing anything to disk.

# ====================== CONFIG (edit me) ======================
OBJECT_NAME   = ""        # "" = active object
CHECK_SCALE   = True      # pre-export this should be True (scale must read 1.0)
USE_EVALUATED = True      # True = fingerprint the modifier-applied (posed) mesh
# ==============================================================

import bpy, struct, hashlib
from array import array

def topology_fingerprint(mesh):
    n_loops = len(mesh.loops); n_poly = len(mesh.polygons)
    loop_v = array('i', [0]) * n_loops; mesh.loops.foreach_get("vertex_index", loop_v)
    ploop  = array('i', [0]) * n_poly;  mesh.polygons.foreach_get("loop_total", ploop)
    h = hashlib.sha1()
    h.update(struct.pack("<QQQQ", len(mesh.vertices), len(mesh.edges), n_poly, n_loops))
    h.update(loop_v.tobytes()); h.update(ploop.tobytes())
    return (len(mesh.vertices), len(mesh.edges), n_poly, n_loops, h.hexdigest())

def validate(obj, check_scale=True, use_evaluated=False):
    msgs, ok = [], True
    if obj is None or obj.type != 'MESH':
        return False, ["No mesh object to validate."]
    for k in ("zb_vcount","zb_ecount","zb_pcount","zb_lcount","zb_conhash"):
        if k not in obj:
            return False, ["Missing fingerprint '%s'. Import with import_pose_mesh.py." % k]
    if use_evaluated:
        deps = bpy.context.evaluated_depsgraph_get()
        ev = obj.evaluated_get(deps); me = ev.to_mesh()
        vc, ec, pc, lc, h = topology_fingerprint(me); ev.to_mesh_clear()
    else:
        vc, ec, pc, lc, h = topology_fingerprint(obj.data)
    if vc != obj["zb_vcount"]: ok=False; msgs.append("VERTEX COUNT %d -> %d (C1: merge/delete/remesh?)" % (obj["zb_vcount"], vc))
    if ec != obj["zb_ecount"]: ok=False; msgs.append("EDGE COUNT %d -> %d" % (obj["zb_ecount"], ec))
    if pc != obj["zb_pcount"]: ok=False; msgs.append("POLY COUNT %d -> %d" % (obj["zb_pcount"], pc))
    if lc != obj["zb_lcount"]: ok=False; msgs.append("LOOP COUNT %d -> %d" % (obj["zb_lcount"], lc))
    if h  != obj["zb_conhash"]: ok=False; msgs.append("CONNECTIVITY changed (face->vertex order differs).")
    if check_scale:
        s = tuple(round(x,5) for x in obj.scale)
        if s != (1.0,1.0,1.0): ok=False; msgs.append("Object scale %s != (1,1,1) (C2/C6)." % (s,))
    if ok:
        msgs.append("OK: topology identical (v=%d e=%d p=%d l=%d). Safe to export." % (vc,ec,pc,lc))
    return ok, msgs

obj = bpy.data.objects.get(OBJECT_NAME) if OBJECT_NAME else bpy.context.active_object
ok, msgs = validate(obj, CHECK_SCALE, USE_EVALUATED)
print("VALIDATION:", "PASS" if ok else "FAIL")
for m in msgs: print("  -", m)
if not ok:
    print("DO NOT export this mesh to ZBrush. Fix the violation above first.")
