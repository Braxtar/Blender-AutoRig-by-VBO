# Blender-AutoRig by VBO

A Claude **skill** for posing a ZBrush sculpt non-destructively in Blender and round-tripping
it back into ZBrush, so Transpose Master re-projects the pose onto the full high-resolution
multi-subdivision sculpt. Built for **concept work, portfolio shots, and 3D printing** —
fast, gesture-first posing, not production animation rigs.

It drives Blender through the Blender MCP connector (`mcp__Blender__*`) and is based on the
workflow taught by creature artist **Gareth Brewer** (workshop hosted by Pablo Muñoz Gómez,
ZBrushGuides).

## The one idea that makes it work

ZBrush re-imports a posed OBJ onto a subtool by matching **vertices by index** — not names,
UVs, or positions. So posing is allowed (moving a vertex doesn't change its index), but
anything that alters the mesh's identity (vertex count, connectivity, or baked coordinates)
silently corrupts the re-projection. The whole skill exists to **deform vertices and change
nothing else**:

- No Edit-Mode topology edits (no merge, delete, remesh, decimate, triangulate).
- Scale is handled with a parent **empty**, never applied to the mesh.
- Export the **lowest-subdivision** TPoseMesh; ZBrush propagates the pose up to full detail.
- A topology **fingerprint** is stamped at import and re-checked before every export; a
  validator refuses to write a corrupt OBJ.

## Choosing how to rig (decision gate)

Two questions: **what body plan**, and **will the rig be reused**. Full matrix in
`references/auto-rigging-landscape.md`.

| Body plan | With Auto-Rig Pro | Free (Rigify / hand-rig) |
|---|---|---|
| Standard humanoid | ARP Smart (AI auto-placement) | Rigify **Human** metarig → Generate |
| Standard quadruped / bird / fish | ARP quad/digitigrade IK | Rigify **bird / cat / horse / shark / wolf** metarig |
| Non-standard (multi-limb, wings, fins, fantasy, asymmetric) | ARP modular limbs (wings, spline-IK tails) | **Rigify rig-types** (`references/rigify-rig-types.md`) |
| Truly bizarre / one-and-done | hand-rig | hand-rig (`references/rigging-and-posing.md`) |

For a single baked **print** pose the rig is discarded at export, so free Rigify or hand-rig
gives the same result; paid tools (ARP) earn their place through speed and pose ergonomics on
complex creatures and reuse, not the printed output.

## Tooling

- **Blender 5.x** (developed/validated on 5.1) with the Blender MCP add-on.
- **Rigify** (bundled, free) — metarig templates and the rig-type system.
- Optional **Auto-Rig Pro** — modular creature rigging; see `references/auto-rig-pro-workflow.md`.
- Optional **Voxel Heat Diffuse Skinning** — robust auto-skinning for merged, non-watertight
  sculpt meshes where Blender's native bone-heat fails. Recommended for this pipeline.

## Layout

```
SKILL.md                              # the workflow Claude follows
references/
  round-trip-constraints.md           # the hard rules + reasons (read first)
  auto-rigging-landscape.md           # decision gate + 2026 tool matrix + round-trip safety
  rigify-rig-types.md                 # rig custom/non-human creatures with Rigify
  auto-rig-pro-workflow.md            # full ARP workflow for the round-trip
  rigging-and-posing.md               # hand-rig bones, IK/FK, weights, posing
  zbrush-side.md                      # literal instructions for the ZBrush steps
scripts/                              # run via the Blender MCP connector
  import_pose_mesh.py                 # import + topology fingerprint + scale-empty
  check_symmetry.py                   # detect asymmetry before trusting symmetrize
  trace_limb_paths.py                 # derive bone-joint coords from geometry
  assign_rigify_types.py              # turn a custom skeleton into a Rigify metarig
  export_posed_mesh.py                # bake pose → validate → export Selection-Only OBJ
  validate_roundtrip.py               # prove topology is byte-identical to import
  _fingerprint.py                     # shared vectorized fingerprint
```

## Usage

This is a skill consumed by Claude (Cowork / Claude Code) with the Blender MCP connector
attached. Point Claude at a ZBrush TPoseMesh OBJ and it follows `SKILL.md`: import → pick the
rigging approach → rig → weight → pose → export → hand back to ZBrush. Each script has a
`CONFIG` block at the top; edit the paths/values and run the file through the connector.

## Credit

Method by **Gareth Brewer**, workshop hosted by **Pablo Muñoz Gómez / ZBrushGuides**. This
skill packages that workflow for Blender 5.x and adds the round-trip safety tooling and a
2026 auto-rigging decision gate.
