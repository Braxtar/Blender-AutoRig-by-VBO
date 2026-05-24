# ZBrush-side steps (instructions for the user)

These run in ZBrush, before and after the Blender work. Relay them literally — the
round-trip depends on them being done exactly. (If a `mcp__zbrush__*` connector is
available and the user wants automation, these map to Transpose Master + Tool > Import/
Export, but most users do them by hand.)

## Before sending to Blender (export)

1. **Finish the sculpt and topology.** All subdivision levels present; retopo done
   (ZRemesher with PolyGroups on, TopoGun, or hand). The pose will be locked to this exact
   topology, so it must be final-ish. (Re-sculpting later is fine **only if topology stays
   identical** — then the Blender rig/weights/poses are reusable.)
2. **Add a recording layer to every subtool** (`Tool > Layers > New Layer`). This keeps the
   pose reversible/adjustable in ZBrush. (Optional if you'll tick Transpose Master's
   "Layer" box on the way back — see step 6.)
3. **Drop every subtool to its LOWEST subdivision level** (SDiv 1). Posing the lowest level
   is what lets ZBrush propagate the deformation up to the high-res detail.
4. **Run Transpose Master → `TPose>SubT` ("T")**. It merges all subtools into one low-res
   `TPoseMesh`.
5. **Export the TPoseMesh as OBJ** (`Tool > Export`, e.g. `pose_mesh.obj`). Note the path —
   you'll give it to Blender. You can re-create the TPoseMesh later; it's deterministic.

## After Blender (import the posed OBJ back)

6. Make sure **Transpose Master's "Layer" checkbox is ON** if you want it to auto-create
   pose layers on each subtool.
7. Select the **`TPoseMesh` subtool** (the merged low-res mesh from step 4 — still in the
   scene). `Tool > Import` and choose the posed OBJ Blender exported.
   - The vertex/polygon count must match exactly. If ZBrush complains about a mismatch,
     the Blender side violated a constraint — re-run `validate_roundtrip.py` and fix
     before retrying. **Do not force it.**
8. Press **Transpose Master → `TPose>Mesh` ("M")**. ZBrush takes the low-res pose and
   propagates it onto the full multi-subdivision sculpt, distributing back to every
   original subtool. Your high-res detail is now posed.

## Notes

- Scale: Blender and ZBrush disagree on units. The Blender workflow keeps the mesh data at
  ZBrush's scale (it only scales a helper empty), so the OBJ returns at the size ZBrush
  expects. You should not need to rescale on import.
- For portfolio/render: after posing, you can bring the posed mesh back into Blender, reuse
  the same rig, and apply your displacement/normal maps to render in Cycles (free) instead
  of KeyShot.
- For 3D printing: pose first, then worry about watertightness, slicing, and the base —
  those are post-design steps.
