from __future__ import annotations

import bpy
from bpy.types import PropertyGroup


# This class will be registered with bpy without decorator
class WmContainer(PropertyGroup):
    """Base window manager container"""

    module: str = "wm_container"

    @classmethod
    def this(cls) -> WmContainer:
        """
        Return Blender's initiated instance of this module.
        """
        return getattr(bpy.context.window_manager, __package__)  # type: ignore
