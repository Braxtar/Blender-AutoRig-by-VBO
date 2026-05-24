# Round-trip constraints (the contract)

ZBrush re-imports a posed OBJ onto a subtool by **matching vertices by index**, then —
via Transpose Master's `TPose>Mesh` — uses that low-res deformation to drive its full
multi-subdivision sculpt. The re-projection only works if the mesh that comes back is the
*same mesh* ZBrush sent out, with vertices in the *same order*, differing **only** in
position. Break that and ZBrush will either reject the import (vertex-count mismatch) or,
worse, silently scramble the sculpt.

Every rule below is a consequence of that single fact. They are ordered by how easy they
are to violate by accident.

## C1 — Never edit topology (the cardinal rule)

The mesh must keep an **identical** vertex count, edge count, polygon count, **and**
face→vertex index connectivity from import to export. In Blender that means: do not enter
Edit Mode to add, delete, dissolve, merge, split, fill, or knife anything, and do not use
any operator/modifier that changes counts or order, including:

- **Merge by Distance / Remove Doubles** — the classic silent killer. Reorders/removes verts.
- **Remesh, Decimate, Subdivision Surface (applied), Multires, Triangulate, Voxel/Quad
  remesh** — all change topology.
- **Symmetrize the *mesh*** (mirror+weld), **Auto Smooth that splits normals into new
  data**, **Separate / Join**, **Delete Loose**.
- **Mesh > Sort Elements**, "Recalculate" ops that reindex.

Allowed: moving existing vertices. That is exactly what an **Armature** modifier does, so
posing is safe. Sculpt-mode brushes that only move existing verts (Grab, Pose brush) are
also fine **as long as Dyntopo/Remesh/Multires are OFF** — those add geometry.

`scripts/validate_roundtrip.py` hashes the connectivity at import and re-checks before
export; it will catch any C1 violation.

## C2 — Never alter the mesh's local coordinates via transforms

Vertex *data* is sacred. Applying scale/rotation/location to the mesh object bakes new
numbers into the vertex coordinates — to ZBrush that is "the artist moved every vertex,"
which corrupts re-projection scale and can misalign the propagation.

Therefore **do not `Object > Apply > Scale/Rotation/All` on the posed mesh.** Blender's
import scale is famously huge/odd, but you fix the *working* size without touching the
mesh:

- Create an **Empty**, parent the mesh to it (`CHILD`, keep transform), and scale the
  **Empty**. The mesh's own transform stays `scale (1,1,1)`, `rotation (0,0,0)`,
  coordinates unchanged.
- Confirm after setup: the **mesh object** still reads `scale = 1.0`. (`import_pose_mesh.py`
  asserts this.)

At export the only transform juggling allowed is the documented sequence in C6.

## C3 — Export from the LOWEST subdivision level

In ZBrush, drop every subtool to **SDiv 1** before running Transpose Master, so the
TPoseMesh is the lowest level. You pose that, and ZBrush propagates the deformation *up*
the subdivision levels onto the high-res detail. If you pose a high level instead, the
lower levels (and thus the propagation) are inconsistent and detail is lost. Lowest level
is also far lighter to rig and pose.

## C4 — One combined mesh via Transpose Master, posed as a unit

Transpose Master merges all subtools into a single `TPoseMesh` so they share one vertex
index space and pose together coherently. Do not split it back into pieces in Blender, and
do not reorder/join meshes. Bring it back as the same single mesh; ZBrush's `TPose>Mesh`
redistributes the result to each original subtool. (If you must treat a rigid part
separately, parent that *whole* object to a bone — never re-topologize it.)

## C5 — Don't destroy the recording layers / use them

Have the user **add a layer to each subtool** before transposing. The pose then lives on
a layer in ZBrush and stays adjustable/reversible. Transpose Master's **Layer** checkbox
recreates these layers automatically when you press `TPose>Mesh`, so the user doesn't have
to make them by hand — remind them to tick it.

## C6 — The exact, safe export sequence

Deviating from this order is how scale/paroity bugs creep in. `export_posed_mesh.py` does
exactly this:

1. **Duplicate** the rigged mesh (keep the original rigged copy for more poses).
2. **Apply modifiers** on the duplicate ("Visual Geometry to Mesh" / `object.convert`):
   bakes the armature (and bendy-bone) deformation **into vertex positions**. Topology is
   untouched — an armature cannot add/remove verts. This also collapses Corrective Smooth.
3. **Clear Parent — Keep Transform** (`parent_clear(type='CLEAR_KEEP_TRANSFORM')`): the
   empty's scale folds into the duplicate's object scale (reads ~`0.02`).
4. **Set object scale back to `(1,1,1)`** — restores the original ZBrush size so the
   exported *global* coordinates equal what ZBrush expects.
5. **Validate** topology fingerprint (must match import) and that scale is now `1.0`.
6. **Export OBJ, Selection Only = ON**, **no triangulation** (keep ngons/quads as-is),
   and the **same axis convention** used on import. Exporting everything, or triangulating,
   breaks the index match.

## C7 — Topology must be finalized before you start

All ZBrush subdivisions present, retopology (ZRemesher with PolyGroups, TopoGun, or hand)
done *before* posing. The pose is keyed to this exact topology. The upside (C-iteration):
if the user later re-sculpts but keeps the **same topology**, the same Blender rig, weights,
and saved poses all still apply — re-import the new TPoseMesh and reuse everything.

## C3b — Lowest-subdiv is a hard practical requirement, not just a quality tip

Confirmed on a 13M-poly test: a full-resolution mesh is unworkable through the connector —
weight-binding exceeds the MCP request timeout, hard-surface weights tear, and OBJs are
gigabytes. The lowest-subdiv TPoseMesh (thousands of polys) makes binding fast and weights
usable, and ZBrush propagates the result upward anyway. `import_pose_mesh.py` warns above
~1.5M verts. Treat a heavy import as a signal that the wrong level was exported from ZBrush.

Connector note: heavy ops (bind, export) may return an MCP timeout while *still completing*
in Blender. Fire → accept the timeout → poll state; never blindly re-fire.

## C8 — OBJ I/O must stay order-stable

Use the same OBJ importer and exporter within one Blender session and never edit between
them, so vertex order is preserved end to end. (Blender's OBJ I/O preserves order when the
mesh isn't edited — the fingerprint check is your safety net.) If the user prefers **GoZ /
the GoB add-on** instead of manual OBJ, that's a valid alternative that also preserves
order and additionally carries PolyGroups/UVs — but the constraints C1–C7 are identical.

---

## Quick pre-export checklist

- [ ] Mesh never entered Edit Mode; no merge/remesh/decimate/triangulate (C1)
- [ ] Mesh object scale = 1.0, rotation = 0; scaling done on the empty only (C2)
- [ ] Source was lowest-subdiv TPoseMesh from Transpose Master (C3, C4)
- [ ] Recording layers present / "Layer" checkbox ticked on return (C5)
- [ ] Export sequence: dup → apply modifiers → clear-parent-keep → scale=1 → export (C6)
- [ ] OBJ exported Selection-Only, no triangulation, matching axes (C6)
- [ ] `validate_roundtrip.py` passed (fingerprint identical)
