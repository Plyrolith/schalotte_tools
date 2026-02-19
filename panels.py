from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from bpy.types import Context

import bpy
from bpy.types import Panel, TIME_MT_editor_menus  # type: ignore

from . import catalog, client, draw, logger, ops, schalotte, session

log = logger.get_logger(__name__)


@catalog.bpy_register
class SCHALOTTE_PT_login(Panel):
    bl_idname = "SCHALOTTE_PT_login"
    bl_category = "Schalotte Tools"
    bl_label = "Login"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_order = 0

    @classmethod
    def poll(cls, context: Context):
        return not client.Client.this().is_logged_in

    def draw(self, context: Context):
        draw.login_ui(self, context)


@catalog.bpy_register
class SCHALOTTE_PT_session(Panel):
    bl_idname = "SCHALOTTE_PT_session"
    bl_category = "Schalotte Tools"
    bl_label = "Session"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_order = 1

    @classmethod
    def poll(cls, context: Context):
        return client.Client.this().is_logged_in

    def draw(self, context: Context):
        draw.session_ui(self, context)


@catalog.bpy_register
class SCHALOTTE_PT_asset_libraries(Panel):
    bl_idname = "SCHALOTTE_PT_asset_libraries"
    bl_category = "Schalotte Tools"
    bl_label = "Asset Libraries"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_order = 2

    @classmethod
    def poll(cls, context: Context):
        return bool(schalotte.get_missing_asset_libraries(context))

    def draw(self, context: Context):
        draw.asset_libraries_ui(self, context)


@catalog.bpy_register
class SCHALOTTE_PT_storyboard(Panel):
    bl_idname = "SCHALOTTE_PT_storyboard"
    bl_category = "Schalotte Tools"
    bl_label = "Storyboard"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_order = 3

    @classmethod
    def register(cls):
        """
        Add the shot marker preview range operator to the timeline.
        """
        TIME_MT_editor_menus.append(draw.shot_range_button)

    @classmethod
    def unregister(cls):
        """
        Remove the shot marker preview range operator from the timeline.
        """
        try:
            TIME_MT_editor_menus.remove(draw.shot_range_button)
        except Exception as e:
            log.debug(f"Timeline draw function has already removed: {e}")

    @classmethod
    def poll(cls, context) -> bool:
        s = session.Session.this()
        return hasattr(context.scene, "WkStoryLiner_props") or bool(
            s.task and s.task.get("task_type_name", "").lower() == "storyboard"
        )

    def draw(self, context: Context):
        draw.storyboard_ui(self, context)


@catalog.bpy_register
class SCHALOTTE_PT_camera(Panel):
    bl_idname = "SCHALOTTE_PT_camera"
    bl_category = "Schalotte Tools"
    bl_label = "Camera"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_order = 4

    def draw(self, context: Context):
        draw.camera_ui(self, context)


@catalog.bpy_register
class SCHALOTTE_PT_storyboard_sequencer(Panel):
    bl_idname = "SCHALOTTE_PT_storyboard_sequencer"
    bl_category = "Schalotte Tools"
    bl_label = "Storyboard"
    bl_space_type = "SEQUENCE_EDITOR"
    bl_region_type = "UI"

    def draw(self, context: Context):
        layout = self.layout
        layout.row().operator(
            ops.SCHALOTTETOOL_OT_AddSoundStrips.bl_idname,
            icon="SOUND",
        )
        layout.row().operator(
            ops.SCHALOTTETOOL_OT_CollectSoundFiles.bl_idname,
            icon="NLA_PUSHDOWN",
        )


@catalog.bpy_register
class SCHALOTTE_PT_performance(Panel):
    bl_idname = "SCHALOTTE_PT_performance"
    bl_category = "Schalotte Tools"
    bl_label = "Performance"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_order = 5

    def draw(self, context: Context):
        draw.performance_ui(self, context)


@catalog.bpy_register
class SCHALOTTE_PT_preview(Panel):
    bl_idname = "SCHALOTTE_PT_preview"
    bl_category = "Schalotte Tools"
    bl_label = "Preview"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_order = 6

    @classmethod
    def poll(cls, context: Context):
        s = session.Session.this()
        return bool(
            bpy.data.filepath
            and s.task
            and not (
                s.task.get("task_type_name", "").lower() == "storyboard"
                and hasattr(context.scene, "WkStoryLiner_props")
            )
        )

    def draw(self, context: Context):
        draw.preview_ui(self, context)


@catalog.bpy_register
class SCHALOTTE_PT_casting(Panel):
    bl_idname = "SCHALOTTE_PT_casting"
    bl_category = "Schalotte Tools"
    bl_label = "Casting"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_order = 7

    @classmethod
    def poll(cls, context: Context):
        s = session.Session.this()
        return bool(s.project and s.shot)

    def draw(self, context: Context):
        draw.casting_ui(self, context)
