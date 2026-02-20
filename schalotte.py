from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from bpy.types import (
        Collection,
        CompositorNodeTree,
        Context,
        Material,
        Object,
        Scene,
        SoundStrip,
        World,
    )


import colorsys
import random
import re
from pathlib import Path

import bpy

from . import client, logger, preferences, session, utils

log = logger.get_logger(__name__)


ASSET_TYPE_MAP = {
    "Character": "02_01_01_characters",
    "Environment": "02_01_02_environments",
    "Set Prop": "02_01_03_environmental_props",
    "Hero Prop": "02_01_04_hero_props",
}

SHOT_TASK_NAME_MAP = {
    "Storyboard": "02_02_storyboard",
    "Layout": "02_03_layout_scene_prep",
    "Anim Blocking": "02_04_animation/02_03_02_episodes",
    "Anim Splining": "02_04_animation/02_03_02_episodes",
    "Anim Polishing": "02_04_animation/02_03_02_episodes",
    "Lighting": "02_05_lighting",
    "FX": "02_06_VFX",
}

COLLECTIONS_MAP = {
    "Character": "#CH",
    "Environment": "#SET",
    "Set Prop": "#SET",
    "Hero Prop": "#PROP",
}

STB_SETUP_FILE_REL = Path(
    "02_02_storyboard",
    "SCH_stb_setup_Blendfile",
    "SCH_s01_e0x_sq0x_STB_setup.blend",
)

ASSET_LIBRARIES = [
    {
        "name": "Animation Library",
        "path": "02_04_animation/02_03_01_animation_library",
        "import_method": "APPEND_REUSE",
        "use_relative_path": True,
    },
    {
        "name": "Storyboard Toolbox",
        "path": "02_02_storyboard/storyboard_toolbox",
        "import_method": "APPEND_REUSE",
        "use_relative_path": True,
    },
]


def find_project_root(
    root_name: str = "02_production",
    use_prefs: bool = True,
) -> Path | None:
    """
    Find the project root path from the current file path.
    Optionally check preferences first and store if it doesn't exist yet.

    Args:
        root_name (str): Name of the root folder in the project structure
        use_prefs (bool): Check and store preferences

    Returns:
        Path | None
    """
    prefs = preferences.Preferences.this()
    if use_prefs and prefs.project_root:
        base_path = Path(prefs.project_root)
    else:
        base_path = Path(bpy.data.filepath)
    if not base_path:
        log.error("Could not determine a base path to find the project root")
        return
    root_path = base_path
    for _ in range(8):
        if root_path.name == root_name:
            break
        root_path = root_path.parent
    else:
        log.error(f"Root name not found in {base_path}.")
        return

    if use_prefs and not prefs.project_root:
        log.info(f"Updating project root to: {root_path}")
        prefs.project_root = root_path.as_posix()
        bpy.ops.wm.save_userpref()

    return root_path


def find_asset_blend(asset_name: str, asset_type_name: str) -> Path | None:
    """
    Find the blend file path of an asset.

    Args:
        asset_name (str): Name of the asset
        asset_type_name (str): Type of the asset

    Returns:
        Path | None: Blend file path of the asset, or None if not found
    """
    root_path = find_project_root()
    if not root_path:
        log.debug("Root path not found.")
        return

    # Check assets dir
    assets_dir = root_path / "02_01_assets" / ASSET_TYPE_MAP[asset_type_name]
    if not assets_dir.is_dir():
        log.debug(f"Assets dir not found {assets_dir}")
        return

    # Generate asset prefix
    asset_prefix = asset_name.split("_")[0]
    if not asset_prefix:
        log.debug(f"Could not determine prefix for {asset_name}")
        return

    # Find the asset dir based on prefix
    for asset_dir in assets_dir.iterdir():
        if asset_prefix in asset_dir.name:
            break
    else:
        log.debug(f"Asset dir not found for {asset_name}")
        return

    # Get all .blend files and pick the first one, sorted in lowercase
    blend_files = sorted(
        [f for f in asset_dir.glob("*.blend") if not f.name.startswith(".")],
        key=lambda f: f.stem.lower(),
    )
    if not blend_files:
        log.debug(f"Asset file not found for {asset_name}")
        return
    asset_path = blend_files[0]
    log.debug(f"Found {asset_name} at {asset_path.as_posix()}")
    return asset_path


def find_asset_type_collection(asset_type_name: str) -> Collection | None:
    """
    Find the collection for the given asset type, if it exists.

    Args:
        asset_type_name (str): The name of the asset type to find

    Returns:
        Collection | None: The collection for the asset type, or None if not found
    """
    target_name = COLLECTIONS_MAP[asset_type_name]
    return bpy.data.collections.get(target_name)


def ensure_camera_rig(
    scene: Scene | None = None,
    force_append: bool = False,
) -> tuple[Collection | None, Object | None, Object | None]:
    """
    Append the camera collection if it doesn't exist yet.

    Args:
        scene (Scene | None): Scene to be set up, defaults to context scene
        force_append (bool): Append a new camera even if it already exists

    Returns:
        tuple[Collection | None, Object | None, Object | None]:
        Camera rig collection, armature object and camera object, if successful
    """
    col_name = "cam.001"
    col_cam = None

    expected_name = "cam_sh0010"
    s = session.Session.this()
    if s.sequence:
        sequence_name = s.sequence.get("name")
        if sequence_name:
            expected_name = f"cam_{sequence_name}_sh0010"

    # Try to find an existing camera collection
    if not force_append:
        for name in (
            col_name,
            expected_name,
        ):
            col_cam = bpy.data.collections.get(name)
            if col_cam:
                break

    # Append the camera collection
    if not col_cam:
        # Find the setup file
        root_path = find_project_root()
        if not root_path:
            log.error("Could not find production directory")
            return (None, None, None)
        setup_file = root_path / STB_SETUP_FILE_REL
        if not setup_file.is_file():
            log.error(f"File not found: {setup_file}")
            return (None, None, None)

        # Append
        log.debug(f"Appending: {setup_file}")
        col_cam = utils.append_collection(setup_file, col_name)
        if not col_cam:
            log.error(f"Failed to append camera collection: {col_name}")
            return (None, None, None)
        col_cam.color_tag = "COLOR_08"

    # Add to #CAM collection
    parent_name = "#CAM"
    col_parent = bpy.data.collections.get(parent_name)
    if not col_parent:
        col_parent = bpy.data.collections.new(parent_name)
        col_parent.color_tag = "COLOR_08"

    # Add camera collection to #CAM
    if col_cam not in set(col_parent.children):
        col_parent.children.link(col_cam)

    # Ensure #CAM collection is in scene
    if not scene:
        scene = bpy.context.scene
    if col_parent not in set(scene.collection.children):
        scene.collection.children.link(col_parent)

    # Find objects
    obj_cam = None
    obj_rig = None
    for obj in col_cam.all_objects:
        if obj.type == "CAMERA":
            obj_cam = obj
        elif obj.type == "ARMATURE":
            obj_rig = obj
        if obj_cam and obj_rig:
            break

    return (col_cam, obj_rig, obj_cam)


def ensure_storyboard_material(name: str = "SCH_stb_shad_ao_085") -> Material:
    """
    Create the default storyboard material, if it doesn't exist yet.

    Args:
        name (str): The name for the material to create

    Returns:
        Material
    """
    material = bpy.data.materials.get(name)
    if material:
        return material

    log.debug("Creating storyboard material.")
    material = bpy.data.materials.new(name)
    material.use_fake_user = True
    material.use_nodes = True
    node_tree = material.node_tree
    nodes = node_tree.nodes

    nodes.clear()
    ao = nodes.new("ShaderNodeAmbientOcclusion")
    ao.location = (-420, 510)
    ao.inputs["Distance"].default_value = 0.8  # type: ignore

    mix = nodes.new("ShaderNodeMix")
    mix.data_type = "RGBA"  # type: ignore
    mix.inputs["A"].default_value = (0, 0, 0, 1)  # type: ignore
    mix.inputs["B"].default_value = (0.85, 0.85, 0.85, 1)  # type: ignore
    mix.location = (-230, 510)

    diff = nodes.new("ShaderNodeBsdfDiffuse")
    diff.location = (-40, 510)

    out = nodes.new("ShaderNodeOutputMaterial")
    out.location = (150, 510)

    node_tree.links.new(out.inputs["Surface"], diff.outputs["BSDF"])
    node_tree.links.new(diff.inputs["Color"], mix.outputs["Result"])
    node_tree.links.new(mix.inputs["Factor"], ao.outputs["AO"])

    return material


def ensure_storyboard_world() -> World | None:
    """
    Append the storyboard world and set it to given scene, if it doesn't exist yet.

    Returns:
        World | None
    """
    world_name = "SCH_stb_world"
    world = bpy.data.worlds.get(world_name)
    if not world:
        # Find the setup file
        root_path = find_project_root()
        if not root_path:
            log.error("Could not find production directory")
            return
        setup_file = root_path / STB_SETUP_FILE_REL
        if not setup_file.is_file():
            log.error(f"File not found: {setup_file}")
            return

        # Append the world
        log.debug(f"Appending: {setup_file}")
        with bpy.context.temp_override(  # type: ignore
            window=bpy.data.window_managers[0].windows[0],
        ):
            bpy.ops.wm.append(
                directory=setup_file.parent.as_posix(),
                filename=f"{setup_file.name}/World/{world_name}",
                link=False,
                do_reuse_local_id=False,
                autoselect=False,
                active_collection=False,
                instance_collections=False,
                instance_object_data=True,
                set_fake=True,
                use_recursive=True,
            )
            world = bpy.data.worlds.get(world_name)
        if not world:
            log.error(f"Failed to import world from {setup_file}")
            return

    return world


def ensure_storyboard_compositing(scene: Scene | None = None):
    """
    Set up compositing nodes in the given scene.

    Args:
        scene (Scene | None): Scene to be set up, defaults to context scene
    """
    if not scene:
        scene = bpy.context.scene

    scene.use_nodes = True
    node_tree: CompositorNodeTree = scene.node_tree  # type: ignore
    nodes = node_tree.nodes
    # Remove all nodes from the scene's node tree.
    nodes.clear()

    rlay = nodes.new("CompositorNodeRLayers")
    rlay.location = (-320, 510)

    hsv = nodes.new("CompositorNodeHueSat")
    hsv.inputs["Saturation"].default_value = 0  # type: ignore
    hsv.location = (0, 510)

    viewer = nodes.new("CompositorNodeViewer")
    viewer.location = (220, 560)

    comp = nodes.new("CompositorNodeComposite")
    comp.location = (220, 460)

    node_tree.links.new(comp.inputs["Image"], hsv.outputs["Image"])
    node_tree.links.new(viewer.inputs["Image"], hsv.outputs["Image"])
    node_tree.links.new(hsv.inputs["Image"], rlay.outputs["Image"])


def generate_shot_blend_path(task_id: str, use_short_sq: bool = False) -> Path | None:
    """
    Generate the expected file path for given task ID.

    Args:
        task_id (str): Task ID
        use_full_sq (bool): Use the short sequence name, removing all but sq + number

    Returns:
        Path | None: Path object for the expected file path, if successful
    """
    # Project root
    project_root = find_project_root()
    if not project_root:
        log.error(f"Could not find project root for {task_id}.")
        return

    # Task dict
    task = client.STORE.get(task_id)
    if not task:
        log.error(f"Task {task_id} has not been fetched yet.")
        return

    # Task type name
    task_name = task.get("task_type_name")
    if not task_name:
        log.error(f"Task {task_id} has no task type name.")
        return

    # Task dir name
    task_dir_name = SHOT_TASK_NAME_MAP.get(task_name)
    if not task_dir_name:
        log.error(f"Can not find directory for {task_name} type tasks.")
        return

    # Shot
    shot_id = task.get("entity_id", "")
    shot = client.STORE.get(shot_id)
    if not shot:
        log.error(f"Shot {shot_id} has not been fetched yet.")
        return

    # Sequence
    sequence_id = shot.get("parent_id", "")
    sequence = client.STORE.get(sequence_id)
    if not sequence:
        log.error(f"Sequence {sequence_id} has not been fetched yet.")
        return

    # Sequence name
    sq_name: str = sequence.get("name", "")
    if not sq_name:
        log.error(f"Sequence {sequence_id} has no name.")
        return

    # Episode
    eqisode_id = sequence.get("parent_id", "")
    episode = client.STORE.get(eqisode_id)
    if not episode:
        log.error(f"Episode {eqisode_id} has not been fetched yet.")
        return

    # Episode name
    ep_name = episode.get("name")
    if not ep_name:
        log.error(f"Episode {eqisode_id} has no name.")
        return

    # File name
    ep_short = f"e{ep_name[-2:]}"
    sq_match = re.match(r"sq(\d)(\d{2})(\d)", sq_name)
    if sq_match:
        # Remove descriptions after number
        if use_short_sq:
            sq_name = sq_match.group()
        # Reduce for file name
        groups = sq_match.groups()
        sq_short = "sq"
        if groups[0] != "0":
            sq_short += groups[0]
        sq_short += groups[1]
        if groups[2] != "0":
            sq_short += groups[2]
    else:
        # Remove descriptions after number (any padding)
        sq_match = re.match(r"sq(\d+)", sq_name)
        if sq_match:
            sq_short = sq_match.group()
            if use_short_sq:
                sq_name = sq_match.group()
        else:
            sq_short = sq_name
    tt_file = "" if task_name == "Storyboard" else f"_{task_name.split(' ')[0]}"
    file_name = f"SCH{tt_file}_s01_{ep_short}_{sq_short}.blend"

    # Build path
    return project_root / task_dir_name / "s01" / ep_name / sq_name / file_name


def generate_sound_path(sequence_id: str) -> Path | None:
    """
    Generate the expected sound path for given sequence and return if it exists.
    Fall back to episode.

    Args:
        sequence_id (str): Sequence ID

    Returns:
        Path | None: Path object for the expected sound path, if successful
    """
    # Project root
    project_root = find_project_root()
    if not project_root:
        log.error(f"Could not find project root for {sequence_id}.")
        return

    sequence = client.STORE.get(sequence_id)
    if not sequence:
        log.error(f"Sequence {sequence_id} has not been fetched yet.")
        return

    # Sequence name
    sq_name = sequence.get("name")
    if not sq_name:
        log.error(f"Sequence {sequence_id} has no name.")
        return

    # Episode
    eqisode_id = sequence.get("parent_id", "")
    episode = client.STORE.get(eqisode_id)
    if not episode:
        log.error(f"Episode {eqisode_id} has not been fetched yet.")
        return

    # Episode name
    ep_name = episode.get("name")
    if not ep_name:
        log.error(f"Episode {eqisode_id} has no name.")
        return

    # Build path
    ep_path = Path(project_root, "02_08_sound", "s01", ep_name)
    sq_path = Path(ep_path, sq_name)

    if sq_path.exists():
        log.debug(f"Sequence sound path: {sq_path}")
        return sq_path

    elif ep_path.exists():
        log.debug(f"Episode sound path: {ep_path}")
        return ep_path

    log.debug(f"Path does not exist: {sq_path}")


def setup_storyboard(scene: Scene | None = None):
    """
    Set up given scene for Schalotte storyboarding tasks.

    Args:
        scene (Scene | None): Scene to be set up, defaults to context scene
    """
    if not scene:
        scene = bpy.context.scene

    # Frame dropping & audio
    scene.sync_mode = "FRAME_DROP"
    scene.use_audio = True
    scene.use_audio_scrub = True

    # Format
    render = scene.render
    render.resolution_x = 1920
    render.resolution_y = 1080
    render.resolution_percentage = 100
    render.pixel_aspect_x = 1.0
    render.pixel_aspect_y = 1.0
    render.use_border = False
    render.use_crop_to_border = False
    render.fps = 25

    # Simplify
    render.use_simplify = True
    render.simplify_subdivision = 0
    render.simplify_subdivision_render = 6

    # Compositing
    render.engine = "BLENDER_EEVEE_NEXT"  # type: ignore
    render.use_single_layer = False
    render.use_compositing = True
    ensure_storyboard_compositing(scene)

    # Viewports
    for window in bpy.context.window_manager.windows:
        for area in window.screen.areas:
            if area.type != "VIEW_3D":
                continue
            for space in area.spaces:
                if hasattr(space, "shading"):
                    space.shading.use_compositor = "ALWAYS"  # type: ignore

    # Collections
    scene_collections = set(scene.collection.children)
    for col_name, color in {
        "#LIGHT": "COLOR_07",
        "#SET": "COLOR_03",
        "#FX": "COLOR_05",
        "#PROP": "COLOR_01",
        "#CH": "COLOR_04",
        "#CAM": "COLOR_08",
    }.items():
        col = bpy.data.collections.get(col_name)
        if not col:
            log.debug(f"Creating collection {col_name}.")
            col = bpy.data.collections.new(col_name)
        if col not in scene_collections:
            log.debug(f"Linking {col_name} to scene collection")
            scene.collection.children.link(col)
        col.color_tag = color  # type: ignore

    # Get all character and FX objects to exclude from re-shading
    char_col = bpy.data.collections.get("#CH")
    if char_col:
        char_objs = set(char_col.all_objects)
    else:
        char_objs = set()
        log.warning("Could not find #CH collection")

    fx_col = bpy.data.collections.get("#FX")
    if fx_col:
        fx_objs = set(fx_col.all_objects)
    else:
        fx_objs = set()
        log.warning("Could not find #FX collection")

    # Shader
    material = ensure_storyboard_material()
    for obj in scene.objects:
        # Skip characters and FX
        if obj in char_objs or obj in fx_objs:
            continue
        # Skip linked and overrides
        if obj.library or obj.override_library:
            continue
        # Skip widgets
        if obj.name.lower().startswith("wgt"):
            continue
        # Only shadable objects
        if obj.type in {"CURVE", "MESH", "SURFACE", "META", "FONT"}:
            # Create a slot if none are present
            if not obj.material_slots:
                with bpy.context.temp_override(object=obj):  # type: ignore
                    try:
                        bpy.ops.object.material_slot_add()
                    except RuntimeError:
                        log.warning(f"Could not add material slot for {obj.name}")
                        continue
            # Set material on all slots
            for i, slot in enumerate(obj.material_slots):
                if slot.link == "DATA" and (
                    obj.data.library or obj.data.override_library
                ):
                    continue
                if slot.material is not material:
                    log.debug(f"Assigning storyboard material to {obj.name} [{i}].")
                    slot.material = material

    # Camera
    # ensure_camera_rig(scene, False)

    # World
    scene.world = ensure_storyboard_world()


def setup_storyliner(scene: Scene | None = None):
    """
    Set up storyliner settings for the given Blender scene.
    """
    if not scene:
        scene = bpy.context.scene

    # Find storyliner addon in case it's installed from a repo
    for addon in bpy.context.preferences.addons:
        if "storyliner" in addon.module:
            module = addon.module
            break
    else:
        module = "storyliner"

    storyliner_addon = bpy.context.preferences.addons.get(module)
    if storyliner_addon:
        prefs = storyliner_addon.preferences
        prefs.naming_shot_format = "sh####"  # type: ignore
        prefs.camNamePrefix = "cam_"  # type: ignore
        bpy.ops.wm.save_userpref()
    else:
        log.warning("Could not find Storyliner add-on preferences.")

    scene_props = scene.WkStoryLiner_props  # type: ignore
    scene_props.use_project_settings = False

    # Sequence
    s = session.Session.this()
    prefix = "STB"
    if s.episode:
        episode_name = s.episode.get("name")
        if episode_name:
            prefix += f"_{episode_name}"
    scene_props.render_sequence_prefix = f"{prefix}_"

    if s.sequence:
        sequence_name = s.sequence.get("name", "sq")
        scene_props.sequence_name = sequence_name
        cam_name = f"cam_{sequence_name}_sh0010"
        # scene.name = sequence_name
    else:
        cam_name = "cam_sh0010"
    scene_props.naming_shot_format = "sh####"

    # Stamp info
    stamp = scene.WKSL_StampInfo_Settings  # type: ignore
    stamp.stampInfoRenderMode = "OVER"
    stamp.stampRenderResOver_percentage = 86.0
    stamp.projectNameUsed = True

    # Project
    if s.project:
        stamp.projectName = s.project.get("name", "").upper()

    # Logo
    project_root = find_project_root()
    stamp.logoUsed = False
    if project_root:
        logo_path = (
            project_root
            / "02_02_storyboard"
            / "SCH_stb_setup_Blendfile"
            / "SCH_stb_setup_material"
            / "schalotte_schriftzug_weiss.png"
        )
    else:
        logo_path = None
        log.warning("Could not find project root for logo setup.")
    if logo_path and logo_path.is_file():
        stamp.logoUsed = True
        stamp.logoMode = "CUSTOM"
        stamp.logoFilepath = bpy.path.relpath(logo_path.as_posix())
        stamp.logoScaleH = 0.06
        stamp.logoPosNormX = 0.012
        stamp.logoPosNormY = 0.01
        stamp.projectNameUsed = False

    else:
        # Fall back to project title
        log.warning(f"Project logo does not exist: {logo_path}")
        stamp.projectNameUsed = True

    # Metadata
    stamp.sceneUsed = False
    stamp.sequenceUsed = False
    stamp.takeUsed = False
    stamp.shotUsed = True
    stamp.cameraUsed = False
    stamp.cameraLensUsed = True
    stamp.videoFrameUsed = True
    stamp.dateUsed = False
    stamp.timeUsed = False
    stamp.notesUsed = False
    stamp.cornerNoteUsed = False

    # User
    user = client.Client.this().user
    if user:
        stamp.bottomNoteUsed = True
        name = user.get("full_name")
        if not name:
            name = user.get("email")
        stamp.bottomNote = name
    else:
        stamp.bottomNoteUsed = False

    # File
    stamp.filenameUsed = False
    stamp.filepathUsed = False

    # Text
    stamp.textColor = (1, 1, 1, 1)
    stamp.automaticTextSize = True
    stamp.fontScaleHNorm = 0.02
    stamp.interlineHNorm = 0.015
    stamp.extPaddingNorm = 0.015
    stamp.extPaddingHorizNorm = 0.02
    stamp.stampPropertyLabel = True

    # Initialize
    bpy.ops.wksl_stamp_info.initialize()  # type: ignore

    # Rename take
    if bpy.data.filepath:
        for take in scene_props.takes:
            if take.name == "Main Edit":
                take.name = Path(bpy.data.filepath).stem

    # Create first shot
    if not scene_props.getShotsList():
        col, _, cam = ensure_camera_rig(scene, False)
        if not cam:
            return
        scene_props.addShot(  # type: ignore
            name="sh0010",
            start=1,
            end=51,
            camera=cam,
            color=colorsys.hsv_to_rgb(random.random(), 0.9, 1.0) + (1.0,),
        )
        rename_cam_rig(cam, cam_name, col)


def rename_cam_rig(
    camera_obj: Object,
    name: str,
    collection: Collection | None = None,
):
    """
    Rename a camera, its collection, rig object, data and actions.

    Args:
       camera_obj (Object): The camera object to rename.
       name (str): The new name for the camera.
       collection (Collection | None): The rig collection, will be searched if None
    """
    camera_obj.name = name

    # Data and actions
    if camera_obj.animation_data and camera_obj.animation_data.action:
        camera_obj.animation_data.action.name = f"{name}_Action"
    camera_obj.data.name = f"{name}_Data"
    if camera_obj.data.animation_data and camera_obj.data.animation_data.action:
        camera_obj.data.animation_data.action.name = f"{name}_Data_Action"

    # Rig, data and actions
    rig = camera_obj.parent
    if rig:
        rig.name = f"{name}_Rig"
        if rig.animation_data and rig.animation_data.action:
            rig.animation_data.action.name = f"{name}_Rig_Action"
        if rig.data:
            rig.data.name = f"{name}_Rig_Data"
            if rig.data.animation_data and rig.data.animation_data.action:
                rig.data.animation_data.action.name = f"{name}_Rig_Data_Action"

    # Collection
    if collection:
        collection.name = name
        return

    for col in bpy.data.collections:
        if camera_obj in set(col.objects):
            col.name = name
            break


def fix_cam_rig_names(scene: Scene | None = None):
    """
    Set all camera rig names to their associated shots. Includes the collection,
    rig object, rig data and action (if available).
    """
    if not scene:
        scene = bpy.context.scene

    # Get from Storyliner and rename
    if hasattr(scene, "WkStoryLiner_props"):
        props = scene.WkStoryLiner_props  # type: ignore
        for shot in props.getShotsList():
            if shot.camera:
                rename_cam_rig(shot.camera, f"cam_{props.sequence_name}_{shot.name}")

    # ... or use timeline markers and rename
    else:
        # Get sequence name
        sq_part = ""
        sequence = session.Session.this().sequence
        if sequence:
            sq_name = sequence.get("name")
            if sq_name:
                sq_part = f"{sq_name}_"

        i = 0
        for marker in scene.timeline_markers:
            if marker.camera:
                i += 1
                rename_cam_rig(marker.camera, f"cam_{sq_part}{marker.name}")


def rename_storyliner_shots(scene: Scene | None = None):
    """
    Rename Storyliner shots in order.

    Args:
        scene (Scene): Scene to use, defaults to context
    """
    if not scene:
        scene = bpy.context.scene

    props = scene.WkStoryLiner_props  # type: ignore

    # First iteration to ensure unique names
    for shot in props.getShotsList():
        shot.name = "tmp"

    # Actual renaming
    for i, shot in enumerate(props.getShotsList(), 1):
        shot.name = f"sh{i:03d}0"


def sort_storyliner_shots(scene: Scene | None = None):
    """
    Sort the Storyliner shots list by their start frame and adjust their names.

    Args:
        scene (Scene): Scene to use, defaults to context
    """
    if not scene:
        scene = bpy.context.scene

    props = scene.WkStoryLiner_props  # type: ignore
    for i in range(len(props.getShotsList())):
        sorted_shots = sorted(props.getShotsList(), key=lambda x: x.start)
        target_shot = sorted_shots[i]
        props.moveShotToIndex(target_shot, i)


def remove_storyliner_shot_gaps(context: Context | None = None):
    """
    Remove all gaps between StoryLiner shots and make them linear.

    Args:
        context (Context)
    """
    if not context:
        context = bpy.context

    props = context.scene.WkStoryLiner_props  # type: ignore
    last_frame = None
    for shot in sorted(props.getShotsList(), key=lambda x: x.start):
        if last_frame is None:
            last_frame = shot.end + 1
            continue

        shot.offsetToFrame(context, last_frame)
        last_frame = shot.end + 1


def get_external_sound_strips(
    root_path: Path | None = None,
    scene: Scene | None = None,
) -> list[SoundStrip]:
    """
    Get all sound strips in the scene that point to an audio file outside of the given
    directory or project root.

    Args:
        root_path (Path | None): Internal path, defaults to project root
        scene (Scene | None): Scene of the sequencer, current if not given

    Returns:
        list[SoundStrip]: List of sound strips with external files
    """
    if TYPE_CHECKING:
        strip: SoundStrip

    if not root_path:
        root_path = find_project_root()
        if not root_path:
            log.warning("Could not determine project root.")
            return []

    if not scene:
        scene = bpy.context.scene

    external_strips = []
    for strip in scene.sequence_editor_create().strips_all:  # type: ignore
        # Check if the strip is a sound strip with a file path
        if strip.type == "SOUND" and strip.sound and strip.sound.filepath:
            sound_path = Path(bpy.path.abspath(strip.sound.filepath)).resolve()

            # Check if the path is relative to project root
            if not sound_path.is_relative_to(root_path.resolve()):
                external_strips.append(strip)

    return external_strips


def get_marker_shot_range(
    scene: Scene | None = None,
    frame: int | None = None,
) -> tuple[str, int, int]:
    """
    Sets the stamp to the current shot information, if available.

    Args:
        scene (Scene | None): Scene to use, defaults to context
        frame (int | None): Sample shot at this position, use current frame if not given

    Returns:
        tuple[str, int, int]: Current shot name, start and end frame
    """
    if not scene:
        scene = bpy.context.scene

    if not frame:
        frame = scene.frame_current

    shot_start = scene.frame_start
    shot_end = scene.frame_end
    shot_name = ""
    for marker in scene.timeline_markers:
        if not marker.camera:
            continue

        if marker.frame >= shot_start and marker.frame <= frame:
            shot_start = marker.frame
            shot_name = marker.name
        elif marker.frame - 1 < shot_end and marker.frame >= frame:
            shot_end = marker.frame - 1

    return (shot_name, shot_start, shot_end)


def set_stamp(scene: Scene | None = None, _=None):
    """
    Sets the stamp to the current shot information, if available.

    Args:
        scene (Scene): Scene to use, defaults to context
    """
    if not scene:
        scene = bpy.context.scene

    stamp = ""

    # Shot info
    s = session.Session.this()
    project = s.project
    if project:
        pr_name = project.get("name")
        if pr_name:
            stamp += pr_name

    episode = s.episode
    if episode:
        ep_name = episode.get("name")
        if ep_name:
            if stamp:
                stamp += " "
            stamp += ep_name.lower()
    sequence = s.sequence
    if sequence:
        sq_name = sequence.get("name")
        if sq_name:
            if stamp:
                stamp += "_"
            stamp += f"{sq_name.lower()}"

    # Find name, start and end frame of current shot marker
    shot_name, shot_start, shot_end = get_marker_shot_range(scene)
    if stamp:
        stamp += "_"
    stamp += (
        f"{shot_name} [ "
        f"{scene.frame_current - shot_start:03d} / "
        f"{shot_end - shot_start:03d} ]"
    )
    task = session.Session.this().task
    if task:
        task_type_name = task.get("task_type_name")
        if task_type_name:
            stamp += f" - {task_type_name}"

    user = client.Client.this().user
    if user:
        user_name = user.get("full_name")
        if not user_name:
            user_name = user.get("email")
        if user_name:
            stamp += f" - {user_name}"

    log.debug(f"Setting stamp text to: {stamp}")

    # Stamp settings
    render = scene.render
    render.metadata_input = "SCENE"
    render.use_stamp_date = False
    render.use_stamp_time = False
    render.use_stamp_render_time = False
    render.use_stamp_frame = False
    render.use_stamp_frame_range = False
    render.use_stamp_memory = False
    render.use_stamp_hostname = False
    render.use_stamp_camera = False
    render.use_stamp_lens = True
    render.use_stamp_scene = False
    render.use_stamp_marker = False
    render.use_stamp_filename = False
    render.use_stamp_note = True
    render.use_stamp = True
    render.stamp_font_size = 24
    render.stamp_foreground = (1.0, 1.0, 1.0, 1.0)
    render.stamp_background = (0.0, 0.0, 0.0, 1.0)
    render.use_stamp_labels = False
    render.stamp_note_text = stamp


def get_missing_asset_libraries(
    context: Context | None = None,
) -> list[dict[str, str | bool]]:
    """
    Return asset library definitions that are not added yet.

    Args:
        Context (Context | None)

    Returns:
        list[dict[str, str |bool ]]: List of missing asset library definitions
    """
    root_path = find_project_root()
    if not root_path:
        return []

    missing_libs = []
    for al_dict in ASSET_LIBRARIES:
        for asset_lib in context.preferences.filepaths.asset_libraries:
            if utils.are_same_paths(asset_lib.path, Path(root_path, al_dict["path"])):
                break
        else:
            missing_libs.append(al_dict)

    return missing_libs


def toggle_asset_collections_exclusion(
    type_name: str = "#CH",
    context: Context | None = None,
) -> list[str]:
    """
    Toggle all asset collections with specified type collection and mark them in a scene
    property.

    Args:
        context (Context)
    """
    if not context:
        context = bpy.context

    scene = context.scene
    if not scene:
        return []

    # Check for excluded assets
    prop_name = "schalotte_excluded_assets"
    excluded_assets: dict = scene.get(prop_name, {})

    old_excluded = excluded_assets.get(type_name)
    new_excluded = []

    # Iterate layer collections
    layer_col = context.view_layer.layer_collection.children.get(type_name)
    if not layer_col:
        log.error(f"{type_name} not in {context.view_layer} layer collection")
        return []

    for child in layer_col.children:
        # Include if already excluded
        if old_excluded and child.name in old_excluded:
            child.exclude = False

        # Exclude if not selected
        elif not child.exclude:
            # Check if collection contains any selected object
            if any(
                obj in set(child.collection.all_objects)
                for obj in context.selected_objects
            ):
                continue

            # Exclude and register
            child.exclude = True
            new_excluded.append(child.name)

    # Remove the type name from exclusions
    if old_excluded:
        excluded_assets.pop(type_name)

        # Remove prop if no exclusions are left
        if not excluded_assets.keys():
            del scene[prop_name]

    # Store exclusions on scene
    if new_excluded:
        # Create scene key if not present
        if not scene.get(prop_name):
            scene[prop_name] = {}

        # Store list
        scene[prop_name][type_name] = new_excluded

    return new_excluded
