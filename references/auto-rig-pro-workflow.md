# Auto-Rig Pro workflow (for the ZBrush → Blender → ZBrush round-trip)

When the decision gate (`references/auto-rigging-landscape.md`) points to **Auto-Rig Pro**,
this is how to drive it for *posing a sculpt that must round-trip back to ZBrush*. ARP is
installed and enabled (module `auto_rig_pro`, v3.78.14); its AI Smart engine (v1.20) lives at
`C:\Users\Vincent\Documents\AutoRigPro\AI`.

ARP is GUI-first, but every step has a `bpy.ops.arp.*` operator you can call through
`mcp__Blender__execute_blender_code`. Operator **names** below are verified against the
installed add-on; some operators open a chooser/modal or take enum args whose exact values
you should read live (`bpy.ops.arp.show_limb_params`, the ARP N-panel, or
`get_python_api_docs`) rather than assume. **Inspect before you assume** — same rule as the
rest of this skill.

## What ARP gives you here (and the one thing it doesn't)

Strong for: standard-ish limbs you want good IK on fast, **multi-limb** bodies (duplicate a
limb), **wings**, **spline-IK** tails/tentacles/fins, and **secondary controllers** for fine
pose-sculpting. ARP rigs the mesh **in place**, so it is round-trip safe.

The one limit: **ARP's Smart (AI) auto-placement is humanoid bipeds only.** For non-human
creatures you place reference bones manually (geometry-derived, exactly as the hand-rig path)
and skip Smart. The AI engine still has nothing to do with creatures.

## Core ARP concepts

- **Reference (`_ref`) bones** — the editable "guide" skeleton you fit to the mesh. You only
  ever position reference bones; ARP builds the real control rig from them.
- **`match_to_rig`** — the "Match to Rig" button: generates/updates the full control rig
  (controllers + mechanism + **deform** bones) from the reference bones. Re-run it after any
  reference-bone edit.
- **Deform bones** — the layer the mesh is skinned to. Weighting always targets these
  (ARP's bind operators do this for you).

## Path A — humanoid (use Smart AI)

1. Add the ARP armature: `bpy.ops.arp.append_arp(...)` (ARP panel ▸ "Add Armature").
2. Enter Smart, set the body markers (neck, chin, shoulders, wrists, spine root, ankles).
   `bpy.ops.arp.guess_markers` uses the AI engine to auto-place them; refine if needed.
   Relevant props: `scn.arp_fingers_to_detect`, `scn.arp_smart_AI_samples`,
   `scn.arp_smart_depth`, `scn.arp_full_facial`.
3. `bpy.ops.arp.match_to_rig` — builds the control rig from the markers.
4. Bind (below), pose, then the round-trip export (below).

## Path B — non-human creature (manual, the common ZBrush case)

1. `check_symmetry.py` and `trace_limb_paths.py` first — same geometry-derived placement as
   the hand-rig path. ARP does not change this.
2. Add the ARP armature (`append_arp`) and enter reference-bone editing
   (`bpy.ops.arp.edit_ref`).
3. Fit the base reference bones (spine, neck, head, legs) to the traced coordinates.
4. Add the extra/odd limbs with `bpy.ops.arp.add_limb` (opens a limb-type chooser — arm, leg,
   spine, tail, ear, **wings**, etc.). For symmetric extras use `bpy.ops.arp.dupli_limb` /
   `bpy.ops.arp.dupli_limb_mirror`; `bpy.ops.arp.disable_limb` removes one. Position each
   added limb's reference bones from its traced medial path.
   - **Multi-arm** (e.g. the four-armed mech): add/duplicate arm limbs, one per arm.
   - **Wings**: the wings limb, then `bpy.ops.arp.align_wings` to fan the feather bones.
   - **Tails / tentacles / fins**: use a **spline-IK** limb for smooth curve control.
   - **Quadruped legs**: ARP's 3-bone digitigrade leg.
5. `bpy.ops.arp.match_to_rig` — generate the control rig. Re-run after any `_ref` edit.

## Binding / skinning (where your two purchases interlock)

ARP's bind engine is selectable via `scn.arp_bind_engine`. Two good options:

- **`bpy.ops.arp.bind_to_rig`** — ARP's own heatmap+voxel binding with auto-splitting; tune
  `arp_bind_*` props (e.g. `arp_bind_split`, `arp_bind_preserve`, `arp_bind_improve_twists`).
- **`bpy.ops.arp.bind_vhds`** — bind through **Voxel Heat Diffuse Skinning** directly. Since
  the TPoseMesh is a merged, often non-watertight sculpt, VHD is the robust choice (see
  `references/auto-rigging-landscape.md`). ARP wires the VHD weights onto its deform bones.

Either way, weighting targets ARP's **deform** bones automatically — you do not hand-pick the
bone layer. Add a **Corrective Smooth** modifier *after* the Armature modifier (Step 3 of
`SKILL.md`). Hard-surface/rigid parts: bone-parent them instead of skinning.

## Posing

- Pose with ARP's controllers; use the **secondary controllers** along the limbs for fine
  shaping (the main reason to prefer ARP over a plain rig on a hero creature pose).
- `bpy.ops.arp.set_pose` / `reset_pose` manage poses; `apply_pose_as_rest` can lock a pose as
  the new rest pose if useful before export.
- Bendy-bone-style smoothing on the secondary controllers is fine — it bakes at export.

## Round-trip export — CRITICAL

ARP builds a large rig (controllers + mechanism + deform bones, plus a separate widget/picker
collection). None of that goes back to ZBrush.

- **Use this skill's `scripts/export_posed_mesh.py`** (SKILL.md Step 5). It evaluates the
  armature-deformed **mesh** in local space, validates the topology fingerprint, and exports
  Selection-Only. This works regardless of how complex the ARP rig is — it bakes the final
  vertex positions only.
- **Do NOT use ARP's FBX/GLTF exporter** (`arp.export`) for the round-trip — that's for game
  engines and would not produce the index-identical OBJ ZBrush needs.
- Export **only the deformed mesh object**, never the ARP rig or its widgets.
- The fingerprint validator is still the gatekeeper: ARP only moves vertices, so topology
  stays identical — but run the validator every time anyway.

## Gotchas

- **Smart AI is humanoid-only** — for creatures, place reference bones manually; don't wait
  for AI markers that won't fit.
- ARP adds twist/secondary/mechanism bones. Harmless for the round-trip (baked away), but it
  means weighting must go to deform bones — let ARP's bind operators handle that, don't
  hand-assign to controllers.
- Re-run `match_to_rig` after editing reference bones, then **re-bind** if deform bones moved.
- The install zip extracts to `auto_rig_pro-master`; the hyphen breaks Python import, so the
  add-on folder must be named `auto_rig_pro` (already handled on this machine).
- Many ARP steps are modal/GUI. If an operator needs interaction the connector can't drive,
  fall back to screenshots + literal user instructions, the same way the skill handles the
  ZBrush-side steps.
