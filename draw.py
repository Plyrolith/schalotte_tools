from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from bpy.types import AddonPreferences, Context, Panel

from . import client, ops


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
    layout.row().operator(op)
