from __future__ import annotations
from typing import TYPE_CHECKING


if TYPE_CHECKING:
    from bpy.types import Context

import bpy
from bpy.props import EnumProperty, StringProperty
from bpy.types import AddonPreferences

from . import draw, logger


def set_log_level(self: Preferences | None = None, context: Context | None = None):
    """
    Set the logger's log level to the preferences value.

    Args:
        self (Preferences | None)
        context (Context | None)
    """
    if not self:
        self = Preferences.this()
    logger.set_handler_levels("console", int(self.log_level))


# This class will be registered with bpy without decorator
class Preferences(AddonPreferences):
    """Add-on preferences"""

    bl_idname: str = __package__  # type:ignore

    module: str = "preferences"

    log_level: EnumProperty(
        name="Log Level",
        items=(
            ("10", "Debug", ""),
            ("20", "Info", ""),
            ("30", "Warning", ""),
            ("40", "Error", ""),
            ("50", "Critical", ""),
        ),
        default="20",
        update=set_log_level,
    )

    project_root: StringProperty(name="Project Root", subtype="DIR_PATH")

    def draw(self, context: Context):
        col = self.layout.column()
        col.use_property_split = True
        col.row().prop(self, "log_level")
        col.row().prop(self, "project_root")
        draw.login_ui(self, context)

    @classmethod
    def this(cls) -> Preferences:
        """
        Return Blender's initiated instance of this module.
        """
        return bpy.context.preferences.addons[__package__].preferences  # type: ignore
