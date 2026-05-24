# Rigging decision gate + 2026 auto-rigging landscape

This file answers one question: **for this particular sculpt, how should you rig it?**
It also records the state of Blender rigging tools as of 2026 (Blender 5.0/5.1, Rigify
0.6.x) so the choice is grounded, not guessed.

The rest of the skill (`SKILL.md` Steps 3–6) is identical no matter which approach you
pick — all of them end in a mesh deformed by an armature, baked at export. Only the
*building of the rig* differs.

## The decision gate

Two questions decide everything: **what is the body plan**, and **will the rig be reused**.

### Question 1 — body plan

Both **Auto-Rig Pro** (with the AI Smart engine) and free **Rigify** are installed, so both
columns are live. ARP is generally faster/more ergonomic on complex creatures; Rigify is
free and fully sufficient for a single baked print pose.

| Body plan | With Auto-Rig Pro (owned) | Free (Rigify / hand-rig) |
|---|---|---|
| Standard humanoid | **ARP Smart** — AI auto-placement from rendered viewpoints (asymmetry OK) | Rigify **Human** metarig → align → Generate |
| Standard quadruped / bird / fish | ARP 3-bone digitigrade/quad IK | Rigify **bird / cat / horse / shark / wolf** metarig → align → Generate |
| Non-standard (multi-limb, wings, fins, fantasy, asymmetric) | **ARP modular limbs** — duplicate/remove limbs, **wings** limb, **spline-IK** tentacle/tail/fin, quad IK, secondary controllers. Place manually (Smart AI is humanoid-only) | **Rigify rig-types** — compose chains, Generate (`references/rigify-rig-types.md`) |
| Truly bizarre, or one-and-done fastest | hand-rig | hand-rig (`references/rigging-and-posing.md`) |

The **non-standard** row is the common ZBrush case and the one the original skill
under-served: it always reached for hand-rigging. For complex multi-limb creatures, **ARP's
modular limbs + secondary controllers** are usually the fastest route to a good-feeling pose;
**Rigify rig-types** are the equivalent free path. Either produces a reusable rig.

*Honest note on print specifically:* the pose is baked into vertex positions and the rig
discarded at export, so for a single print pose **free Rigify (or hand-rig) gives the same
printed result** as ARP. ARP earns its place through workflow speed, pose ergonomics on
many-limbed creatures, and reuse across poses — not the print output. Use ARP where its limbs
and controllers save time; use Rigify when they don't.

**Placement is the same work either way.** A Rigify metarig still has to be snapped joint-
by-joint onto the mesh — use `scripts/trace_limb_paths.py` exactly as for a hand rig. The
tool's value is the *control layer it generates after placement*, not the placement itself.

### Question 2 — reuse

- **One-off, bake-and-export → posing-only.** The control rig is discarded at export, so
  don't over-build. This is the skill's default.
- **Reusable puppet / re-pose often / animation → animation-ready** control rig (Rigify
  Generate or ARP).

## Posing-only vs animation-ready (the distinction, and the default)

A **posing** rig is the minimum to push the model into *one* good static shape, then bake
and export it: bones, rough IK so a foot plants, maybe bendy bones for a nice arc. The
controls can be crude because you use them once.

An **animation-ready** rig is built to be driven over time, repeatedly, by an animator. It
adds the conveniences that only matter across dozens of keyframes: **IK/FK switching**
(snap a limb between modes mid-shot), **pole-vector targets**, **foot-roll**, **stretch/
squash**, a clean **control-vs-`DEF-`-bone separation**, named control widgets, and a
**pose/action library**. Rigify's *generated* rig and Auto-Rig Pro are exactly this.

**Default = posing-only.** For the ZBrush round-trip, the pose is baked into vertex
positions and exported, so the entire control layer is thrown away at export regardless of
how fancy it was. Building an animation-ready rig for a single baked frame is wasted effort.
Switch to animation-ready only when the user explicitly wants a reusable puppet they will
re-pose or animate — then the IK/FK and pose library earn their setup cost.

## Round-trip safety — which tools are allowed

The vertex-index invariant (`references/round-trip-constraints.md`) is the only thing that
matters here.

- **Safe — rig the existing mesh in place:** hand-rigging, Rigify (metarig templates *and*
  rig-types), Auto-Rig Pro, Voxel Heat Diffuse Skinning, Robust Weight Transfer,
  AccuRIG/Mixamo. Posing then baking moves vertices without changing their index.
- **NOT safe — regenerate/retopologize the mesh:** AI one-click "mesh + rig" generators
  (Tripo, Meshy, DeepMotion-style). A regenerated mesh has new vertex indices, so ZBrush's
  index-based `TPose>Mesh` re-projection is destroyed. The fingerprint validator will block
  the export, but don't burn the round trip — never send the round-trip mesh through one.
- **When using a generated rig (Rigify/ARP): weight to the `DEF-` deformation bones, and at
  export select only the mesh, never the generated rig object.**

## 2026 tool landscape (grounded notes)

**Rigify (free, bundled, v0.6.x in Blender 5.1).** Modular auto-rigging by composing rig
types. Ships Human + Animals (bird, cat, horse, shark, wolf) metarig templates, and a full
rig-type catalog for arbitrary skeletons (`references/rigify-rig-types.md`). Generates a
proper IK/FK control rig. Best free path for both standard and non-standard creatures.

**Auto-Rig Pro (owned — Full v3.78.14, module `auto_rig_pro`, Blender 2.93–5.1).** Installed
and enabled. First-class path for this skill:
- **Modular creature rigging** — duplicate/remove limbs for multi-arm bodies, a **wings**
  limb, a **spline-IK** limb for tentacles/tails/fins, 3-bone IK for quad/digitigrade legs.
  This is where ARP beats hand-rigging on complex creatures.
- **Secondary controllers** all along the limbs for fine pose-sculpting — strong for the
  dynamic gestures print/concept work wants.
- **Smart (AI) auto-placement** — humanoid bipeds only. The AI engine (v1.20) is installed at
  `C:\Users\Vincent\Documents\AutoRigPro\AI` (`inference/` + `info.dat`). For non-human
  creatures, place limbs manually (geometry-derived); Smart won't apply.
- Its game-export / retargeting / IK-FK-switching machinery is irrelevant to bake-and-print
  but harmless.
Skinning: ARP's own binding works, or bind with Voxel Heat Diffuse (compatible) — see below.
Round-trip: ARP rigs the mesh in place, so it's safe; weight to `DEF-` bones and export only
the mesh, never the generated rig.

**AccuRIG (free, Reallusion / ActorCore) and Mixamo (free, Adobe).** Fast one-click
auto-rig + auto-skin, but **humanoid bipeds only** — Reallusion states there are "no plans
to support quadruped or other types of animals." Mixamo likewise struggles with non-humanoid
anatomy. Both require a round trip out to FBX and back. For an in-Blender humanoid where the
user already owns nothing else, they're an option, but Rigify Human or ARP Smart keep
everything in Blender with less friction. **Not usable for the creature cases this skill
targets.**

**AI one-click riggers (Tripo, Meshy, DeepMotion, etc.).** Biped-template, animation output
is thin, and many regenerate the mesh — **unsafe for the round trip** (see above). Skip for
this workflow.

**Weighting add-ons.** *Voxel Heat Diffuse Skinning* (~$30) is the one paid tool actually
worth it for this pipeline — and it is current (v3.5.4, 2026-05-18, supports Blender
3.6–5.1). The TPoseMesh is all subtools *merged*: typically non-watertight, with overlaps
and gaps, which makes native bone-heat fail. VHD ray-traces the mesh into a solid voxel
statue and diffuses bone heat through the volume, producing usable weights on non-airtight,
multi-limb, asymmetric meshes in one click. It writes only vertex groups (topology intact →
round-trip safe). The package bundles *Surface Heat Diffuse* (sharper fingers/toes), a
*Corrective Smooth Baker*, and a *Joint Alignment Tool* that pushes bones to a part's volume
center (pairs with `trace_limb_paths.py`). *Robust Weight Transfer* (free, GitHub) one-clicks
weight transfer from an already-weighted body to clothes/props. Native Blender auto-weighting
is still bone-heat — no new built-in skinning algorithm in 5.x.

## Blender 5.x features worth exploiting

- **Copy Global Transform is now native** (was an add-on). Copy / paste / **paste-flipped**
  a whole pose across rigs — ideal for blocking symmetric or contrapposto variants and for
  the iterate-and-flip loop.
- **5.1 performance:** action evaluation ~+130%, shapekey evaluation up to ~+240% vs 5.0 —
  heavy posed meshes scrub and play back faster.
- **Bone visibility/selection moved onto the pose bone** (per-instance). Scripts that hide
  or select bones must use the per-bone properties, not the old shared-layer API.
- **Drivers now survive bone renames**, so Rigify generation and `symmetrize`'s `.L`→`.R`
  renaming no longer silently drop constraints/drivers.
- **Pose assets in the Asset Browser** are the current pose-library system (legacy 2.93 pose
  libraries and their conversion operators were removed in 5.0).
- New **Geometry Attribute** constraint (5.0) can drive a bone transform from a geometry
  attribute — niche, but available if a pose needs to read sampled data.
