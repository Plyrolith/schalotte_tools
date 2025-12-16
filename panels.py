from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from bpy.types import Context

import bpy
from bpy.types import Panel

from . import catalog, client, draw, ops, session


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
class SCHALOTTE_PT_storyboard(Panel):
    bl_idname = "SCHALOTTE_PT_storyboard"
    bl_category = "Schalotte Tools"
    bl_label = "Storyboard"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_order = 2

    @classmethod
    def poll(cls, context) -> bool:
        return hasattr(context.scene, "WkStoryLiner_props")

    def draw(self, context: Context):
        draw.storyboard_ui(self, context)


@catalog.bpy_register
class SCHALOTTE_PT_camera(Panel):
    bl_idname = "SCHALOTTE_PT_camera"
    bl_category = "Schalotte Tools"
    bl_label = "Camera"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_order = 3

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
        row_sound = self.layout.row()
        row_sound.operator(ops.SCHALOTTETOOL_OT_AddSoundStrips.bl_idname, icon="SOUND")


@catalog.bpy_register
class SCHALOTTE_PT_preview(Panel):
    bl_idname = "SCHALOTTE_PT_preview"
    bl_category = "Schalotte Tools"
    bl_label = "Preview"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_order = 4

    @classmethod
    def poll(cls, context: Context):
        s = session.Session.this()
        return bool(
            bpy.data.filepath
            and s.task
            and not s.task.get("task_type_name", "").lower() == "storyboard"
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
    bl_order = 5

    @classmethod
    def poll(cls, context: Context):
        s = session.Session.this()
        return bool(s.project and s.shot)

    def draw(self, context: Context):
        draw.casting_ui(self, context)
