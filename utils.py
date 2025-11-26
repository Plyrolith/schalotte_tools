from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from typing import Iterable
    from bpy.types import Bone, Collection, Context, Object, Scene

import bpy
from pathlib import Path

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


def render_scene(
    file_path: Path | str,
    scene: Scene | None = None,
    use_stamp: bool = False,
):
    """
    Render given or current scene.

    Args:
        file_path (Path | str): Destination file path
        scene (Scene | None): Scene to render, defaults to the current scene
        use_stamp (bool): Burn in the stamp
    """
    if not scene:
        scene = bpy.context.scene
    file_path = Path(file_path)

    # Render settings
    render = scene.render
    render.filepath = file_path.as_posix()
    render.use_file_extension = True
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

    # Stamp settings
    if use_stamp:
        render.metadata_input = "SCENE"
        render.use_stamp_date = False
        render.use_stamp_time = False
        render.use_stamp_render_time = False
        render.use_stamp_frame = True
        render.use_stamp_frame_range = True
        render.use_stamp_memory = False
        render.use_stamp_hostname = False
        render.use_stamp_camera = True
        render.use_stamp_lens = True
        render.use_stamp_scene = False
        render.use_stamp_marker = False
        render.use_stamp_filename = True
        render.use_stamp_note = False
        render.use_stamp = True
        render.stamp_font_size = 16
        render.stamp_foreground = (1.0, 1.0, 1.0, 1.0)
        render.stamp_background = (0.0, 0.0, 0.0, 1.0)
        render.use_stamp_labels = False
    else:
        render.use_stamp = False

    # Render
    file_path.parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.render.render(
        animation=True,
        use_viewport=False,
        scene=scene.name,
    )


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
