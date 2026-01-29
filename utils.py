from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from typing import Iterable, Literal
    from bpy.types import (
        Bone,
        Collection,
        Context,
        ID,
        Object,
        Operator,
        Scene,
        SoundStrip,
        SpaceView3D,
        UILayout,
    )

import bpy
import contextlib
from pathlib import Path
import shutil

from . import logger


log = logger.get_logger(__name__)


def are_same_paths(*paths: str | Path, resolve: bool = True) -> bool:
    """
    Checks whether a number of paths points to the same file/folder. Resolves pathlib
    Path objects, strings and relative Blender paths.

    Parameters:
        - *paths (str | Path): Paths to compare
        - resolve (bool): Resolve all paths before comparison

    Returns:
        - bool: Whether all paths are the same or not
    """
    first_path = None
    for path in paths:
        # If path is a string and .blend file is loaded, guarantee absolute path
        if isinstance(path, str):
            if bpy.data.filepath:
                path = Path(bpy.path.abspath(path)).resolve()
            else:
                path = Path(path)

        # Resolve and convert to posix
        elif resolve:
            path = path.resolve()
        path = path.as_posix()

        # Store first path for comparison
        if not first_path:
            first_path = path
            continue

        # Compare
        if path != first_path:
            return False

    return True


def render_settings(scene: Scene | None = None):
    """
    Set default render settings for given or current scene.

    Args:
        scene (Scene | None): Scene to render, defaults to the current scene
    """
    if not scene:
        scene = bpy.context.scene

    # Render settings
    render = scene.render
    render.image_settings.file_format = "FFMPEG"

    # Image settings
    image_settings = render.image_settings
    image_settings.color_mode = "RGB"
    image_settings.color_management = "FOLLOW_SCENE"
    image_settings.color_depth = "8"

    # FFmpeg settings
    ffmpeg = render.ffmpeg
    ffmpeg.format = "MPEG4"
    ffmpeg.use_autosplit = False
    ffmpeg.codec = "H264"
    ffmpeg.constant_rate_factor = "MEDIUM"
    ffmpeg.ffmpeg_preset = "GOOD"
    ffmpeg.gopsize = 18
    ffmpeg.use_max_b_frames = False
    ffmpeg.audio_codec = "AAC"
    ffmpeg.audio_channels = "STEREO"
    ffmpeg.audio_mixrate = 48000
    ffmpeg.audio_bitrate = 192
    ffmpeg.audio_volume = 1.0


def render_scene(file_path: Path | str, scene: Scene | None = None):
    """
    Render given or current scene.

    Args:
        file_path (Path | str): Destination file path
        scene (Scene | None): Scene to render, defaults to the current scene
    """
    if not scene:
        scene = bpy.context.scene

    file_path = Path(file_path)

    # Render settings
    render = scene.render
    render.filepath = file_path.as_posix()
    render.use_file_extension = True

    # Render
    file_path.parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.render.render(
        animation=True,
        use_viewport=False,
        scene=scene.name,
    )


def playblast_scene(file_path: Path | str, scene: Scene | None = None):
    """
    Playblast given or current scene.

    Args:
        file_path (Path | str): Destination file path
        scene (Scene | None): Scene to render, defaults to the current scene
    """
    if TYPE_CHECKING:
        space: SpaceView3D

    if not scene:
        scene = bpy.context.scene

    file_path = Path(file_path)

    # Render settings
    render = scene.render
    render.filepath = file_path.as_posix()
    render.use_file_extension = True

    # Render
    file_path.parent.mkdir(parents=True, exist_ok=True)
    with temp_window(bpy.context) as window:
        area = window.screen.areas[0]
        area.type = "VIEW_3D"
        for space in area.spaces:  # type: ignore
            if space.type == "VIEW_3D":
                space.region_3d.view_perspective = "CAMERA"
                space.shading.type = "SOLID"
                space.overlay.show_overlays = False

        bpy.ops.render.opengl(animation=True)


def append_collection(file_path: Path | str, name: str) -> Collection | None:
    """
    Append a collection from given .blend file by name.

    Args:
        file_path (Path | str): Path of the .blend file to append from
        name (str): Name of the collection to append

    Returns:
        Collection | None: Appended collection, if successful
    """
    # Remove "Appended Data" collection, if it exists
    appended_data = bpy.data.collections.get("Appended Data")
    if appended_data:
        bpy.data.collections.remove(appended_data)

    path = Path(file_path)

    # Append
    with bpy.context.temp_override(  # type: ignore
        window=bpy.data.window_managers[0].windows[0],
    ):
        bpy.ops.wm.append(
            directory=path.parent.as_posix(),
            filename=f"{path.name}/Collection/{name}",
            link=False,
            do_reuse_local_id=False,
            autoselect=False,
            active_collection=False,
            instance_collections=False,
            instance_object_data=True,
            set_fake=False,
            use_recursive=True,
        )

    # Find "Appended Data" collection
    appended_data = bpy.data.collections.get("Appended Data")
    if not appended_data:
        log.error(f"Could not locate appended data for {name}")
        return

    # Find new collection in "Appended Data" collection
    try:
        col = appended_data.children[0]
    except IndexError:
        log.error(f"Could not find appended collection for {name}")
        return

    # Remove "Appended Data" collection
    bpy.data.collections.remove(appended_data)

    return col


def get_sequencer_max_channel(scene: Scene | None = None) -> int:
    """
    Get the highest channel number of all strips within a scene sequencer.

    Parameters:
        scene (Scene | None): Scene of the sequencer, use context if none is given

    Returns:
        int: Highest used channel number
    """
    if not scene:
        scene = bpy.context.scene

    channel_offset = 0
    for strip in scene.sequence_editor.strips:
        if strip.channel > channel_offset:
            channel_offset = strip.channel

    return channel_offset


def select_pose_bones(
    obj: Object,
    bone_names: Iterable[str],
    clear: bool = False,
    context: Context | None = None,
) -> Bone:
    """
    Select all bones with the given names. Make the first one active.

    Parameters:
        obj (Object): The armature object
        bone_names (Iterable[str]): Bone names to select
        clear (bool): Whether to clear selection before adding new ones
        context (Context | None): The current Blender context

    Returns:
        list[Bone]: List of selected bones.
    """
    if not context:
        context = bpy.context

    # Switch to object mode
    if context.mode != "OBJECT":
        bpy.ops.object.mode_set(mode="OBJECT")

    # Deselect all objects
    if clear:
        bpy.ops.object.select_all(action="DESELECT")

    # Select object and set active
    obj.select_set(True)
    context.view_layer.objects.active = obj

    # Switch to pose mode
    bpy.ops.object.mode_set(mode="POSE")

    # Deselect all pose bones
    if clear:
        bpy.ops.pose.select_all(action="DESELECT")

    # Select pose bones
    bones = []
    for bone_name in bone_names:
        bone = obj.data.bones.get(bone_name)  # type: ignore
        if not bone:
            log.warning(f"{bone_name} not found in {obj.name}.")
            continue

        bone.select = True
        bones.append(bone)

    # Activate first bone
    if bones:
        obj.data.bones.active = bones[0]  # type: ignore

    return bones  # type: ignore


def iterable_to_string(iterable: Iterable, delimiter: str = "␟") -> str:
    """
    Converts an iterable to string using a delimiter.

    Args:
        iterable (Iterable): The iterable to convert
        delimiter (str): The delimiter used for splitting the string

    Returns:
        str: The converted string
    """
    return delimiter.join(map(str, iterable))


def string_to_list(string: str, delimiter: str = "␟") -> list[str]:
    """
    Converts a delimited string into a list.

    Args:
        string (str): The string to convert
        delimiter (str): The delimiter used for splitting the string

    Returns:
        list[str]: The converted list
    """
    return string.split(delimiter)


def copy_pose(source: Object, target: Object):
    """
    Copy the current pose from one armature object to another.

    Args:
        source (Object): The source armature object.
        target (Object): The target armature object.
    """
    props = (
        "location",
        "rotation_axis_angle",
        "rotation_euler",
        "rotation_mode",
        "rotation_quaternion",
        "scale",
    )

    # Set object transforms
    for prop in props:
        setattr(target, prop, getattr(source, prop))

    # Set pose bone props
    for pbone_s in source.pose.bones:
        pbone_t = target.pose.bones.get(pbone_s.name)
        if not pbone_t:
            log.warning(f"Bone {pbone_s.name} does not exist on {target.name}.")
            continue

        # Set transforms
        for prop in props:
            setattr(pbone_t, prop, getattr(pbone_s, prop))

        # Set custom attributes
        for k, v in pbone_s.items():
            pbone_t[k] = v


def move_datablock_filepath(
    datablock: ID,
    directory: Path | str,
    name: str | None = None,
    relative: bool = True,
    copy: bool = False,
    overwrite: bool = False,
) -> Path | None:
    """
    Move a datablock's filepath to another location.

    Args:
        datablock (ID): The datablock to move
        directory (Path | str): The new directory for the datablock
        name (str | None): New file name, use old name by default
        relative (bool): Make new path relative
        copy (bool): Make a copy of the file instead of moving it
        overwrite (bool): Overwrite file if it already exists

    Returns:
        Path | None: New file path if move was successful
    """
    # Get the source path
    src = Path(bpy.path.abspath(datablock.filepath))  # type: ignore

    # Generate destination file path
    if not name:
        name = src.name
    dst = Path(directory, name)

    # Check if the current location is already correct
    if src == dst:
        return dst

    # Check if the files exist
    if src.exists():
        if overwrite or not dst.exists():
            # Move or copy the file
            dst.parent.mkdir(parents=True, exist_ok=True)
            if copy:
                shutil.copy(src, dst)
            else:
                src.rename(dst)
    elif not dst.exists():
        log.error(f"{datablock.name} file does not exist: {src}")

    # Set new datablock filepath
    filepath = dst.as_posix()
    if relative:
        filepath = bpy.path.relpath(filepath)
    datablock.filepath = filepath  # type: ignore

    return dst


def show_layout(
    layout: UILayout,
    data: ID | Operator,
    property: str,
    text: str | None = None,
    alignment: Literal["LEFT", "CENTER", "RIGHT"] = "LEFT",
    icon: str = "",
) -> bool:
    """
    Draw a foldout control in the current UI.

    Args:
        layout (UILayout): Layout to draw at
        data (ID | Operator): Host datablock of the collapse status bool property
        property (str): Name of the collapse status bool property
        text (str, optional): Alternative text for label
        alignment (str):
            - LEFT
            - CENTER
            - RIGHT
        icon (str): Draw an additional icon of this type

    Returns:
        bool: Whether the foldout should be drawn or not
    """
    enabled = bool(getattr(data, property))

    row_main = layout.row(align=True)
    row_main.use_property_split = False

    # Button, add text if left
    row_button = row_main.row(align=True)
    row_button.alignment = "LEFT"
    row_button.prop(
        data=data,
        property=property,
        text=text if alignment == "LEFT" and not icon else "",
        icon_only=False if alignment == "LEFT" or icon else True,
        icon="DOWNARROW_HLT" if enabled else "RIGHTARROW",
        emboss=False,
    )

    # Text in separate property if not left aligned, to be able to separate from button
    if alignment != "LEFT" or icon:
        row_text = row_main.row(align=True)
        row_text.alignment = alignment
        row_text.prop(
            data=data,
            property=property,
            text=text,
            icon=icon or "NONE",  # type: ignore
            toggle=True,
            emboss=False,
        )

    return enabled


def get_packed_sound_strips(scene: Scene | None = None) -> list[SoundStrip]:
    """
    Get all packed sound strips in the scene's sequencer.

    Args:
        scene (Scene | None): Scene of the sequencer, current if not given

    Returns:
        list[SoundStrip]: List of packed sound strips
    """
    if TYPE_CHECKING:
        strip: SoundStrip

    if not scene:
        scene = bpy.context.scene

    packed_strips = []
    for strip in scene.sequence_editor_create().strips_all:  # type: ignore

        # Check if the strip is packed
        if strip.type == "SOUND" and strip.sound and strip.sound.packed_file:
            packed_strips.append(strip)

    return packed_strips


@contextlib.contextmanager
def temp_window(context: Context | None = None):
    """
    Create temporary-window context.

    Args:
        context (Context |None): Blender context
    """
    if not context:
        context = bpy.context

    current_windows = set(context.window_manager.windows)
    bpy.ops.wm.window_new()
    window = list(set(context.window_manager.windows) - current_windows)[0]
    try:
        yield window
    finally:
        bpy.ops.wm.window_close()
