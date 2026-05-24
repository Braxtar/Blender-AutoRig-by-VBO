# _fingerprint.py  (shared helper, inlined into the other scripts)
# Fast, vectorized topology fingerprint. DO NOT loop over polygons in Python — at
# multi-million-poly scale (e.g. a real ZBrush export) a per-polygon loop is unusably
# slow and will appear to hang. foreach_get pulls everything into a stdlib array.array
# (buffer protocol) in C, so a 13M-poly mesh hashes in well under a second.
#
# Positions are deliberately excluded from the hash: posing changes positions, never
# identity/order. We hash counts + the face->vertex index stream + per-face loop sizes,
# which is exactly the invariant ZBrush's index-based re-projection depends on.

import hashlib, struct
from array import array

def topology_fingerprint(mesh):
    n_loops = len(mesh.loops)
    n_poly  = len(mesh.polygons)
    loop_v = array('i', [0]) * n_loops          # allocate n_loops int32 slots
    mesh.loops.foreach_get("vertex_index", loop_v)
    ploop  = array('i', [0]) * n_poly
    mesh.polygons.foreach_get("loop_total", ploop)
    h = hashlib.sha1()
    h.update(struct.pack("<QQQQ", len(mesh.vertices), len(mesh.edges), n_poly, n_loops))
    h.update(loop_v.tobytes())
    h.update(ploop.tobytes())
    return (len(mesh.vertices), len(mesh.edges), n_poly, n_loops, h.hexdigest())
