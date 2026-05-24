# Rigging & posing in Blender (via the connector)

This is the **hand-rig path** — the "quick, dirty, good-enough" rig Gareth uses for posing,
not a production animation rig. It is one of several approaches; pick the approach first
with the decision gate in `references/auto-rigging-landscape.md`. In short: hand-rigging is
the fastest route for a single baked gesture and for genuinely bizarre topology, but for
non-human creatures you also want a reusable control rig, **Rigify rig-types**
(`references/rigify-rig-types.md`, free) or **Auto-Rig Pro** (paid) are usually the better
posing experience. The placement work below (trace joints, check symmetry) is identical
whichever approach you choose — only the control layer differs.

Run all bpy through `mcp__Blender__execute_blender_code`. When unsure of an API, use
`mcp__Blender__get_python_api_docs` / `search_api_docs`, and `get_object_detail_summary`
to read current state — **inspect before you assume** (the scene may already have bones,
named objects, or modifiers you must respect).

## Mental model: 4 relationships

- **Parent → child**: child follows parent down the chain (Forward Kinematics).
- **Master**: a bone that parents several chains (e.g. a `body` bone over hips + spine).
- **Constraint**: changes a relationship without parenting — IK, Damped Track, Stretch To.

FK = move shoulder, whole arm follows. IK = plant the foot, move the hips, foot stays.
You add an IK *control* bone to tell the rig where a chain should anchor.

## Place bones FROM THE GEOMETRY, never by eyeballed numbers (hard-won lesson)

The single biggest rigging failure on a non-human creature is guessing bone coordinates.
Tested case: a four-armed mech. Eyeballed coords put every arm bone at a flat depth and the
arms didn't line up at all — because the two arms on each side were separated in **depth
(Y), not just height (Z)**. One arm swept forward, the other angled back; a flat rig missed
both. The legs and spine (which sit near the mid-plane) looked fine, masking the problem.

So before building arm/limb bones on anything non-obvious, **derive joint positions from
the mesh**: run `scripts/trace_limb_paths.py`. It slices the mesh along the limb's spread
axis and clusters each cross-section by a second axis (depth) to separate overlapping
limbs, printing a medial polyline per limb. Read shoulder/elbow/wrist/hand coordinates off
the polylines and build bones at those exact world coords. Verify by screenshotting the
bones over the mesh in **X-ray** from front AND a 3/4 (or **top**) angle before binding —
the off-axis view is what catches depth errors a front view hides.

(This same placement step is what you do when snapping a Rigify metarig or ARP reference
bones onto the mesh — see `references/auto-rigging-landscape.md`.)

### Do NOT blindly `symmetrize` — check symmetry first (second hard-won lesson)

`armature.symmetrize` mirrors one side's bones to the other. It is a shortcut that is only
valid if the **mesh** is mirror-symmetric. ZBrush concept/print models frequently are not:
the tested mech had its arms arranged diagonally (left long arm forward, right long arm
back; the short arms at different depths too). Symmetrizing fit the traced side perfectly
and left the other side's bones floating off the limbs — looks fine head-on, obviously
wrong from the top.

Rule:
1. Run `scripts/check_symmetry.py` first. It bins vertices by distance from the mid-plane
   and compares the left vs right (y,z) centroid per band.
2. **Symmetric** → build one side, `symmetrize`, done.
3. **Asymmetric** → build **each side from its own** `trace_limb_paths.py` run
   (`SIDE_SIGN = +1` then `-1`). You may still `symmetrize` first to get the naming,
   parenting, and constraints, then **re-snap the mismatched side's bone head/tails** to
   that side's real medial coords (cheaper than rebuilding). Rebind after moving rest bones.

(In Blender 5.x, drivers now survive bone renames, so `symmetrize`'s `.L`→`.R` rename no
longer silently drops constraints/drivers — one less thing to repair afterwards.)

## Build order

1. **Rigify is already bundled and can be enabled** with
   `bpy.ops.preferences.addon_enable(module="rigify")`. Note what enabling it actually
   does: it adds the **metarig templates, the rig-type system, and the Generate Rig
   button** — it does **not** add generic "bone options" to a plain hand-built armature.
   So enabling Rigify only matters if you intend to use a metarig template or assign
   rig-types (`references/rigify-rig-types.md`). For a pure hand rig it is not needed.
2. Add the armature, enter Edit Mode. Place bones at the **geometry-derived coords** above
   (or, for simple humanoids, by eye with **X-ray on** and **snapping** — Face+Center, or
   Volume Center to sit bones inside the mesh).
3. Skeleton layout: **hips at the centre of mass** (for quadrupeds that's toward the back),
   spine up to a **head** bone (place it *above* the head — easy to grab), a **jaw**, then
   limbs. Fingers/toes: a single bone each is enough.
4. **Separate rotation** of hips / upper body / tail:
   - make a `hips` bone and a `body` (master) bone;
   - parent **legs → hips**, **spine + tail → body**, **hips → body**.
   Now rotating `body` moves everything, `hips` moves just the legs, `tail` just the tail.
5. Name only what you'll mirror or select often: `hips`, `body`, `spine.1`, `tail.1`,
   plus a `.L` suffix on left-side limb bones (batch-rename: `bpy.ops.object.
   batch_rename`, or set names directly). Then **Symmetrize** (Edit Mode, `armature.
   symmetrize`) to mirror bones + constraints + parenting to `.R`.

### Snippet: armature + a couple of bones

```python
import bpy
from mathutils import Vector

# inspect first
print([o.name for o in bpy.data.objects])

bpy.ops.object.armature_add(enter_editmode=True, location=(0,0,0))
arm = bpy.context.object
arm.name = "creature_rig"
arm.show_in_front = True            # X-ray-like visibility for bones
eb = arm.data.edit_bones
eb.remove(eb[0])                    # drop the default bone

def bone(name, head, tail, parent=None, connected=False):
    b = eb.new(name)
    b.head, b.tail = Vector(head), Vector(tail)
    if parent: b.parent = eb[parent]; b.use_connect = connected
    return b

bone("body",   (0,0,1.0), (0,0,1.3))            # master
bone("hips",   (0,0,1.0), (0,-0.3,1.0), "body")
bone("spine.1",(0,0,1.0), (0,0.4,1.1),  "body")
# ... extrude/subdivide more as needed
bpy.ops.object.mode_set(mode='OBJECT')
```

## Constraints

- **IK** on a limb: extrude a control bone off the foot/hand (`E` then lock an axis),
  **clear its parent** (`ALT+P` keep-offset / `parent_clear`), then select control +
  last chain bone and `CTRL+SHIFT+C → Inverse Kinematics`. Set **chain length** to the
  number of joints (e.g. 3). Parent the foot bone to the IK control so it tracks.
- **Damped Track**: locks a bone in place but aims it at a target — great for merging a
  toe/fin cluster onto one controller, or anchoring a cape edge.
- **Stretch To**: stretchy, volume-preserving — cartoony limbs, long ears, cape drape.
  Use sparingly (it changes volume).

(If you want IK/FK *switching*, pole targets, foot roll and the like rather than hand-wired
single-mode IK, that is the moment to use Rigify rig-types or ARP instead — see the gate.)

### Snippet: add an IK constraint via code

```python
import bpy
bpy.ops.object.mode_set(mode='POSE')
pb   = bpy.context.object.pose.bones["shin.L"]
ik   = pb.constraints.new('IK')
ik.target     = bpy.context.object
ik.subtarget  = "ik_foot.L"     # the control bone
ik.chain_count = 3
bpy.ops.object.mode_set(mode='OBJECT')
```

## Weights

- **Voxel Heat Diffuse Skinning** add-on (recommended; ~$30): select mesh, then armature,
  Bind at resolution ~412 (128 for a fast preview). Handles asymmetry, many limbs, clothes.
- Or Blender auto weights: select mesh, shift-select armature, `bpy.ops.object.parent_set(
  type='ARMATURE_AUTO')`. For transferring weights to clothing/props from an already-
  weighted body, the free **Robust Weight Transfer** add-on is a one-click option.
- **If you generated a Rigify/ARP control rig, bind to the `DEF-` deformation bones**, not
  the control bones.
- **Corrective Smooth** modifier *after* the Armature modifier in the stack — preserves
  volume across joints (delta-mush-like). Tune factor/iterations lightly.
- Clean-up is usually only armpits/shoulders/forearms. To zero weights on a region
  cleanly, hide the rest with a vertex mask: select the loop, `CTRL+ +` to grow, enter
  Weight Paint, enable the mask, `CTRL+I` to invert, paint weight 0. (Blender 5.1 adds loop
  selection in Weight Paint with Vertex Selection — handy here.)
- **Hard surface / stiff clothing**: don't paint — parent the whole object to one bone
  (`bone parent`). **Tight clothing**: Data Transfer modifier from the body.
  **Saddle/props**: own bone parented to the back; the prop object parented to that bone;
  nudge with sculpt tools, finalize in ZBrush.

## Posing

- Pose Mode. `G`/`R`; lock unwanted rotation axes in the Item panel for clean single-axis
  rotation. Aim for **contrapposto** (weight on one leg) — instant asymmetry and life.
- **Bendy bones**: raise a bone's segment count (e.g. 4) for smooth arcing limbs/spine.
  Safe here (not a game engine); the curve is baked at export by "Visual Geometry to Mesh."
- **Copy Global Transform** is native in Blender 5.x: copy a pose, paste it, or
  **paste-flipped** onto the mirror bones — quicker than the manual copy/paste-flip dance.
- **Save poses**: insert a keyframe (`I`), switch the timeline editor to **Action Editor**,
  name the action (e.g. `contrapposto`), and **Stash** it — or save it as a **pose asset**
  in the Asset Browser. Flip a pose: select bones, `CTRL+C`, `CTRL+V`, then **Flip** in the
  operator panel.
- Micro-adjust fingers/cape with the **Pose brush** in Sculpt Mode (Dyntopo/Remesh OFF!)
  rather than over-rigging.
- Reference: search wildlife / wildlife-action photography for believable creature poses.

## After posing

Go to `SKILL.md` Step 5 and run `scripts/export_posed_mesh.py`. Do **not** apply scale,
merge, or remesh as a "cleanup" — the export script handles transforms correctly and the
validator will block a corrupt export. If you used a generated rig, export the *mesh*, not
the generated rig object.
