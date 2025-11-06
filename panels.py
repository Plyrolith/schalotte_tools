from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from bpy.types import Context

from bpy.types import Panel

from . import catalogue, client, draw


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
class SCHALOTTE_PT_shots(Panel):
    bl_idname = "SCHALOTTE_PT_shots"
    bl_category = "Schalotte"
    bl_label = "Shots"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_order = 2

    @classmethod
    def poll(cls, context: Context):
        return client.Client.this().is_logged_in

    def draw(self, context: Context):
        draw.shots(self, context)
