# Rigging custom / non-human creatures with Rigify rig-types

Rigify is not limited to its humanoid and animal templates. You can rig an arbitrary
creature — four arms, wings, fins, a tail, asymmetry — by composing the skeleton from
**per-chain rig types** and pressing Generate. This is the free best path for the
non-standard ZBrush models this skill targets, and it gives a proper IK/FK control rig that
hand-rigging does not. Placement work is identical to hand-rigging
(`scripts/trace_limb_paths.py`); only the control layer differs.

Use `scripts/assign_rigify_types.py` to do the assignment from a CONFIG map.

## Why the Generate button greys out (FAQ)

The Rigify panel and its **Generate Rig** button are disabled unless the active armature is
a **metarig**. Rigify's own test (verified in source, `rigify.ui.is_metarig`) is:

```python
def is_metarig(obj):
    if not (obj and obj.data and obj.type == 'ARMATURE'): return False
    if 'rig_id' in obj.data: return False          # already a generated rig
    for b in obj.pose.bones:
        if b.rigify_type != "": return True         # at least one typed bone
    return False
```

So Generate greys out when **no pose bone has a `rigify_type` assigned** — which is exactly
the state of a hand-built armature (built with `edit_bones.new()` and never typed). It is
*not* a broken install and *not* a mode problem. Assign a rig type to at least one chain and
the panel lights up. (It also greys out on an *already-generated* rig, which carries a
`rig_id` on its armature data.)

The rig-type dropdown lives in **Bone Properties ▸ Rigify Type** when a bone is selected in
**Pose Mode**.

## How it works

You assign a rig type to the **first bone of a chain**. Rigify consumes that bone plus its
connected children to generate controls. Generate then builds a **separate** control-rig
object and leaves your metarig untouched. You bind the mesh to the generated rig's `DEF-`
bones.

Programmatically:

```python
import bpy
ob = bpy.context.object                      # the metarig armature, active
pb = ob.pose.bones["upper_arm.L"]            # first bone of the chain
pb.rigify_type = "limbs.super_limb"          # assign the type
pb.rigify_parameters.limb_type = "arm"       # set type-specific params
# ...assign other chains...
bpy.ops.pose.rigify_generate()               # poll passes once any bone is typed
```

Parameters for the assigned type live on `pose_bone.rigify_parameters` (the property group
changes shape depending on the assigned `rigify_type`).

## Verified rig-type catalog (Blender 5.1, Rigify 0.6.x) mapped to creature parts

| Rig type | Consumes | Use it for | Key params |
|---|---|---|---|
| `basic.super_copy` | 1 bone | head, jaw, single rigid prop, root/master, one-off appendage | make_control, make_deform, make_widget |
| `basic.super_finger` | connected chain | fingers, toes, claws, segmented antennae — one curl control | — |
| `limbs.super_limb` | 3-segment chain + tip | **the workhorse** — any arm/leg-like limb; full IK/FK + pole + stretch (proxy → arm/leg/paw via `limb_type`) | limb_type, segments, bbones |
| `limbs.arm` / `limbs.leg` | 3-segment chain | genuinely humanoid limbs (leg adds foot roll/pivot) | foot_pivot_type, extra_ik_toe |
| `limbs.paw` / `front_paw` / `rear_paw` | chain | digitigrade quadruped legs | — |
| `limbs.simple_tentacle` | connected chain | tails, trunks, fins — smooth FK tweak arcs (replaces manual bendy-bone fiddling) | copy_rotation_axes, roll_alignment |
| `limbs.spline_tentacle` | connected chain | long flexible appendages posed like a curve — tentacles, cables, vines, long tails | sik_start/mid/end_controls, sik_stretch_control, sik_radius_scaling |
| `limbs.super_palm` | palm bones | a hand palm spread | — |
| `spines.basic_spine` | spine chain | torso — hip/chest controls + tweaks | pivot_pos, make_fk_controls |
| `spines.super_spine` | spine chain | torso + neck + head in one (proxy that splits into parts) | — |
| `spines.basic_tail` | chain off the spine | a tail attached to the spine | copy_rotation_axes |
| `spines.super_head` | neck → head | head with long-neck support | — |
| `basic.copy_chain` / `basic.raw_copy` / `basic.pivot` | chain / 1 bone | pass-through deform chains, raw copies, pivot helpers | — |
| `skin.*`, `faces.super_face`, `face.*` | — | facial / skin systems — rarely needed for a posing round-trip | — |

`limbs.super_limb` is a proxy that resolves to arm/leg/paw based on its `limb_type`
parameter — for most creature limbs it is the one to reach for first.

## Workflow for a non-human creature

1. **Check symmetry** (`scripts/check_symmetry.py`) and **trace joints**
   (`scripts/trace_limb_paths.py`) — same as the hand-rig path.
2. **Build the bone chains** at the traced coordinates. Each functional limb/spine/tail is a
   *connected* chain whose first bone you will type. Connectivity matters: tentacle and
   spine types expect a connected chain.
3. **Assign rig types** to each chain's first bone (use `scripts/assign_rigify_types.py`):
   `super_limb` per arm/leg, `simple_`/`spline_tentacle` for tails/wings/fins,
   `basic_spine`/`super_spine` for the torso, `super_head` for the head, `super_copy` for
   single bones (jaw, props), `super_finger` for digits.
4. **Generate** (`bpy.ops.pose.rigify_generate()`). This produces a second armature object,
   the control rig.
5. **Weight the mesh to the generated rig's `DEF-` bones** (Voxel Heat Diffuse, or auto
   weights + cleanup). Add Corrective Smooth after the Armature modifier.
6. **Pose, then Step 5 of `SKILL.md`** — bake and export the *mesh* (not the rig). Validator
   guarantees the round trip.

## Caveats

- Generate creates a **separate** object full of control + mechanism + `DEF-` bones. Never
  export it; export only the deformed mesh.
- The generated rig assumes connected chains and the expected bone counts per type
  (`super_limb` wants a 3-segment chain plus a tip; tentacles want a connected chain). For
  genuinely branching or fused topology, fall back to `super_copy` or hand bones for those
  parts.
- Re-running Generate updates/regenerates the control rig from the metarig; keep the metarig
  as the source of truth and re-bind if you change rest-pose bones.
