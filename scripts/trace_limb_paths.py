# trace_limb_paths.py
# Run via mcp__Blender__execute_blender_code.
#
# Derives limb medial paths (candidate bone-joint positions) FROM THE MESH instead of
# eyeballing coordinates. Eyeballed bone coords are the #1 cause of bad rigs on non-human
# creatures: a multi-limb model often separates limbs in DEPTH, not just in the front-view
# plane, so bones placed at a flat depth (y=0) miss the limbs entirely.
#
# Strategy: slice the mesh along a primary axis (the limb's spread direction), and within
# each slice cluster the cross-section by a secondary axis to separate overlapping limbs.
# Each cluster's per-slice centroid traces that limb's medial line -> read shoulder/elbow/
# wrist/hand off the polyline.
#
# This is a REPORTING tool: it prints polylines for you to read joint coords from, then you
# place bones at those coords. Inspect, then build.

# ====================== CONFIG (edit me) ======================
OBJECT_NAME   = ""          # "" = active mesh
PRIMARY_AXIS  = "x"         # the axis the limbs spread along (arms: x; legs from hips: z)
PRIMARY_MIN   = 0.34        # start slicing beyond the torso
PRIMARY_MAX   = 1.30
SLICE         = 0.07
SECONDARY_AXIS= "y"         # split overlapping limbs along this axis (depth for stacked arms)
SECONDARY_SPLIT = 0.06      # |secondary| > this => assign to + / - group; between => skip torso
SIDE_SIGN     = 1           # +1 = positive primary side (one half); mirror handles the other
MIN_SLICE_VERTS = 20
# ==============================================================

import bpy, numpy as np
ax = {"x":0,"y":1,"z":2}
pa, sa = ax[PRIMARY_AXIS], ax[SECONDARY_AXIS]

obj = bpy.data.objects.get(OBJECT_NAME) if OBJECT_NAME else bpy.context.active_object
me = obj.data
n = len(me.vertices)
co = np.empty(n*3, dtype=np.float32); me.vertices.foreach_get("co", co); co = co.reshape(-1,3)
M = np.array(obj.matrix_world)
w = (np.hstack([co, np.ones((n,1),np.float32)]) @ M.T)[:,:3]
P, S = w[:,pa]*SIDE_SIGN, w[:,sa]

def trace(sec_mask, label):
    pts = []
    c = PRIMARY_MIN
    while c < PRIMARY_MAX:
        m = (P >= c) & (P < c+SLICE) & sec_mask
        if m.sum() >= MIN_SLICE_VERTS:
            pts.append([round(float(w[m,0].mean()),3), round(float(w[m,1].mean()),3),
                        round(float(w[m,2].mean()),3), int(m.sum())])
        c += SLICE
    return {label: pts}

res = {}
res.update(trace(S >  SECONDARY_SPLIT, "limbA_path(x,y,z,cnt)"))   # e.g. back/upper arm
res.update(trace(S < -SECONDARY_SPLIT, "limbB_path(x,y,z,cnt)"))   # e.g. front/lower arm
res["note"] = ("Read joints off each polyline: first pt ~ shoulder (attach a clavicle from "
               "the spine to it), last pt ~ hand/tip, pick 1-2 interior pts as elbow/wrist. "
               "Build bones at these world coords, then symmetrize for the other side.")
result = res
