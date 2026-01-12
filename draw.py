from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from bpy.types import AddonPreferences, Context, OperatorProperties, Panel, UILayout

from pathlib import Path
import bpy
from . import camera, casting, client, ops, preferences, session


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

    col_login = layout.column()
    col_login.use_property_split = True
    col_login.enabled = not c.is_logged_in
    col_login.row().prop(c, "host")
    col_login.row().prop(c, "username")
    col_login.row().prop(c, pw)
    col_login = layout.row().column()
    col_login.use_property_split = True
    col_login.prop(c, "use_cache")
    layout.row().operator(op)


def storyboard_ui(self: Panel, context: Context):
    """
    Storyboard operators.
    """
    layout = self.layout
    layout.row().operator(ops.SCHALOTTETOOL_OT_SetupStoryboard.bl_idname, icon="PRESET")

    layout.row().separator()
    layout.row().operator(ops.SCHALOTTETOOL_OT_AddSoundStrips.bl_idname, icon="SOUND")
    layout.row().operator(
        ops.SCHALOTTETOOL_OT_CollectSoundFiles.bl_idname,
        icon="NLA_PUSHDOWN",
    )

    layout.row().separator()
    layout.row().operator(
        ops.SCHALOTTETOOL_OT_RemoveStoryLinerGaps.bl_idname,
        icon="SEQ_STRIP_META",
    )

    layout.row().operator(
        ops.SCHALOTTETOOL_OT_FixStoryboardNames.bl_idname,
        icon="WORDWRAP_OFF",
    )

    row_add = layout.row(align=True)
    row_add.operator(
        ops.SCHALOTTETOOL_OT_AddShot.bl_idname,
        icon="CON_CAMERASOLVER",
    ).use_current_camera = True
    row_add.operator(
        ops.SCHALOTTETOOL_OT_AddShot.bl_idname,
        text="",
        icon="ADD",
    ).use_current_camera = False


def preview_ui(self: Panel, context: Context):
    """
    Preview operator UI.
    """
    layout = self.layout
    layout.row().operator(
        ops.SCHALOTTETOOL_OT_UploadPreview.bl_idname,
        icon="RENDER_ANIMATION",
    )


def session_ui(self: Panel, context: Context):
    """
    Session selector and operator UI.
    """
    s = session.Session.this()
    layout = self.layout

    if not preferences.Preferences.this().project_root:
        file_status = "NO_ROOT"
    else:
        file_status = s.get_work_file_status()
    row_guess = layout.row()
    if bpy.data.filepath:
        if file_status == "ACTIVE":
            row_guess.alignment = "CENTER"
            row_guess.label(text="File is Active", icon="CHECKMARK")
        else:
            row_guess.operator(
                operator=ops.SCHALOTTETOOL_OT_GuessSessionFromFilepath.bl_idname,
                icon="FILE_ALIAS",
            )
    else:
        row_guess.alignment = "CENTER"
        row_guess.label(text="Open a File to Guess Task", icon="INFO")

    col_select = layout.column()
    col_select.use_property_split = True
    col_select.row().prop(s, "project_id")
    col_select.row().prop(s, "episode_id")
    col_select.row().prop(s, "sequence_id")
    col_select.row().prop(s, "shot_id")
    col_select.row().prop(s, "task_id")

    row_file = layout.row(align=True)

    match file_status:
        case "ACTIVE":
            op_open = row_file.operator(
                operator="wm.path_open",
                text="Open Location",
                icon="FILEBROWSER",
            )
            op_open.filepath = Path(s.work_file_path).parent.as_posix()

        case "EXISTS":
            row_file.operator_context = "EXEC_DEFAULT"
            op_file = row_file.operator(
                operator="wm.open_mainfile",
                text="Open Work File",
                icon="FILE_BLEND",
            )
            op_file.filepath = s.work_file_path
            op_file.load_ui = False
            op_file.use_scripts = False
            op_open = row_file.operator(
                operator="wm.path_open",
                text="",
                icon="FILEBROWSER",
            )
            op_open.filepath = Path(s.work_file_path).parent.as_posix()

        case "MISSING":
            op_open = row_file.operator(
                operator=ops.SCHALOTTETOOL_OT_CreateWorkFile.bl_idname,
                text=ops.SCHALOTTETOOL_OT_CreateWorkFile.bl_label,
                icon="FILE_NEW",
            )
        case "NONE":
            row_file.alignment = "CENTER"
            row_file.label(
                text="Select a Task",
                icon="INFO",
            )
        case "NO_ROOT":
            row_file.alignment = "CENTER"
            row_file.label(
                text="Guess From Path to Set Project Root",
                icon="ERROR",
            )
        case _:
            row_file.alignment = "CENTER"
            row_file.label(
                text="Cannot Generate File Path",
                icon="ERROR",
            )


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

    col_casting = layout.column()
    col_atype_map = {}
    for i, link in enumerate(c.links):
        # Asset type box
        col_atype = col_atype_map.get(link.asset_type_name)
        if not col_atype:
            col_atype = col_casting.box().column(align=True)
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
            operator=ops.SCHALOTTETOOL_OT_ImportAsset.bl_idname,
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
            operator=ops.SCHALOTTETOOL_OT_ImportAsset.bl_idname,
            text="Append All Missing" if is_storyboard else "Link All Missing",
            icon=link_icon,
        )
        op_all.index = -1
        op_all.mode = "APPEND" if is_storyboard else "AUTO"


def camera_ui(self: Panel, context: Context):
    """
    Dolly camera rig UI.
    """

    def draw_select(
        layout: UILayout,
        bone_names: str,
        text: str = "",
        icon: str = "NONE",
        clear: bool = False,
        depress: bool = False,
    ) -> OperatorProperties:
        """
        Draws a pose bones select operator.
        """
        op_sel = layout.operator(
            operator=ops.SCHALOTTETOOL_OT_SelectPoseBones.bl_idname,
            text=text,
            icon=icon,  # type: ignore
            depress=depress,
        )
        op_sel.object_name = object_name
        op_sel.bone_names = bone_names
        op_sel.clear = clear
        return op_sel

    # Find camera and rig
    enabled = False
    rig = None
    object_name = ""
    cam = context.scene.camera
    if cam and cam.parent and cam.parent.type == "ARMATURE":
        rig = cam.parent
        object_name = rig.name
        enabled = True

    # Check selection
    cam_bone = None
    root_selected = False
    cam_selected = False
    aim_selected = False
    off_selected = False
    if rig:
        cam_bone = rig.pose.bones.get("Camera")
        selected_pose_bones = context.selected_pose_bones
        if selected_pose_bones:
            if cam_bone and cam_bone in selected_pose_bones:
                cam_selected = True
            root_bone = rig.pose.bones.get("Root")
            if root_bone and root_bone in selected_pose_bones:
                root_selected = True
            aim_bone = rig.pose.bones.get("Aim")
            if aim_bone and aim_bone in selected_pose_bones:
                aim_selected = True
            offset_bone = rig.pose.bones.get("Camera_Offset")
            if offset_bone and offset_bone in selected_pose_bones:
                off_selected = True

    # Camera UI
    layout = self.layout
    c = camera.CameraSettings.this()

    # Hide inactive
    icon_hide = "RESTRICT_VIEW_ON" if c.hide_inactive_cameras else "RESTRICT_VIEW_OFF"
    layout.row().prop(c, "hide_inactive_cameras", icon=icon_hide, toggle=True)

    # Focal length
    row_lens = layout.row()
    row_lens.use_property_split = True
    if cam_bone:
        row_lens.prop(cam_bone, '["lens"]', text="Focal Length")
    else:
        row_lens.alignment = "CENTER"
        row_lens.label(text="No Active Camera Rig", icon="OBJECT_HIDDEN")

    layout.row()

    # Offset
    box_select = layout.box()
    row_offset = box_select.row(align=True)
    row_offset.enabled = enabled
    draw_select(
        row_offset,
        "Camera_Offset",
        "Offset",
        "MESH_CIRCLE",
        True,
        off_selected,
    )
    draw_select(row_offset, "Camera_Offset", "", "SELECT_EXTEND", False, off_selected)

    col_camaim = box_select.column(align=True)

    # Camera
    row_single = col_camaim.row(align=True)
    row_single.enabled = enabled

    # Aim
    draw_select(row_single, "Aim", "Aim", "EMPTY_AXIS", True, aim_selected)
    draw_select(row_single, "Aim", "", "SELECT_EXTEND", False, aim_selected)

    draw_select(
        row_single,
        "Camera",
        "Camera",
        "NONE",
        True,
        cam_selected,
    )
    draw_select(row_single, "Camera", "", "SELECT_EXTEND", False, cam_selected)

    # Camera & Aim
    row_both = col_camaim.row(align=True)
    row_both.enabled = enabled
    draw_select(
        row_both,
        "Camera␟Aim",
        "Camera & Aim",
        "CAMERA_DATA",
        True,
        cam_selected and aim_selected,
    )
    draw_select(
        row_both,
        "Camera␟Aim",
        "",
        "SELECT_EXTEND",
        False,
        cam_selected and aim_selected,
    )

    # Root
    row_root = box_select.row(align=True)
    row_root.enabled = enabled
    draw_select(row_root, "Root", "Root", "CURSOR", True, root_selected)
    draw_select(row_root, "Root", "", "SELECT_EXTEND", False, root_selected)

    layout.row()

    # Camera
    col_cam = layout.column()

    # StoryLiner passepartout
    storyliner = context.preferences.addons.get("storyliner")
    if storyliner:
        row_slpasse = col_cam.row()
        row_slpasse.prop(
            storyliner.preferences,
            "playback_useOpaquePassePartout",
            text="Auto Passepartout",
            icon="EVENT_MEDIAPLAY",
            toggle=True,
        )

    # Passepartout
    row_passe = col_cam.row(align=True)
    row_passe.enabled = bool(
        not storyliner or not storyliner.preferences.playback_useOpaquePassePartout  # type: ignore
    )
    row_passe.prop(c, "passepartout_alpha", expand=True)
    view_3d = bpy.context.preferences.themes[0].view_3d
    row_passe.prop(view_3d, "camera_passepartout", text="")

    # Guides
    row_guides = col_cam.row(align=True)  # heading="Guides")
    row_guides.prop(c, "show_composition_thirds", icon="MESH_GRID", toggle=True)
    row_guides.prop(c, "show_composition_golden", icon="MOD_MULTIRES", toggle=True)
    row_guides.prop(c, "show_composition_center", icon="SPLIT_VERTICAL", toggle=True)
    row_guides.prop(view_3d, "view_overlay", text="")
