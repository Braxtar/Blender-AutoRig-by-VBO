# check_symmetry.py
# Run via mcp__Blender__execute_blender_code.
#
# Decides whether the mesh is mirror-symmetric across X BEFORE you rely on Blender's
# `armature.symmetrize`. ZBrush concept/print models are often posed/arranged
# ASYMMETRICALLY (e.g. limbs in different rest positions left vs right). If you symmetrize
# bones on an asymmetric mesh, one side lines up and the other doesn't -- a common, easily
# missed rigging failure.
#
# Method: bin vertices by |x| (distance from the mid-plane). In each bin compare the (y,z)
# centroid of the left half (x>0) to the right half (x<0). If the two halves diverge by
# more than TOL anywhere, the mesh is asymmetric and you must build EACH SIDE's limb bones
# from its own geometry (trace_limb_paths.py per side) instead of symmetrizing positions.

# ====================== CONFIG (edit me) ======================
OBJECT_NAME = ""     # "" = active mesh
TOL         = 0.08   # world-unit divergence (y or z) above which a band is "asymmetric"
# ==============================================================

import bpy, numpy as np
obj = bpy.data.objects.get(OBJECT_NAME) if OBJECT_NAME else bpy.context.active_object
me = obj.data; n = len(me.vertices)
co = np.empty(n*3, dtype=np.float32); me.vertices.foreach_get("co", co); co = co.reshape(-1,3)
M = np.array(obj.matrix_world); w = (np.hstack([co, np.ones((n,1),np.float32)]) @ M.T)[:,:3]
x,y,z = w[:,0],w[:,1],w[:,2]
size = float(max(x.max()-x.min(), y.max()-y.min(), z.max()-z.min()))

bad=[]; bands=0
for ax in np.arange(0.05, abs(x).max(), 0.10):
    L=(x>=ax)&(x<ax+0.10); R=(-x>=ax)&(-x<ax+0.10)
    if L.sum()<30 or R.sum()<30: continue
    bands+=1
    dy=abs(float(y[L].mean())-float(y[R].mean()))
    dz=abs(float(z[L].mean())-float(z[R].mean()))
    if dy>TOL or dz>TOL:
        bad.append({"|x|":round(float(ax),2),"dy":round(dy,3),"dz":round(dz,3),
                    "L_yz":[round(float(y[L].mean()),2),round(float(z[L].mean()),2)],
                    "R_yz":[round(float(y[R].mean()),2),round(float(z[R].mean()),2)]})

asym = len(bad) > 0
result = {
  "model_size": round(size,3), "bands_checked": bands, "tol": TOL,
  "SYMMETRIC": not asym,
  "asymmetric_bands": bad,
  "recommendation": ("Mesh is ~symmetric: symmetrize is safe (build one side, mirror it)."
                     if not asym else
                     "Mesh is ASYMMETRIC. Do NOT rely on symmetrize for bone positions. "
                     "Trace EACH side with trace_limb_paths.py (SIDE_SIGN +1 and -1) and "
                     "build that side's bones from its own medial paths. Use symmetrize only "
                     "to copy naming/constraints, then re-snap the mismatched side's bones."),
}
