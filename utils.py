from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from typing import Any, Generator, Iterable, Literal

    from bpy.types import (
        bpy_struct,
        ID,
        Bone,
        Collection,
        Context,
        Object,
        Operator,
        PoseBone,
        Scene,
        SoundStrip,
        SpaceView3D,
        UILayout,
        Window,
    )

import contextlib
import shutil
from pathlib import Path

import bpy

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


def insert_pbone_keyframe(
    pbone: PoseBone,
    frame: int | None = None,
    use_location: bool = True,
    use_rotation: bool = True,
    use_scale: bool = True,
    use_custom_properties: bool = True,
):
    """
    Set a keyframe on a pose bone for transform channels and custom properties.

    Args:
        pbone (PoseBone): The pose bone to set keyframes for
        frame (int | None): The frame to set keyframes on, None for current frame
        use_location (bool): Whether to set keyframes on location channels
        use_rotation (bool): Whether to set keyframes on rotation mode and channels
        use_scale (bool): Whether to set keyframes on scale channels
        use_custom_properties (bool): Whether to set keyframes on custom properties
    """
    obj = pbone.id_data
    property_names = []

    # Frame
    if frame is None:
        frame = bpy.context.scene.frame_current

    # Location
    if use_location:
        property_names.append(".location")

    # Rotation
    if use_rotation:
        property_names.append(".rotation_mode")

        # Use currently used rotation property
        rotation_mode = pbone.rotation_mode
        if rotation_mode == "QUATERNION":
            property_names.append(".rotation_quaternion")
        elif rotation_mode == "AXIS_ANGLE":
            property_names.append(".rotation_axis_angle")
        else:
            property_names.append(".rotation_euler")

    # Scale
    if use_scale:
        property_names.append(".scale")

    # Custom properties
    if use_custom_properties:
        for prop in get_drivable_custom_properties(pbone).keys():  # type: ignore
            log.debug(f"Adding: {pbone.name}: {prop}")
            property_names.append(f'["{prop}"]')

    # Set keyframes
    for prop in property_names:
        # log.debug(f"Key: {obj.name} - {pbone.name}{prop}")
        obj.keyframe_insert(
            f'pose.bones["{pbone.name}"]{prop}',
            index=-1,
            frame=frame,
            group=pbone.name,
        )


def get_drivable_custom_properties(
    datablock: ID,
) -> dict[str, int | float | tuple[int | float]]:
    """
    Get all integer and float custom property names for a datablock.

    Args:
        datablock (ID): Datablock to get the property names from

    Returns:
        dict[str, int | float | tuple[int | float]]: Dictionary of property names and values
    """
    return {
        prop: value
        for prop, value in datablock.items()
        if type(value).__name__ in {"bool", "float", "int", "IDPropertyArray"}
    }


def apply_render_settings(
    scene: Scene | None = None,
    prop_tracker: PropTracker | None = None,
) -> PropTracker:
    """
    Set default render settings for given or current scene and track previous settings.

    Args:
        scene (Scene | None): Scene to render, defaults to the current scene
        prop_tracker (PropTracker | None): Existing property tracker or create a new one

    Returns:
        PropertyTracker: Tracker storing previous values
    """
    if not scene:
        scene = bpy.context.scene

    if not prop_tracker:
        prop_tracker = PropTracker(scene)  # type: ignore

    prop_tracker.set(
        render__image_settings__file_format="FFMPEG",
        render__image_settings__color_mode="RGB",
        render__image_settings__color_management="FOLLOW_SCENE",
        render__image_settings__color_depth="8",
        render__ffmpeg__format="MPEG4",
        render__ffmpeg__use_autosplit=False,
        render__ffmpeg__codec="H264",
        render__ffmpeg__constant_rate_factor="MEDIUM",
        render__ffmpeg__ffmpeg_preset="GOOD",
        render__ffmpeg__gopsize=18,
        render__ffmpeg__use_max_b_frames=False,
        render__ffmpeg__audio_codec="AAC",
        render__ffmpeg__audio_channels="STEREO",
        render__ffmpeg__audio_mixrate=48000,
        render__ffmpeg__audio_bitrate=192,
        render__ffmpeg__audio_volume=1.0,
        render__metadata_input="SCENE",
        render__use_stamp_date=False,
        render__use_stamp_time=False,
        render__use_stamp_render_time=False,
        render__use_stamp_frame=False,
        render__use_stamp_frame_range=False,
        render__use_stamp_memory=False,
        render__use_stamp_hostname=False,
        render__use_stamp_camera=False,
        render__use_stamp_lens=False,
        render__use_stamp_scene=False,
        render__use_stamp_marker=False,
        render__use_stamp_filename=False,
        render__use_stamp_note=False,
        render__use_stamp=False,
        render__stamp_font_size=24,
        render__stamp_foreground=(1.0, 1.0, 1.0, 1.0),
        render__stamp_background=(0.0, 0.0, 0.0, 1.0),
        render__use_stamp_labels=False,
        render__stamp_note_text="",
    )
    return prop_tracker


def playblast_scene(
    file_path: Path | str,
    scene: Scene | None = None,
    modal: bool = False,
) -> Window | None:
    """
    Playblast given or current scene.

    Args:
        file_path (Path | str): Destination file path
        scene (Scene | None): Scene to render, defaults to the current scene
        modal (bool): Whether to render in modal mode

    Returns:
        Window | None: New Window if run modally
    """

    def set_up_window(window: Window):
        """
        Set up the new window display for playblasting.

        Args:
            window (Window): Window to set up
        """
        if TYPE_CHECKING:
            space: SpaceView3D
        area = window.screen.areas[0]
        area.type = "VIEW_3D"
        for space in area.spaces:  # type: ignore
            if space.type == "VIEW_3D":
                space.region_3d.view_perspective = "CAMERA"
                space.shading.type = "SOLID"
                space.overlay.show_overlays = False

    context = bpy.context
    if not scene:
        scene = context.scene

    file_path = Path(file_path)

    # Render settings
    render = scene.render
    render.filepath = file_path.as_posix()
    render.use_file_extension = True

    file_path.parent.mkdir(parents=True, exist_ok=True)

    # Render in modal
    if modal:
        window = create_new_window(context)
        set_up_window(window)
        bpy.ops.render.opengl("INVOKE_DEFAULT", animation=True)
        return window

    # Or directly
    else:
        with temp_window(context) as window:
            set_up_window(window)
            bpy.ops.render.opengl("EXEC_DEFAULT", animation=True)


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


def create_new_window(context: Context | None = None) -> Window:
    """
    Create temporary-window context.

    Args:
        context (Context |None): Blender context
    """
    if not context:
        context = bpy.context

    current_windows = set(context.window_manager.windows)
    bpy.ops.wm.window_new()
    return list(set(context.window_manager.windows) - current_windows)[0]


def close_window(window: Window, context: Context | None = None):
    """
    Close given window.

    Args:
        window (Window): Window to be closed
        context (Context |None): Blender context
    """
    if not context:
        context = bpy.context

    with context.temp_override(window=window):  # type: ignore
        bpy.ops.wm.window_close()


def same_paths(*paths: str | Path) -> bool:
    """
    Checks whether a list of paths points to the same file/folder.

    Parameters:
        - *paths (str | Path): Paths to compare

    Returns:
        - bool: Whether all paths are the same or not
    """
    if len(paths) == 1:
        return True

    first_path = None
    for path in paths:
        # If path is a string, guarantee absolute path and convert to pathlib
        if isinstance(path, str):
            path = Path(bpy.path.abspath(path))

        # Resolve and convert to posix
        path = path.resolve().as_posix()

        # Store first path for comparison
        if not first_path:
            first_path = path
            continue

        # Compare
        if path != first_path:
            return False

    return True


@contextlib.contextmanager
def temp_window(context: Context | None = None):
    """
    Create temporary-window context.

    Args:
        context (Context |None): Blender context
    """
    if not context:
        context = bpy.context

    window = create_new_window(context)
    try:
        yield window
    finally:
        close_window(window, context)


@contextlib.contextmanager
def temp_props(struct: bpy_struct, **kwargs) -> Generator[PropTracker, Any, Any]:
    """
    Create a context with temporary property values for given struct.

    Args:
        struct (bpy_struct): Struct to store and set values for
        **: prop names and values, double underscores for nested props
    """
    prop_tracker = PropTracker(struct, **kwargs)
    try:
        yield prop_tracker
    finally:
        prop_tracker.revert()


class PropTracker:
    """
    Set a struct's properties to temporary values and easily revert to previous ones.
    """

    struct: bpy_struct
    value_dict: dict[str, tuple[Any, Any]]

    def __init__(self, struct: bpy_struct, **kwargs):
        """
        Save previous values, set new values and save them as well.

        Args:
            struct (bpy_struct): Struct to store and set values for
            **: prop names and values, double underscores for nested props
        """
        self.struct = struct
        self.value_dict = {}
        self.set(**kwargs)

    def get_new(self, prop: str) -> Any:
        """
        Return the struct's stored newly applied value for given prop name.

        Args:
            prop (str): Name of the property whose new value is returned
        """
        prop = prop.replace("__", ".")
        return self.value_dict[prop][1]

    def get_old(self, prop: str) -> Any:
        """
        Return the struct's previously stored value for given prop name.

        Args:
            prop (str): Name of the property whose old value is returned
        """
        prop = prop.replace("__", ".")
        return self.value_dict[prop][0]

    def reapply(self):
        """
        Apply the new values to the struct again.
        """
        for prop_key, (_, value) in self.value_dict.items():
            # Convert double underscores to dots
            prop = prop_key.replace("__", ".")

            # Navigate to nested property
            current = self.struct
            parts = prop.split(".")

            for part in parts[:-1]:
                current = getattr(current, part)

            setattr(current, parts[-1], value)

    def revert(self):
        """
        Revert the struct's values to the stored ones.
        """
        for prop_key, (value, _) in self.value_dict.items():
            # Convert double underscores to dots
            prop = prop_key.replace("__", ".")

            # Navigate to nested property
            current = self.struct
            parts = prop.split(".")

            for part in parts[:-1]:
                current = getattr(current, part)

            setattr(current, parts[-1], value)

    def set(self, **kwargs):
        """
        Set values and store previous one. Overrides previous entries.

        Args:
            **: prop names and values, double underscores for nested props
        """
        for prop_key, value in kwargs.items():
            # Convert double underscores to dots
            prop = prop_key.replace("__", ".")

            # Navigate to nested property
            current = self.struct
            parts = prop.split(".")

            for part in parts[:-1]:
                current = getattr(current, part)

            old_value = getattr(current, parts[-1])
            self.value_dict[prop] = (old_value, value)
            setattr(current, parts[-1], value)
