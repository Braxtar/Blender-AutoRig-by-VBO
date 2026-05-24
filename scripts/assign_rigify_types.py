# assign_rigify_types.py
# -----------------------------------------------------------------------------
# Turn a hand-built / custom armature into a generate-able Rigify METARIG by
# assigning a `rigify_type` (and optional parameters) to the first bone of each
# chain, then optionally pressing Generate.
#
# WHY THIS EXISTS
# ---------------
# Rigify's "Generate Rig" button is greyed out unless the active armature is a
# metarig. Rigify's own test (rigify.ui.is_metarig) returns True only if at least
# one pose bone has a non-empty `rigify_type`. A plain hand-built armature has none,
# so Generate stays disabled. Assigning even one rig type lights up the panel.
#
# See references/rigify-rig-types.md for the rig-type catalogue and the per-chain
# mapping (super_limb for arms/legs, simple_/spline_tentacle for tails/wings/fins,
# basic_spine / super_head for torso/head, super_copy for single bones, etc.).
#
# Run the whole file through mcp__Blender__execute_blender_code after editing CONFIG.
# Assign a JSON-serialisable dict to `result` (this script does).
# -----------------------------------------------------------------------------

import bpy

# ============================ CONFIG =========================================
# Armature to operate on. None = use the active object.
ARMATURE_NAME = None

# Map: first-bone-of-chain -> {"type": "<rigify_type>", "params": {<name>: <value>}}
# The bone name must be the FIRST (root) bone of a connected chain. Params are
# optional and depend on the rig type (see references/rigify-rig-types.md).
ASSIGNMENTS = {
    # --- examples; replace with your skeleton ---
    # "spine.1":      {"type": "spines.basic_spine"},
    # "head":         {"type": "spines.super_head"},
    # "upper_arm.L":  {"type": "limbs.super_limb", "params": {"limb_type": "arm"}},
    # "upper_arm.R":  {"type": "limbs.super_limb", "params": {"limb_type": "arm"}},
    # "thigh.L":      {"type": "limbs.super_limb", "params": {"limb_type": "leg"}},
    # "thigh.R":      {"type": "limbs.super_limb", "params": {"limb_type": "leg"}},
    # "tail.1":       {"type": "limbs.simple_tentacle"},
    # "wing.L":       {"type": "limbs.spline_tentacle"},
    # "jaw":          {"type": "basic.super_copy"},
    # "finger1.L":    {"type": "basic.super_finger"},
}

# Press Generate after assigning? Leave False first to eyeball the metarig, then
# re-run with True (or call bpy.ops.pose.rigify_generate() yourself).
GENERATE = False
# =============================================================================


def _get_armature():
    if ARMATURE_NAME:
        ob = bpy.data.objects.get(ARMATURE_NAME)
        if ob is None:
            raise RuntimeError("No object named %r" % ARMATURE_NAME)
    else:
        ob = bpy.context.active_object
        if ob is None:
            raise RuntimeError("No active object; set ARMATURE_NAME in CONFIG.")
    if ob.type != "ARMATURE":
        raise RuntimeError("%r is not an armature (type=%s)." % (ob.name, ob.type))
    return ob


def main():
    info = {"assigned": [], "skipped": [], "warnings": []}

    if "rigify" not in bpy.context.preferences.addons:
        try:
            bpy.ops.preferences.addon_enable(module="rigify")
            info["warnings"].append("Enabled the Rigify add-on.")
        except Exception as e:
            raise RuntimeError("Rigify add-on is not enabled and could not be "
                               "enabled: %s" % e)

    ob = _get_armature()

    # Guard: a generated rig carries rig_id on its data and is NOT a metarig.
    if "rig_id" in ob.data:
        info["warnings"].append(
            "This armature has 'rig_id' on its data — it is a GENERATED rig, not a "
            "metarig. Assign types to the METARIG, not the generated rig.")

    # Make it active and enter Pose mode (rigify_type lives on pose bones).
    bpy.context.view_layer.objects.active = ob
    ob.select_set(True)
    if ob.mode != "POSE":
        bpy.ops.object.mode_set(mode="POSE")

    valid_types = None
    try:
        from rigify import rig_lists
        valid_types = set(rig_lists.rigs.keys())
    except Exception:
        pass  # validation is best-effort

    for bone_name, spec in ASSIGNMENTS.items():
        pb = ob.pose.bones.get(bone_name)
        if pb is None:
            info["skipped"].append({"bone": bone_name, "reason": "bone not found"})
            continue
        rtype = spec.get("type", "")
        if valid_types is not None and rtype not in valid_types:
            info["skipped"].append({"bone": bone_name,
                                    "reason": "unknown rig type %r" % rtype})
            continue
        pb.rigify_type = rtype
        applied = {}
        for pname, pval in (spec.get("params") or {}).items():
            try:
                setattr(pb.rigify_parameters, pname, pval)
                applied[pname] = pval
            except Exception as e:
                info["warnings"].append(
                    "param %s on %s failed: %s" % (pname, bone_name, e))
        info["assigned"].append({"bone": bone_name, "type": rtype, "params": applied})

    # Report metarig status (mirrors rigify.ui.is_metarig).
    is_metarig = ("rig_id" not in ob.data) and any(
        b.rigify_type != "" for b in ob.pose.bones)
    info["is_metarig_now"] = is_metarig
    info["generate_button_enabled"] = is_metarig

    if GENERATE:
        if not is_metarig:
            info["warnings"].append("GENERATE requested but armature is not a metarig; "
                                    "skipped.")
        else:
            try:
                bpy.ops.pose.rigify_generate()
                info["generated"] = True
            except Exception as e:
                info["generated"] = False
                info["warnings"].append("rigify_generate failed: %s" % e)

    info["armature"] = ob.name
    return info


try:
    result = main()
except Exception as e:
    result = {"error": str(e)}
