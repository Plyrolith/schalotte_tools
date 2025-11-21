from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from bpy.types import AddonPreferences, Context, Panel

import bpy
from . import casting, client, ops, session


def login_ui(self: Panel | AddonPreferences, context: Context):
    """
    Draw the login UI.
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


def setup_ui(self: Panel, context: Context):
    """
    File setup operators.
    """
    layout = self.layout
    layout.row().operator(ops.SCHALOTTETOOL_OT_SetupStoryboard.bl_idname)


def preview_ui(self: Panel, context: Context):
    """
    Preview operator UI.
    """
    layout = self.layout
    layout.row().operator(ops.SCHALOTTETOOL_OT_UploadPreview.bl_idname)


def session_ui(self: Panel, context: Context):
    """
    Session selector and operator UI.
    """
    s = session.Session.this()
    layout = self.layout

    file_status = s.get_work_file_status()
    row_guess = layout.row()
    if bpy.data.filepath:
        if file_status == "ACTIVE":
            row_guess.enabled = False
            row_guess.emboss = "NONE"
            op_guess_text = "Current File Matches Selection"
            op_guess_icon = "CHECKMARK"
        else:
            op_guess_text = ops.SCHALOTTETOOL_OT_GuessSessionFromFilepath.bl_label
            op_guess_icon = "FILE_ALIAS"
    else:
        row_guess.enabled = False
        row_guess.emboss = "NONE"
        op_guess_text = "Open File to Guess Task"
        op_guess_icon = "INFO"

    row_guess.operator(
        ops.SCHALOTTETOOL_OT_GuessSessionFromFilepath.bl_idname,
        text=op_guess_text,
        icon=op_guess_icon,
    )

    col_select = layout.column()
    col_select.use_property_split = True
    col_select.row().prop(s, "project_id")
    col_select.row().prop(s, "episode_id")
    col_select.row().prop(s, "sequence_id")
    col_select.row().prop(s, "shot_id")
    col_select.row().prop(s, "task_id")

    row_file = layout.row()
    op_file_name = ops.SCHALOTTETOOL_OT_CreateWorkFile.bl_idname

    match file_status:
        case "ACTIVE":
            row_file.enabled = False
            row_file.emboss = "NONE"
            op_file_text = "File is Active"
            op_file_icon = "CHECKMARK"
        case "EXISTS":
            row_file.operator_context = "EXEC_DEFAULT"
            op_file_name = "wm.open_mainfile"
            op_file_text = "Open Work File"
            op_file_icon = "FILE_BLEND"
        case "MISSING":
            op_file_text = ops.SCHALOTTETOOL_OT_CreateWorkFile.bl_label
            op_file_icon = "FILE_NEW"
        case "NONE":
            row_file.enabled = False
            row_file.emboss = "NONE"
            op_file_text = "Select a Task"
            op_file_icon = "INFO"
        case _:
            row_file.enabled = False
            row_file.emboss = "NONE"
            op_file_text = "Cannot Generate File Path"
            op_file_icon = "ERROR"

    op_open = row_file.operator(op_file_name, text=op_file_text, icon=op_file_icon)
    if file_status == "EXISTS":
        op_open.filepath = s.work_file_path
        op_open.load_ui = False
        op_open.use_scripts = False


def casting_ui(self: Panel, context: Context):
    """
    Casting list and operator UI.
    """
    c = casting.Casting.this()
    layout = self.layout

    layout.row().operator(
        operator=ops.SCHALOTTETOOL_OT_FetchCasting.bl_idname,
        text="Update Casting" if c.links else "Fetch Casting",
        icon="FILE_REFRESH",
    )

    if c.breakdown_file != bpy.data.filepath:
        return

    # Append for storyboard tasks
    s = session.Session.this()
    is_storyboard = s.task and s.task.get("task_type_name", "").lower() == "storyboard"
    link_icon = "APPEND_BLEND" if is_storyboard else "LINKED"

    col = layout.column()
    col_atype_map = {}
    for i, link in enumerate(c.links):
        # Asset type box
        col_atype = col_atype_map.get(link.asset_type_name)
        if not col_atype:
            col_atype = col.box().column(align=True)
            col_atype_map[link.asset_type_name] = col_atype
            row_atype = col_atype.row()
            row_atype.alignment = "CENTER"
            row_atype.label(text=link.asset_type_name)

        # Asset label
        row_asset = col_atype.box().row()
        row_asset.label(text=link.asset_name)

        # Link label and operator
        row_link = row_asset.row(align=True)
        row_link.enabled = bool(link.file_path)
        row_link.label(
            text="",
            icon=link_icon if link.library_name else "BLANK1",
        )
        op_link = row_link.operator(
            operator=ops.SCHALOTTETOOL_OT_LinkAsset.bl_idname,
            text="",
            icon="PLUS" if link.library_name else link_icon,
        )
        op_link.index = i
        op_link.mode = "APPEND" if is_storyboard else "AUTO"

    # Operator to link all missing
    if c.links:
        row_all = layout.row()
        row_all.enabled = any(
            link.file_path and not link.library_name for link in c.links
        )
        op_all = row_all.operator(
            operator=ops.SCHALOTTETOOL_OT_LinkAsset.bl_idname,
            text="Append All Missing" if is_storyboard else "Link All Missing",
            icon=link_icon,
        )
        op_all.index = -1
        op_all.mode = "APPEND" if is_storyboard else "AUTO"
