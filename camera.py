from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from typing import Iterator
    from bpy.types import Camera, Context, Object

import bpy
from bpy.props import BoolProperty, EnumProperty
from bpy.types import Scene, PropertyGroup

from . import catalog, logger


log = logger.get_logger(__name__)


@bpy.app.handlers.persistent
def hide_inactive_cameras(_):
    """
    Set camera visibilities.
    """
    # Don't do anything during playback to not affect performance
    if bpy.context.screen.is_animation_playing:
        return

    c = CameraSettings.this()
    if c.hide_inactive_cameras:
        c.update_hide_inactive_cameras(bpy.context)


@catalog.bpy_register
class CameraSettings(PropertyGroup):
    """Camera settings module"""

    module: str = "camera_settings"

    @classmethod
    def this(cls) -> CameraSettings:
        return bpy.context.scene.camera_settings  # type: ignore

    @classmethod
    def register(cls):
        """
        Register with scenes. Add handler to hide inactive cameras post frame change.
        """
        # Register as scene property
        setattr(Scene, cls.module, bpy.props.PointerProperty(type=cls))

        # Add handlers
        if hide_inactive_cameras not in bpy.app.handlers.frame_change_post:
            bpy.app.handlers.frame_change_post.append(hide_inactive_cameras)
        if hide_inactive_cameras not in bpy.app.handlers.animation_playback_post:
            bpy.app.handlers.animation_playback_post.append(hide_inactive_cameras)

    @classmethod
    def deregister(cls):
        """
        Remove handler to hide inactive cameras post frame change.
        """
        if hide_inactive_cameras in bpy.app.handlers.frame_change_post:
            bpy.app.handlers.frame_change_post.remove(hide_inactive_cameras)
        if hide_inactive_cameras in bpy.app.handlers.animation_playback_post:
            bpy.app.handlers.animation_playback_post.remove(hide_inactive_cameras)

    @staticmethod
    def get_all_cameras_in_scene(scene: Scene | None = None) -> Iterator[Object]:
        """
        Get all cameras in given scene.

        Args:
            scene (Scene | None): The scene to get the cameras from

        Returns:
            Iterator[Object]: Iterator of camera objects in scene
        """
        if not scene:
            scene = bpy.context.scene
        for obj in scene.collection.all_objects:
            if obj.type == "CAMERA":
                yield obj

    def update_passepartout_alpha(self, context: Context):
        """
        Set the passepartout on all cameras within the current scene.
        """
        for cam in self.get_all_cameras_in_scene(context.scene):
            cam.data.show_passepartout = True  # type: ignore
            cam.data.passepartout_alpha = float(self.passepartout_alpha)  # type: ignore

    def update_show_composition_center(self, context: Context):
        """
        Set center composition on all cameras within the current scene.
        """
        for cam in self.get_all_cameras_in_scene(context.scene):
            cam.data.show_composition_center = self.show_composition_center  # type: ignore

    def update_show_composition_golden(self, context: Context):
        """
        Set golden composition on all cameras within the current scene.
        """
        for cam in self.get_all_cameras_in_scene(context.scene):
            cam.data.show_composition_golden = self.show_composition_golden  # type: ignore

    def update_show_composition_thirds(self, context: Context):
        """
        Set thirds composition on all cameras within the current scene.
        """
        for cam in self.get_all_cameras_in_scene(context.scene):
            cam.data.show_composition_thirds = self.show_composition_thirds  # type: ignore

    def update_hide_inactive_cameras(self, context: Context):
        """
        Set camera visibilities.
        """
        # StoryLiner shot cameras
        if hasattr(context.scene, "WkStoryLiner_props"):
            cams = set()
            for take in context.scene.WkStoryLiner_props.takes:  # type: ignore
                for shot in take.shots:
                    if shot.camera:
                        cams.add(shot.camera)
        # Use all cameras in scene without StoryLiner
        else:
            cams = set(self.get_all_cameras_in_scene(context.scene))

        # Hide/unhide
        active_cam = context.scene.camera
        for cam in cams:
            if cam is active_cam:
                continue

            # Remove camera rig from pose mode to avoid pose lock
            if (
                self.hide_inactive_cameras
                and cam.parent
                and cam.parent is context.pose_object
            ):
                log.debug(f"{cam.parent.name} is in pose mode, removing.")
                bpy.ops.object.mode_set(mode="OBJECT")
                cam.parent.select_set(False)
                if context.selected_objects:
                    context.view_layer.objects.active = context.selected_objects[0]
                    bpy.ops.object.mode_set(mode="POSE")
                else:
                    log.debug(f"No other object found, staying in object mode.")

            cam.hide_viewport = self.hide_inactive_cameras  # type: ignore
            if cam.parent:  # type: ignore
                cam.parent.hide_viewport = self.hide_inactive_cameras  # type: ignore

        # Ensure active camera is visible
        active_cam.hide_viewport = False  # type: ignore
        if active_cam.parent:  # type: ignore
            active_cam.parent.hide_viewport = False  # type: ignore

    def set_up_camera(self, camera: Camera):
        """
        Set up given camera according to the scene settings.

        Args:
            camera (Camera): Camera data object
        """
        camera.show_passepartout = True  # type: ignore
        camera.passepartout_alpha = float(self.passepartout_alpha)  # type: ignore
        camera.show_composition_center = self.show_composition_center  # type: ignore
        camera.show_composition_thirds = self.show_composition_thirds  # type: ignore
        camera.show_composition_golden = self.show_composition_golden  # type: ignore

    hide_inactive_cameras: BoolProperty(
        name="Hide Inactive Cameras",
        description="Automatically hide all inactive cameras and rigs on frame change",
        update=update_hide_inactive_cameras,
    )

    passepartout_alpha: EnumProperty(
        items=(
            ("0.0", "None", "Transparent", "PIVOT_BOUNDBOX", 0),
            ("0.5", "Half", "Translucent", "MOD_SUBSURF", 1),
            ("1.0", "Full", "Opaque", "MOD_MASK", 2),
        ),
        name="Passepartout",
        description="Opacity (alpha) of the darkened overlay in camera view",
        default="0.5",
        update=update_passepartout_alpha,
    )

    show_composition_center: BoolProperty(
        name="Center",
        description="Display center composition guide inside the camera view",
        update=update_show_composition_center,
    )

    show_composition_golden: BoolProperty(
        name="Golden",
        description="Display golden ratio composition guide inside the camera view",
        update=update_show_composition_golden,
    )

    show_composition_thirds: BoolProperty(
        name="Thirds",
        description="Display rule of thirds composition guide inside the camera view",
        update=update_show_composition_thirds,
    )
