from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from typing import Iterator
    from bpy.types import Context, Scene

import bpy
from bpy.props import BoolProperty, EnumProperty

from . import catalog, logger


log = logger.get_logger(__name__)


@catalog.bpy_window_manager
class Camera(catalog.WindowManagerModule):
    """Camera module"""

    module: str = "camera"

    @staticmethod
    def get_all_cameras_in_scene(scene: Scene | None = None) -> Iterator[Camera]:
        """
        Get all cameras in given scene.

        Args:
            scene (Scene | None): The scene to get the cameras from

        Returns:
            Iterator: Iterator of cameras in scene
        """
        if not scene:
            scene = bpy.context.scene
        for obj in scene.collection.all_objects:
            if obj.type == "CAMERA":
                yield obj.data  # type: ignore

    def update_passepartout_alpha(self, context: Context):
        """
        Set the passepartout on all cameras within the current scene.
        """
        for cam in self.get_all_cameras_in_scene(context.scene):
            cam.show_passepartout = True  # type: ignore
            cam.passepartout_alpha = float(self.passepartout_alpha)  # type: ignore

    def update_show_composition_center(self, context: Context):
        """
        Set center composition on all cameras within the current scene.
        """
        for cam in self.get_all_cameras_in_scene(context.scene):
            cam.show_composition_center = self.show_composition_center  # type: ignore

    def update_show_composition_golden(self, context: Context):
        """
        Set golden composition on all cameras within the current scene.
        """
        for cam in self.get_all_cameras_in_scene(context.scene):
            cam.show_composition_golden = self.show_composition_golden  # type: ignore

    def update_show_composition_thirds(self, context: Context):
        """
        Set thirds composition on all cameras within the current scene.
        """
        for cam in self.get_all_cameras_in_scene(context.scene):
            cam.show_composition_thirds = self.show_composition_thirds  # type: ignore

    passepartout_alpha: EnumProperty(
        items=(
            ("0.0", "None", "Transparent", "PIVOT_BOUNDBOX", 0),
            ("0.5", "Half", "Translucent", "MOD_SUBSURF", 1),
            ("1.0", "Full", "Opaque", "MOD_MASK", 2),
        ),
        name="Passepartout",
        update=update_passepartout_alpha,
    )

    show_composition_center: BoolProperty(
        name="Center",
        update=update_show_composition_center,
    )

    show_composition_golden: BoolProperty(
        name="Golden",
        update=update_show_composition_golden,
    )

    show_composition_thirds: BoolProperty(
        name="Thirds",
        update=update_show_composition_thirds,
    )
