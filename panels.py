from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from bpy.types import Context

from bpy.types import Panel

from . import catalog, client, draw, session


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
class SCHALOTTE_PT_setup(Panel):
    bl_idname = "SCHALOTTE_PT_setup"
    bl_category = "Schalotte Tools"
    bl_label = "Setup"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_order = 2

    @classmethod
    def poll(cls, context) -> bool:
        s = session.Session.this()
        return bool(s.task and s.task.get("task_type_name", "").lower() == "storyboard")

    def draw(self, context: Context):
        draw.setup_ui(self, context)


@catalog.bpy_register
class SCHALOTTE_PT_preview(Panel):
    bl_idname = "SCHALOTTE_PT_preview"
    bl_category = "Schalotte Tools"
    bl_label = "Preview"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_order = 3

    @classmethod
    def poll(cls, context: Context):
        s = session.Session.this()
        return bool(
            s.task and not s.task.get("task_type_name", "").lower() == "storyboard"
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
    bl_order = 4

    @classmethod
    def poll(cls, context: Context):
        s = session.Session.this()
        return bool(s.project and s.shot)

    def draw(self, context: Context):
        draw.casting_ui(self, context)
