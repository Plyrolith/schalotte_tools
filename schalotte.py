from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from bpy.types import Collection, CompositorNodeTree, Material, Scene, World


from pathlib import Path
import bpy
from . import logger

log = logger.get_logger(__name__)


ASSET_TYPE_MAP = {
    "Character": "02_01_01_characters",
    "Environment": "02_01_02_environments",
    "Set Prop": "02_01_03_environmental_props",
    "Hero Prop": "02_01_04_hero_props",
}

COLLECTIONS_MAP = {
    "Character": "#CH",
    "Environment": "#SET",
    "Set Prop": "#SET",
    "Hero Prop": "#PROP",
}


def find_project_root(root_name: str = "02_production") -> Path | None:
    """
    Find the project root path from the current file path.

    Args:
        root_name (str): Name of the root folder in the project structure

    Returns:
        Path | None
    """
    root_path = Path(bpy.data.filepath)
    if not root_path:
        log.error("Could not determine current file path")
        return
    for _ in range(5):
        root_path = root_path.parent
        if root_path.name == root_name:
            break
    else:
        return
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
    blend_files = sorted(asset_dir.glob("*.blend"), key=lambda f: f.stem.lower())
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
    name = "SCH_stb_world"
    file_rel = Path(
        "02_02_storyboard",
        "SCH_stb_setup_Blendfile",
        "SCH_s01_e0x_sq0x_STB_setup.blend",
    )

    world = bpy.data.worlds.get(name)
    if not world:
        # Find the setup file
        root_path = find_project_root()
        if not root_path:
            log.error("Could not find production directory")
            return
        setup_file = root_path / file_rel
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
                filename=f"{setup_file.name}/World/{name}",
                link=False,
                do_reuse_local_id=False,
                autoselect=False,
                active_collection=False,
                instance_collections=False,
                instance_object_data=True,
                set_fake=True,
                use_recursive=True,
            )
            world = bpy.data.worlds.get(name)
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

    # Get all character objects to exclude from re-shading
    char_col = bpy.data.collections.get("#CH")
    if char_col:
        char_objs = set(char_col.all_objects)
    else:
        char_objs = set()
        log.warning("Could not find #CH collection")

    # Shader
    material = ensure_storyboard_material()
    for obj in scene.objects:
        # Skip characters
        if obj in char_objs:
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

    # World
    scene.world = ensure_storyboard_world()
