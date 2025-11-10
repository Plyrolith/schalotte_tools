from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from bpy.types import Context

from bpy.types import Panel

from . import catalogue, client, draw, session


@catalogue.bpy_register
class SCHALOTTE_PT_login(Panel):
    bl_idname = "SCHALOTTE_PT_login"
    bl_category = "Schalotte"
    bl_label = "Login"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_order = 0

    @classmethod
    def poll(cls, context: Context):
        return not client.Client.this().is_logged_in

    def draw(self, context: Context):
        draw.login_ui(self, context)


@catalogue.bpy_register
class SCHALOTTE_PT_setup(Panel):
    bl_idname = "SCHALOTTE_PT_setup"
    bl_category = "Schalotte"
    bl_label = "Setup"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_order = 1

    def draw(self, context: Context):
        draw.setup(self, context)


@catalogue.bpy_register
class SCHALOTTE_PT_session(Panel):
    bl_idname = "SCHALOTTE_PT_session"
    bl_category = "Schalotte"
    bl_label = "Session"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_order = 2

    @classmethod
    def poll(cls, context: Context):
        return client.Client.this().is_logged_in

    def draw(self, context: Context):
        draw.session_ui(self, context)


@catalogue.bpy_register
class SCHALOTTE_PT_casting(Panel):
    bl_idname = "SCHALOTTE_PT_casting"
    bl_category = "Schalotte"
    bl_label = "Casting"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_order = 3

    @classmethod
    def poll(cls, context: Context):
        s = session.Session.this()
        return bool(s.project != "NONE" and s.shot != "NONE")

    def draw(self, context: Context):
        draw.casting_ui(self, context)
