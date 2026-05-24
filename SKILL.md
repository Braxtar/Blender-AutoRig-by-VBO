---
name: zbrush-blender-posing
description: >-
  Pose a ZBrush sculpt non-destructively in Blender (via the Blender MCP connector)
  and round-trip it back into ZBrush so Transpose Master re-projects the pose onto the
  high-resolution multi-subdivision sculpt. Use this whenever the user wants to pose,
  rig, gesture, or "bring to life" a ZBrush model/creature/character in Blender, mentions
  Transpose Master / TPoseMesh / GoZ-free OBJ posing, or asks how to get a posed mesh
  back into ZBrush without breaking it. The skill first helps pick the right rigging
  approach (hand-rig, Rigify metarig template, Rigify rig-types for custom creatures, or
  an external auto-rigger like Auto-Rig Pro) via a decision gate, then preserves the strict
  round-trip constraints (identical vertex count + connectivity, untouched mesh-local
  coordinates, scale handled only via a parent empty, lowest-subdivision export). Trigger
  even if the user only says "pose my sculpt in Blender" or "rig this creature for a
  concept render / 3D print" — getting the constraints right is the hard part and is
  exactly what this skill is for.
---

# ZBrush → Blender → ZBrush posing (non-destructive round-trip)

This skill drives **Blender through the Blender MCP connector** (`mcp__Blender__*`,
chiefly `execute_blender_code`) to rig and pose a sculpt that originated in ZBrush, then
export it so it re-projects cleanly onto the original high-res sculpt.

It is based on the workflow taught by creature artist **Gareth Brewer** (workshop hosted
by Pablo Muñoz Gómez, ZBrushGuides). The method is for **concept work, portfolio shots,
and 3D printing** — fast, gesture-first posing — not production animation rigs.

## The one idea that makes the whole thing work

ZBrush re-imports a posed OBJ onto a subtool by matching **vertices by index**. It does
not look at names, UVs, or positions to decide identity — it trusts the order. Posing is
allowed only because moving a vertex doesn't change which index it is. So the entire job
is: **deform vertices, change absolutely nothing else about the mesh's identity.**

Everything below exists to protect that invariant. If you internalize *why* (index-based
re-projection), the rules stop feeling arbitrary.

> Read `references/round-trip-constraints.md` before touching the mesh. It is the
> contract. `scripts/validate_roundtrip.py` enforces it programmatically — run it before
> every export. Do not skip it; a single stray Merge-by-Distance silently corrupts the
> whole re-projection and the user won't find out until ZBrush mangles their sculpt.

## Workflow overview

```
ZBrush (user)            Blender (you, via the connector)              ZBrush (user)
-----------              --------------------------------              ------------
finalize sculpt   ->     import OBJ (no edits, no scale)        ->     import OBJ onto
add layer / subtool      parent to empty, scale the EMPTY              the TPoseMesh subtool
go to LOWEST subdiv      pick rig approach (decision gate)             press TPose>Mesh
Transpose Master  ->     rig + weight + corrective smooth       ->     (pose propagates up
export TPoseMesh.obj     pose (bendy bones ok)                         all subdiv levels)
                         duplicate -> apply armature -> reset scale
                         export OBJ (Selection Only)
```

You own the **Blender** column. The ZBrush columns are user actions — give clear,
literal instructions for them (see `references/zbrush-side.md`). If a ZBrush MCP
(`mcp__zbrush__*`) is connected and the user wants it automated, you may drive those
steps too, but the Blender connector is the spine of this skill.

## Performance & connector limits (read this — it shapes the whole job)

Validated end-to-end on a real 13M-polygon mesh. Hard lessons that change how you work:

- **Use the LOWEST-subdivision TPoseMesh (C3) — this is not optional in practice.** A
  full-resolution sculpt (millions of polys, a multi-hundred-MB OBJ) is the wrong input.
  At that scale, weight-binding through the connector *exceeds the MCP request timeout*,
  weights on hard surfaces are unusable, and exported files are gigabytes. On a proper
  lowest-subdiv mesh (typically thousands of polys) everything below is fast and clean.
  On import, `import_pose_mesh.py` warns when the vert count is suspiciously high — heed it.
- **Heavy operations time out at the MCP layer but keep running in Blender.** If a bind or
  export returns a timeout, do NOT assume it failed: wait, then poll state
  (`get_objects_summary`, or check `obj.modifiers` / file size). Fire → accept the timeout
  → poll. Don't re-fire blindly; that stacks duplicate operations.
- **Never loop over polygons in Python.** Use the vectorized `foreach_get` fingerprint in
  the scripts — a per-poly loop hangs at multi-million-poly scale.
- **For hard-surface models (mechs, armor, props), don't rely on smooth weights.** Auto/
  envelope weights tear rigid parts. Parent each rigid piece to a single bone instead
  (see the weights section). Envelope binding is only a fast, crude fallback for very
  heavy meshes.
- **Blender 5.1 sped action evaluation ~130% and shapekey evaluation up to ~240%** vs 5.0.
  Heavy posed meshes scrub and play back noticeably faster — but this changes nothing about
  the export contract; the validator is still the gatekeeper.

## Step 0 — Confirm what arrived from ZBrush

Before anything, get the user to produce the export correctly, because mistakes here are
invisible until the very end:

- The OBJ must be a **Transpose Master "TPoseMesh"** (all subtools merged into one mesh)
  exported at the **lowest subdivision level**. Posing the lowest level is what lets
  ZBrush propagate the deformation *up* to the millions-of-polys detail. Posing a high
  level throws that away.
- Tell the user to **add a layer to each subtool first** (a recording layer) so the pose
  is reversible in ZBrush. Transpose Master can also recreate these layers on the way
  back via its "Layer" checkbox.

Ask for the OBJ path, then inspect it with the connector before rigging:
`mcp__Blender__get_objects_summary` and `get_object_detail_summary`.

> **Round-trip safety — what you may and may not rig with.** Any rigging tool that rigs
> the *existing* mesh in place (Rigify, Auto-Rig Pro, hand-rigging, AccuRIG/Mixamo) is
> safe: posing then baking moves vertices without changing their index. **Never** route
> the mesh through an AI tool that *regenerates or retopologizes* it (Tripo, Meshy,
> DeepMotion-style one-click mesh+rig generators) — a new mesh has new vertex indices and
> the ZBrush re-projection is destroyed. The fingerprint validator will catch it, but
> don't waste the round trip. See `references/auto-rigging-landscape.md`.

## Step 1 — Import without destroying vertex history

Use `scripts/import_pose_mesh.py` (run its contents through
`mcp__Blender__execute_blender_code`; edit the CONFIG block at the top first). It:

1. Imports the OBJ.
2. **Stamps a topology fingerprint** (vertex/edge/poly counts + a hash of the
   face→vertex index connectivity) onto the object as a custom property. This is the
   ground truth you validate against before export.
3. Creates an **Empty** and parents the mesh to it, scaling the **Empty** (not the mesh)
   to bring Blender's nonsensical import scale into a workable range — but only **if the
   model imported at an unworkable size**. Many OBJs already arrive at a sane scale (the
   test robot did), in which case the script skips the empty. Either way the mesh's own
   `scale` stays `(1,1,1)` and its local coordinates are never touched.

Why the empty: ZBrush and Blender disagree wildly on unit scale. You must *not* apply
scale to the mesh (that bakes new coordinates = altered vertex data). Scaling a parent
empty changes the *display* size only; the mesh data stays byte-for-byte what ZBrush
sent. See the constraints reference for the full reasoning.

After import, **never enter Edit Mode on this mesh.** No merge, no delete, no fill, no
remesh, no decimate, no triangulate, no Auto-Smooth-that-splits, no symmetrize of the
*mesh*. Only the armature may move its vertices.

## Step 1.5 — Choose the rigging approach (decision gate)

**Do this before building any bones.** The biggest efficiency win is picking the right rig
for the body plan instead of always hand-rigging. Two questions decide it. The full
matrix, costs, and 2026 tool landscape are in `references/auto-rigging-landscape.md`; the
short gate:

**Question 1 — what is the body plan?** Both **Auto-Rig Pro** (with its AI Smart engine) and
free **Rigify** are installed; choose per the body plan. Full matrix in
`references/auto-rigging-landscape.md`.

- **Standard humanoid** → **ARP Smart** is the fast path: the AI engine auto-places bones
  from a few rendered viewpoints (asymmetry supported). Free alternative: Rigify **Human**
  metarig (`Add ▸ Armature ▸ Human (Meta-Rig)`), align, Generate.
- **Standard quadruped / bird / fish** → either **ARP** (3-bone digitigrade/quad IK) or a
  Rigify **bird / cat / horse / shark / wolf** metarig — align, Generate.
- **Non-standard** (multi-limb, wings, fins, extra appendages, fantasy, asymmetric — the
  common ZBrush case) → two strong options:
  - **ARP modular** — duplicate/remove limbs for multi-arm bodies, the **wings** limb,
    **spline-IK** for tentacles/tails/fins, quad IK for legs, plus **secondary controllers**
    for fine pose-sculpting. Usually the fastest route to a *good-feeling* creature pose.
    ARP's Smart AI is humanoid-only, so place these limbs manually from geometry
    (`scripts/trace_limb_paths.py`). Full steps in `references/auto-rig-pro-workflow.md`.
  - **Rigify rig-types** (free) — compose per-chain types and Generate
    (`references/rigify-rig-types.md`). Just as capable for a static pose, no cost.
- **Truly bizarre / fastest one-and-done** → **hand-rig** (Step 2 below). For a single baked
  gesture it is often the quickest path of all.

*Honest note:* for a single print pose the deformation is baked and the rig discarded, so
**free Rigify or hand-rig is entirely sufficient for the print result**. ARP's edge is
workflow speed and pose ergonomics on complex/multi-limb creatures, and reuse across many
poses — not the printed output itself. Reach for ARP when its modular limbs and controllers
genuinely save you time; use Rigify when they don't.

**Question 2 — will the rig be reused?**

- **One-off, bake-and-export** → any path above, **posing-only**. The control rig is thrown
  away at export, so don't over-build. This is the skill's default.
- **Reusable puppet / re-pose often / animation** → generate a full **animation-ready**
  control rig (Rigify Generate or ARP): IK/FK switching, pole targets, foot roll, pose
  library. More setup; only worth it if you'll drive it repeatedly.

The difference between *posing-only* and *animation-ready*, and why the default is
posing-only, is explained in `references/auto-rigging-landscape.md`.

Whatever you pick, the rest of the skill (weights, pose, export, hand-back) is identical —
all approaches converge on a mesh deformed by an armature, baked at export.

## Step 2 — Rig (hand-rigging path)

This section is the **hand-rig path** from the gate. If you chose a Rigify metarig template
or rig-types, follow `references/rigify-rig-types.md` instead, then come back to Step 3.
Full details and ready code patterns for hand-rigging are in
`references/rigging-and-posing.md`. The short version:

- **Place limb bones from the geometry, not eyeballed numbers.** On non-human creatures
  (extra arms, wings, tails) this is the difference between a working rig and a broken one
  — limbs often separate in *depth*, not just the front-view plane. Run
  `scripts/trace_limb_paths.py` to get medial polylines per limb, read joint coords off
  them, and verify bones over the mesh in X-ray from a 3/4 angle before binding. (Tested:
  a four-armed mech's arms only aligned once placed this way.) The same geometry-derived
  placement is what you do when aligning a Rigify metarig too.
- Build a quick, dirty armature: hips at the centre of mass, spine, head/jaw, limbs.
  One bone per finger/toe is plenty ("cheat" rigging) — this is for a pose, not a film.
- Separate control: parent legs → hips, spine+tail → a master/body bone, hips → master.
- Add **IK** to limbs you want planted (extrude a control bone, clear its parent,
  `CTRL+SHIFT+C` → Inverse Kinematics, set a sensible chain length). Use **Damped Track**
  for toe/fin clusters and **Stretch To** for cartoony stretch, ears, capes.
- Name only what matters (`hips`, `spine.1`, `tail.1`, plus `.L` suffixes), then
  **Symmetrize** the armature — it mirrors bones, constraints, and parenting and renames
  to `.R` automatically. **But check symmetry first** with `scripts/check_symmetry.py`:
  symmetrize only works if the *mesh* is mirror-symmetric. Many ZBrush models are posed
  asymmetrically (the tested mech's arms ran diagonally), and symmetrizing then leaves one
  side's bones off the limbs — correct head-on, obviously wrong from the top. If
  asymmetric, build/snap each side from its own `trace_limb_paths.py` run.

> **Blender 5.x API note for scripts.** Bone visibility and selection now live on the
> *pose bone* (per-instance), not shared armature layers — set `pose_bone.bone.hide` /
> selection per bone, not via the old layer API. Upside: drivers now survive bone renames,
> so `symmetrize`'s `.L`→`.R` renaming no longer drops constraints/drivers.

## Step 3 — Weights

- Preferred: **Voxel Heat Diffuse Skinning** add-on (~$30, volumetric, actively maintained
  for Blender 5.1 as of 2026). The TPoseMesh is all subtools *merged* — usually non-
  watertight, with overlaps and gaps — which is exactly where Blender's native bone-heat
  weights fail ("failed to find solution for one or more bones"). VHD voxelizes the mesh
  into a solid and diffuses heat through the volume, so it skins non-airtight, multi-limb,
  asymmetric meshes in one click. It writes only vertex groups, so topology stays intact
  (round-trip safe). Its bundled **Surface Heat Diffuse** sharpens fingers/toes, and its
  **Joint Alignment Tool** can push bones to a part's volume center (pairs with
  `trace_limb_paths.py`). Otherwise Blender's automatic weights
  (`bpy.ops.object.parent_set(type='ARMATURE_AUTO')`), which needs more cleanup. For
  transferring weights onto tight clothing/props from an already-weighted body, the free
  **Robust Weight Transfer** add-on is a good one-click option.
- **If you generated a Rigify or ARP control rig, weight to the `DEF-` deformation bones,
  not the control bones.** Voxel Heat Diffuse binds to deform bones correctly. This is the
  one extra subtlety a generated rig adds over a hand rig.
- Add a **Corrective Smooth** modifier (delta-mush-like) to preserve volume across joints.
  It must sit **after** the Armature modifier in the stack, so it smooths the already-
  deformed result. (Above the Armature it would smooth the rest pose and do nothing useful.)
- Hard-surface parts and stiff clothing: don't weight-paint — parent the whole object to
  a single bone. Tight clothing: a **Data Transfer** modifier from the body. A saddle:
  its own bone parented to the back, the saddle object parented to that bone.
- In Blender 5.1 weight paint, **loop selection works with Vertex Selection** — handy for
  isolating a joint loop during cleanup.

## Step 4 — Pose

- Pose Mode. Use IK handles and FK rotations; lock unwanted rotation axes in the Item
  panel for clean single-axis control.
- **Bendy bones** (set bone segments, e.g. 4) give smooth arcing limbs/spines — fine here
  because we're not targeting a game engine. The deformation is baked at export.
- **Copy Global Transform is now built into Blender 5.x** (no longer an add-on). Use it to
  copy a pose, paste it, or **paste-flipped** onto the mirrored bones — faster than the old
  copy/paste-flip dance for blocking symmetric or contrapposto variants.
- Save poses in the **Action Editor** + **Stash**, or as **pose assets in the Asset
  Browser**, so the user can flip between contrapposto, sitting, etc.
- For finger/cape micro-adjustments, prefer Blender's **Pose brush** or finishing in
  ZBrush over fiddly per-digit rigs.

## Step 5 — Export the posed mesh (the careful part)

Use `scripts/export_posed_mesh.py` (via `execute_blender_code`; set the output path in its
CONFIG block). It refuses to export if the fingerprint check fails.

In the **GUI**, Gareth's literal sequence is: duplicate → "Visual Geometry to Mesh"
(apply modifiers / bake armature deform) → "Clear Parent — Keep Transform" → reset object
scale to `(1,1,1)` → export Selection Only. Teach a user doing it by hand exactly that.

> **If you used a generated Rigify/ARP rig:** export the *mesh*, not the generated rig
> object. The control rig is a separate object full of control/mechanism bones; it plays
> no part in the OBJ that goes back to ZBrush. Select only the deformed mesh.

The **script** does the programmatic equivalent, which is also **memory-safe** (it does
*not* duplicate a multi-million-vert object — that risks out-of-memory):

1. **Evaluate** the armature-deformed mesh into a temp mesh in the object's **local**
   space (`new_from_object`). Applying the armature bakes the pose into positions while
   leaving vertex count/connectivity untouched. Local space *excludes any scale-empty*, so
   coordinates emerge at the original ZBrush scale automatically.
2. **Validate** the temp mesh's fingerprint against the import (topology must be identical).
3. Put it on a temp object carrying only the importer's **axis rotation** and scale `1`.
4. **Export OBJ, Selection Only**, no triangulation, axes mirroring the import — which
   reverses the conversion back to ZBrush's frame. The rigged original is left untouched.

If validation fails, the script **stops and reports** — it never writes a corrupt OBJ.
(Exported files can be much larger than the source; that's float precision + normals/UVs,
not a topology change — the fingerprint guarantees identity.)

## Step 6 — Hand back to ZBrush

Tell the user: select the original **TPoseMesh** subtool → **Tool > Import** the posed
OBJ → press **Transpose Master "TPose>Mesh"**. The low-res pose propagates onto the full
multi-subdivision sculpt across every subtool. Details in `references/zbrush-side.md`.

## Iteration (a big payoff — surface it to the user)

Once the rig exists, the sculpt and the pose are decoupled:
- Re-sculpt in ZBrush **keeping topology identical** → new TPoseMesh → re-import into the
  *same* Blender file → re-bind/reparent. If topology matches, weights and saved poses
  just work again.
- Re-pose any time by loading a stashed action / pose asset and re-running Step 5.

This is why the setup cost is worth it: the user gets a reusable digital puppet. (And it is
the argument for spending a little more on an animation-ready rig up front — see the gate.)

## Reference files

- `references/round-trip-constraints.md` — the hard rules, each with its reason. **Read first.**
- `references/auto-rigging-landscape.md` — the rigging decision gate, the 2026 tool matrix
  (Rigify, Auto-Rig Pro, AccuRIG/Mixamo, AI riggers, Voxel Heat Diffuse, Robust Weight
  Transfer), round-trip safety, and the posing-only vs animation-ready explanation.
- `references/auto-rig-pro-workflow.md` — full Auto-Rig Pro workflow for the round-trip:
  humanoid Smart-AI path, non-human modular path (multi-limb, wings, spline-IK tails),
  binding via `bind_vhds`, and the critical export rules.
- `references/rigify-rig-types.md` — how to rig custom/non-human creatures with Rigify by
  assigning per-bone rig types, why the Generate button greys out, and the verified rig-type
  catalog mapped to creature parts.
- `references/rigging-and-posing.md` — hand-rig bone building, IK/FK, constraints, weights,
  posing, with copy-ready bpy snippets for the connector.
- `references/zbrush-side.md` — literal instructions for the user's ZBrush steps.

## Scripts (run through `mcp__Blender__execute_blender_code`)

- `scripts/check_symmetry.py` — detect whether the mesh is mirror-symmetric before trusting `symmetrize`; run before rigging limbs.
- `scripts/trace_limb_paths.py` — derive limb medial paths (bone-joint coords) from the mesh; use before placing limb bones on non-human creatures, per side if asymmetric.
- `scripts/import_pose_mesh.py` — import + fast fingerprint + (conditional) empty-scale + heavy-mesh warning.
- `scripts/assign_rigify_types.py` — assign Rigify rig types to a hand-built/custom skeleton from a CONFIG map (turns a plain armature into a generate-able metarig), optionally Generate. Pairs with `references/rigify-rig-types.md`.
- `scripts/validate_roundtrip.py` — verify topology integrity & scale; set `USE_EVALUATED=True` to check the *posed* (armature-applied) result directly, no duplicate needed.
- `scripts/export_posed_mesh.py` — evaluate posed mesh (local space) → validate → export Selection-Only OBJ, memory-safe.
- `scripts/_fingerprint.py` — the shared vectorized `foreach_get` fingerprint (reference; the function is inlined in each script so it runs standalone via the connector).

Each script has a CONFIG block at the top — edit the paths/values, then send the whole
file as the `code` argument. Prefer these over improvising bpy: they encode the constraints
so each run can't reinvent (and re-break) them.
