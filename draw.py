from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from bpy.types import AddonPreferences, Context, Panel

from . import client, ops, wm_select


def login_ui(self: Panel | AddonPreferences, context: Context):
    """
    Draw the login UI.

    Args:
        context (Context)
    """
    layout = self.layout
    c = client.Client.this()
    if c.is_logged_in:
        op = ops.SCHALOTTETOOLS_OT_LogOut.bl_idname
        pw = "login_date"
    else:
        op = ops.SCHALOTTETOOLS_OT_LogIn.bl_idname
        pw = "password"

    col = layout.column()
    col.use_property_split = True
    col.enabled = not c.is_logged_in
    col.row().prop(c, "host")
    col.row().prop(c, "username")
    col.row().prop(c, pw)
    col = layout.row().column()
    col.use_property_split = True
    col.prop(c, "use_cache")
    layout.row().operator(op)


def setup(self: Panel, context: Context):
    """
    File setup operators.
    """
    layout = self.layout
    layout.row().operator(ops.SCHALOTTETOOL_OT_SetupStoryboard.bl_idname)


def shots(self: Panel, context: Context):
    """
    Shot selector and operator UI.
    """
    s = wm_select.WmSelect.this()
    layout = self.layout

    col = layout.column()
    col.use_property_split = True
    col.row().prop(s, "project")
    col.row().prop(s, "episode")
    col.row().prop(s, "sequence")
    col.row().prop(s, "shot")
    col.row().prop(s, "task")

    layout.row().operator(ops.SCHALOTTETOOL_OT_UploadPreview.bl_idname)
