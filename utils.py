from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from bpy.types import Scene

import bpy
from pathlib import Path


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
