from __future__ import annotations

from typing import TYPE_CHECKING, Literal

if TYPE_CHECKING:
    from bpy.types import Context, Event, SoundStrip

import colorsys
import pprint
import random
import re
from pathlib import Path

import bpy
from bpy.props import (
    BoolProperty,
    CollectionProperty,
    EnumProperty,
    IntProperty,
    StringProperty,
)
from bpy.types import (
    Operator,
    OperatorFileListElement,
    OperatorProperties,
    Scene,
    Timer,
)
from bpy_extras.io_utils import ImportHelper

from . import (
    camera,
    casting,
    catalog,
    client,
    logger,
    schalotte,
    session,
    utils,
)

log = logger.get_logger(__name__)


OPERATOR_RETURN_ITEMS = set[
    Literal[
        "CANCELLED",
        "FINISHED",
        "INTERFACE",
        "PASS_THROUGH",
        "RUNNING_MODAL",
    ]
]


@catalog.bpy_register
class SCHALOTTETOOLS_OT_LogIn(Operator):
    """Log in to Kitsu"""

    bl_idname = "schalotte.log_in"
    bl_label = "Log In"
    bl_options = {"REGISTER"}

    @classmethod
    def poll(cls, context) -> bool:
        """
        Allow this operator only when host, username and password are set.

        Args:
            context (Context)

        Returns:
            bool: All properties are set
        """
        c = client.Client.this()
        return bool(c.host and c.username and c.password)

    def execute(self, context: Context) -> OPERATOR_RETURN_ITEMS:
        """
        Log in to Kitsu.

        Args:
            context (Context)

        Returns:
            set[str]: CANCELLED, FINISHED, INTERFACE, PASS_THROUGH, RUNNING_MODAL
        """
        user_dict = client.Client.this().log_in()
        if user_dict:
            log.debug("Logged in as:")
            log.debug(pprint.pprint(user_dict.get("user", {})))
            bpy.ops.wm.save_userpref()
            return {"FINISHED"}
        else:
            log.error("Failed to log in.")
            return {"CANCELLED"}


@catalog.bpy_register
class SCHALOTTETOOLS_OT_LogOut(Operator):
    """End the Kitsu session"""

    bl_idname = "schalotte.log_out"
    bl_label = "Log Out"
    bl_options = {"REGISTER"}

    @classmethod
    def poll(cls, context) -> bool:
        """
        Allow this operator only when logged in.

        Args:
            context (Context)

        Returns:
            bool: Whether the client is logged in or not.
        """
        return client.Client.this().is_logged_in

    def execute(self, context: Context) -> OPERATOR_RETURN_ITEMS:
        """
        End the active Kitsu login session.

        Args:
            context (Context)

        Returns:
            set[str]: CANCELLED, FINISHED, INTERFACE, PASS_THROUGH, RUNNING_MODAL
        """
        client.Client.this().log_out()
        log.info("Session ended.")
        return {"FINISHED"}


@catalog.bpy_register
class SCHALOTTETOOL_OT_CreateWorkFile(Operator):
    """Create a new work file"""

    bl_idname = "schalotte.create_work_file"
    bl_label = "Create Work File"
    bl_options = {"REGISTER"}

    mode: EnumProperty(
        items=(
            ("NEW", "Empty File", "Create a new empty file"),
            ("CURRENT", "Use Current", "Save the open file as a new work file"),
        ),
        name="Mode",
    )

    @classmethod
    def poll(cls, context) -> bool:
        """
        Only if the currently selected task has a work file path.

        Args:
            context (Context)

        Returns:
            bool: Session task has a work file path
        """
        return bool(session.Session.this().work_file_path)

    def invoke(self, context: Context, event: Event) -> OPERATOR_RETURN_ITEMS:
        """
        Set mode based on work file and draw UI.

        Args:
            context (Context)
            event (Event)

        Returns:
            set[str]: CANCELLED, FINISHED, INTERFACE, PASS_THROUGH, RUNNING_MODAL
        """
        if bpy.data.filepath:
            self.mode = "CURRENT"
            return context.window_manager.invoke_props_dialog(self)
        self.mode = "NEW"
        return self.execute(context)

    def draw(self, context: Context):
        """
        Draw the operator UI.

        Args:
            context (Context)
        """
        self.layout.row().prop(self, "mode", expand=True)

    def execute(self, context: Context) -> OPERATOR_RETURN_ITEMS:
        """
        Create an empty file or save the current one to the work file path.

        Args:
            context (Context)

        Returns:
            set[str]: CANCELLED, FINISHED, INTERFACE, PASS_THROUGH, RUNNING_MODAL
        """
        file_path = session.Session.this().work_file_path

        # Empty file
        if self.mode == "NEW":
            bpy.ops.wm.read_homefile(load_ui=False, use_empty=True)

        # Create parent directories
        Path(file_path).parent.mkdir(parents=True, exist_ok=True)

        # Save work file
        bpy.ops.wm.save_as_mainfile(filepath=file_path)
        return {"FINISHED"}


@catalog.bpy_register
class SCHALOTTETOOL_OT_RenderPreview(Operator):
    """Render or playblast a preview"""

    bl_idname = "schalotte.render_preview"
    bl_label = "Render Preview"
    bl_options = {"REGISTER"}

    mode: EnumProperty(
        items=(
            ("PLAYBLAST", "Playblast", "OpenGL workbench playblast"),
            ("RENDER", "Render", "Render using scene settings"),
        ),
        name="Mode",
    )
    range: EnumProperty(
        items=(
            ("SCENE", "Scene", "Full scene"),
            ("SHOT", "Shot", "Current shot based on camera markers"),
        ),
        name="Range",
    )
    quality: EnumProperty(
        items=(
            ("LOW", "Low", "Low quality for fast passes"),
            ("MEDIUM", "Medium", "Medium sampling/AA quality"),
            ("HIGH", "High", "High quality sampling/AA (slow)"),
            ("CUSTOM", "From Scene", "Use settings from the current scene"),
        ),
        name="Quality",
    )
    use_playback: BoolProperty(name="Play After Rendering", default=True)
    use_stamp: BoolProperty(name="Use Burn-in Stamp", default=True)

    _is_modal: bool = False
    _file_path: Path
    _rendering: bool = False
    _render_display_type: Literal["NONE", "SCREEN", "AREA", "WINDOW"]
    _scene_tracker: utils.PropTracker
    _timer: Timer | None = None

    def _render_stop_handler(self, scene: Scene, _=None):
        """Mark if rendering has stopped"""
        log.debug("Render stop detected.")
        self._rendering = False

    @classmethod
    def poll(cls, context) -> bool:
        """
        Allow only file is saved, the client is logged in and a task is selected.

        Args:
            context (Context)

        Returns:
            bool: File is saved, client logged in and task selected
        """
        return client.Client.this().is_logged_in and bool(
            bpy.data.filepath and session.Session.this().task
        )

    def invoke(self, context: Context, event: Event) -> OPERATOR_RETURN_ITEMS:
        """
        Invoke the properties dialog.

        Args:
            context (Context)
            event (Event)

        Returns:
            set[str]: CANCELLED, FINISHED, INTERFACE, PASS_THROUGH, RUNNING_MODAL
        """
        self._is_modal = True
        return context.window_manager.invoke_props_dialog(self)

    def draw(self, context: Context):
        """
        Draw operator properties.

        Args:
            context (Context)
        """
        layout = self.layout
        col = layout.column()
        col.use_property_split = True
        col.row().prop(self, "mode", expand=True)
        col.row().prop(self, "range", expand=True)
        col.row().prop(self, "quality")
        col.row().prop(self, "use_stamp")
        col.row().prop(self, "use_playback")

    def modal(self, context: Context, event: Event) -> OPERATOR_RETURN_ITEMS:
        """Handle modal events"""

        # Check if rendering is complete
        if not self._rendering:
            self.finish(context)
            log.debug("Render modal stopped.")
            return {"FINISHED"}

        # Pass escape to the render operator
        if event.type == "ESC":
            log.debug("Escape pressed.")
            return {"PASS_THROUGH"}

        return {"RUNNING_MODAL"}

    def execute(self, context: Context) -> OPERATOR_RETURN_ITEMS:
        """
        Render the shot.

        Args:
            context (Context)

        Returns:
            set[str]: CANCELLED, FINISHED, INTERFACE, PASS_THROUGH, RUNNING_MODAL
        """
        scene = context.scene

        # Backup
        self._render_display_type = context.preferences.view.render_display_type
        self._scene_tracker = utils.PropTracker(scene)  # type: ignore

        # Find name, start and end frame of current shot marker
        shot_suffix = ""
        if self.range == "SHOT":
            shot_name, shot_start, shot_end = schalotte.get_marker_shot_range(scene)
            shot_suffix = f"_{shot_name}"

            # Set scene frame range to shot
            self._scene_tracker.set(frame_start=shot_start, frame_end=shot_end)

        # Render preview
        blend_path = Path(bpy.data.filepath)
        file_name = blend_path.stem + shot_suffix
        previews_path = blend_path.parent / "previews"
        file_path = previews_path / f"{file_name}.mp4"
        if file_path.exists():
            for i in range(1, 999):
                file_path = previews_path / f"{file_name}_{i:03d}.mp4"
                if not file_path.exists():
                    break
            else:
                log.error("Could not find available video file path.")
                return {"CANCELLED"}

        # Set UI
        context.preferences.view.render_display_type = "NONE"

        # Add handlers
        if (
            self.use_stamp
            and schalotte.set_stamp not in bpy.app.handlers.frame_change_post
        ):
            log.debug("Adding stamp handler.")
            bpy.app.handlers.frame_change_post.append(schalotte.set_stamp)
        if self._render_stop_handler not in bpy.app.handlers.render_cancel:
            log.debug("Adding render cancel handler.")
            bpy.app.handlers.render_cancel.append(self._render_stop_handler)
        if self._render_stop_handler not in bpy.app.handlers.render_complete:
            log.debug("Adding render complete handler.")
            bpy.app.handlers.render_complete.append(self._render_stop_handler)

        # Prepare rendering
        log.info(f"Rendering video to {file_path}")
        self._file_path = file_path
        self._rendering = True
        utils.apply_render_settings(scene, self._scene_tracker)
        self._scene_tracker.set(
            render__filepath=file_path.as_posix(),
            render__use_file_extension=True,
        )

        # Set workbench
        if self.mode == "PLAYBLAST":
            self._scene_tracker.set(render__engine="BLENDER_WORKBENCH")

        # Set quality
        match scene.render.engine:
            case "BLENDER_EEVEE":
                match self.quality:
                    case "LOW":
                        self._scene_tracker.set(eevee__taa_samples=2)
                    case "MEDIUM":
                        self._scene_tracker.set(eevee__taa_samples=6)
                    case "HIGH":
                        self._scene_tracker.set(eevee__taa_samples=12)

            case "BLENDER_WORKBENCH":
                match self.quality:
                    case "LOW":
                        self._scene_tracker.set(display__render_aa="OFF")
                    case "MEDIUM":
                        self._scene_tracker.set(display__render_aa="FXAA")
                    case "HIGH":
                        self._scene_tracker.set(display__render_aa="5")

            case "CYCLES":
                match self.quality:
                    case "LOW":
                        self._scene_tracker.set(cycles__samples=2)
                    case "MEDIUM":
                        self._scene_tracker.set(cycles__samples=12)
                    case "HIGH":
                        self._scene_tracker.set(cycles__samples=24)

        # Render
        file_path.parent.mkdir(parents=True, exist_ok=True)
        bpy.ops.render.render(
            "INVOKE_DEFAULT" if self._is_modal else "EXEC_DEFAULT",
            animation=True,
            use_viewport=False,
            scene=scene.name,
        )
        if not self._is_modal:
            self.finish(context)
            return {"FINISHED"}

        # Start modal
        wm = context.window_manager
        self._timer = wm.event_timer_add(0.1, window=context.window)
        wm.modal_handler_add(self)
        self._rendering = True

        return {"RUNNING_MODAL"}

    def finish(self, context: Context):
        # Remove timer
        if self._timer:
            log.debug("Removing timer.")
            wm = context.window_manager
            wm.event_timer_remove(self._timer)

        # Remove handlers
        if schalotte.set_stamp in bpy.app.handlers.frame_change_post:
            log.debug("Removing stamp handler.")
            bpy.app.handlers.frame_change_post.remove(schalotte.set_stamp)
        if self._render_stop_handler in bpy.app.handlers.render_cancel:
            log.debug("Removing render cancel handler.")
            bpy.app.handlers.render_cancel.remove(self._render_stop_handler)
        if self._render_stop_handler in bpy.app.handlers.render_complete:
            log.debug("Removing render complete handler.")
            bpy.app.handlers.render_complete.remove(self._render_stop_handler)

        # Restore props
        context.preferences.view.render_display_type = self._render_display_type
        self._scene_tracker.revert()

        # Open rendered video
        if self.use_playback:
            log.debug("Starting playback")
            bpy.ops.wm.path_open(filepath=self._file_path.as_posix())


@catalog.bpy_register
class SCHALOTTETOOL_OT_UploadPreview(Operator):
    """Render a preview and upload it to selected task"""

    bl_idname = "schalotte.upload_preview"
    bl_label = "Upload Preview"
    bl_options = {"REGISTER"}

    def enum_task_status_ids(
        self,
        context: Context | None,
    ) -> list[tuple[str, str, str]]:
        """
        Enumerate task status items.
        """
        task_statuses = client.Client.this().fetch_list(
            "task-status",
            {"is_feedback_request": True},
        )
        if not task_statuses:
            return [("NONE", "None", "No task status selected")]

        return [(ts["id"], ts["name"], ts["id"]) for ts in task_statuses]

    def enum_video_path(
        self,
        context: Context | None,
    ) -> list[tuple[str, str, str]]:
        """
        Enumerate available preview files.
        """
        preview_files = []

        preview_path = Path(bpy.data.filepath).parent / "previews"
        if preview_path.exists():
            files = list(preview_path.glob("*.mp4"))
            # Sort by modification date
            for file in sorted(files, key=lambda f: f.stat().st_mtime, reverse=True):
                preview_files.append((file.as_posix(), file.stem, file.name))

        return preview_files

    video_path: EnumProperty(name="Video File", items=enum_video_path)
    task_status_id: EnumProperty(name="Task Status", items=enum_task_status_ids)
    comment: StringProperty(name="Comment")

    @classmethod
    def poll(cls, context) -> bool:
        """
        Allow only file is saved, the client is logged in and a task is selected.

        Args:
            context (Context)

        Returns:
            bool: File is saved, client logged in and task selected
        """
        return client.Client.this().is_logged_in and bool(
            bpy.data.filepath and session.Session.this().task
        )

    def invoke(self, context: Context, event: Event) -> OPERATOR_RETURN_ITEMS:
        """
        Invoke the properties dialog.

        Args:
            context (Context)
            event (Event)

        Returns:
            set[str]: CANCELLED, FINISHED, INTERFACE, PASS_THROUGH, RUNNING_MODAL
        """
        if not self.enum_video_path(context):
            msg = "No video files rendered."
            log.error(msg)
            self.report({"WARNING"}, msg)
            return {"CANCELLED"}

        return context.window_manager.invoke_props_dialog(self)

    def execute(self, context: Context) -> OPERATOR_RETURN_ITEMS:
        """
        Create a new comment and upload selected video to it.

        Args:
            context (Context)

        Returns:
            set[str]: CANCELLED, FINISHED, INTERFACE, PASS_THROUGH, RUNNING_MODAL
        """
        if self.task_status_id == "NONE":
            log.error("No task status for feedback request found.")
            return {"CANCELLED"}

        c = client.Client.this()

        # Create new comment
        log.info("Creating a new comment.")
        task_id = session.Session.this().task_id
        data = {"task_status_id": self.task_status_id, "comment": self.comment}
        comment = c.post(f"actions/tasks/{task_id}/comment", data)

        #

        # Upload preview
        log.info("Creating a new preview.")
        preview = c.post(
            f"actions/tasks/{task_id}/comments/{comment['id']}/add-preview",
            {},
        )
        log.info(f"Uploading video to preview {preview['id']}")
        c.upload(
            f"pictures/preview-files/{preview['id']}?normalize=false",
            self.video_path,
        )

        return {"FINISHED"}


@catalog.bpy_register
class SCHALOTTETOOL_OT_SetupStoryboard(Operator):
    """Set up the current scene for storyboarding"""

    bl_idname = "schalotte.setup_storyboard"
    bl_label = "Storyboard Setup"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context: Context) -> OPERATOR_RETURN_ITEMS:
        """
        Set up the current scene for storyboarding tasks.

        Args:
            context (Context)

        Returns:
            set[str]: CANCELLED, FINISHED, INTERFACE, PASS_THROUGH, RUNNING_MODAL
        """
        scene = context.scene
        schalotte.setup_storyboard(scene)
        if hasattr(scene, "WkStoryLiner_props"):
            schalotte.setup_storyliner(scene)
        else:
            msg = "Storyliner is not enabled, skipping setup."
            self.report({"WARNING"}, msg)
            log.warning(msg)
        bpy.ops.file.make_paths_relative()
        return {"FINISHED"}


@catalog.bpy_register
class SCHALOTTETOOL_OT_GuessSessionFromFilepath(Operator):
    """Guess the current session task context from the file path"""

    bl_idname = "schalotte.guess_session_from_filepath"
    bl_label = "Guess From File Path"
    bl_options = {"REGISTER"}

    @classmethod
    def poll(cls, context) -> bool:
        """
        Only if the current file is saved.

        Args:
            context (Context)

        Returns:
            bool: File is saved
        """
        return bool(bpy.data.filepath)

    def execute(self, context: Context) -> OPERATOR_RETURN_ITEMS:
        """
        Guess the current session task context from the file path.

        Args:
            context (Context)

        Returns:
            set[str]: CANCELLED, FINISHED, INTERFACE, PASS_THROUGH, RUNNING_MODAL
        """
        session.Session.this().guess_from_filepath()
        return {"FINISHED"}


@catalog.bpy_register
class SCHALOTTETOOL_OT_AddSoundStrips(Operator, ImportHelper):  # type: ignore
    """Import selected audio strips into the sequencer"""

    bl_idname = "schalotte.add_sound_strips"
    bl_label = "Import Audio Takes"
    bl_options = {"REGISTER", "UNDO"}

    directory: StringProperty(name="Directory", subtype="DIR_PATH")
    files: CollectionProperty(
        name="File Paths",
        type=OperatorFileListElement,
        options={"HIDDEN", "SKIP_SAVE"},
    )
    filter_glob: StringProperty(
        default=f"*{';*'.join(bpy.path.extensions_audio)}",  # type: ignore
        options={"HIDDEN"},
    )
    use_current_frame: BoolProperty(name="Use Current Frame")
    relative_path: BoolProperty(name="Relative Path", default=True)
    skip_existing: BoolProperty(name="Skip Existing", default=True)

    def invoke(self, context: Context, event: Event) -> OPERATOR_RETURN_ITEMS:  # type: ignore
        """
        Start folder selection.

        Parameters:
            - context (Context)
            - event (Event)

        Returns:
            - set[str]: CANCELLED, FINISHED, INTERFACE, PASS_THROUGH, RUNNING_MODAL
        """
        file_path = bpy.data.filepath
        audio_path = schalotte.generate_sound_path(session.Session.this().sequence_id)
        if not audio_path and file_path:
            audio_path = Path(file_path).parents[1]
        if audio_path:
            layout_takes = audio_path / "layout_takes"
            if layout_takes.is_dir():
                self.directory = layout_takes.as_posix()
            else:
                self.directory = Path(audio_path).as_posix()
        context.window_manager.fileselect_add(self)
        return {"RUNNING_MODAL"}

    def execute(self, context: Context) -> OPERATOR_RETURN_ITEMS:
        """
        Import selected audio strips into the sequencer

        Args:
            context (Context)

        Returns:
            set[str]: CANCELLED, FINISHED, INTERFACE, PASS_THROUGH, RUNNING_MODAL
        """
        # Get sequencer
        sequence_editor = context.scene.sequence_editor_create()

        # Get channel
        channel = utils.get_sequencer_max_channel(context.scene) + 1

        # Get start frame
        if self.use_current_frame:
            current_frame = context.scene.frame_current
        else:
            current_frame = context.scene.frame_start

        # Collect existing paths
        if self.skip_existing:
            existing_paths = {
                Path(bpy.path.abspath(strip.sound.filepath)).resolve()  # type: ignore
                for strip in sequence_editor.strips
                if strip.type == "SOUND"
            }
        else:
            existing_paths = {}

        for file in self.files:
            file_path = Path(self.directory, file.name)

            # Check if already imported
            if file_path.resolve() in existing_paths:
                log.info(f"Skipping existing file: {file_path}")
                continue

            # Check if the file exists
            if not file_path.is_file():
                log.error(f"{file_path} does not exist")
                continue

            # Make relative
            filepath = file_path.as_posix()
            if self.relative_path:
                filepath = bpy.path.relpath(filepath)

            # Create strip
            sequence = sequence_editor.strips.new_sound(
                name=file_path.stem,
                filepath=filepath,
                channel=channel,
                frame_start=current_frame,
            )
            current_frame = sequence.frame_final_end

        return {"FINISHED"}


@catalog.bpy_register
class SCHALOTTETOOL_OT_FetchCasting(Operator):
    """Fetch the casting for the selected shot"""

    bl_idname = "schalotte.fetch_casting"
    bl_label = "Fetch Casting"
    bl_options = {"REGISTER"}

    @classmethod
    def poll(cls, context) -> bool:
        """
        Allow only if a project and a shot are selected.

        Args:
            context (Context)

        Returns:
            bool: Project and shot are selected
        """
        s = session.Session.this()
        return bool(s.project and s.shot)

    def execute(self, context: Context) -> OPERATOR_RETURN_ITEMS:
        """
        Fetch the casting for the selected shot.

        Args:
            context (Context)

        Returns:
            set[str]: CANCELLED, FINISHED, INTERFACE, PASS_THROUGH, RUNNING_MODAL
        """
        s = session.Session.this()
        casting.Casting.this().fetch_entity_breakdown(s.project_id, s.shot_id)
        return {"FINISHED"}


@catalog.bpy_register
class SCHALOTTETOOL_OT_ImportAsset(Operator):
    bl_idname = "schalotte.import_asset"
    bl_label = "Import Asset"
    bl_options = {"REGISTER", "UNDO"}

    index: IntProperty(default=-1)
    mode: EnumProperty(
        items=(
            (
                "AUTO",
                "Staging-based",
                "Select based on 'animate' label",
                "SPREADSHEET",
                0,
            ),
            (
                "INSTANCE",
                "Instance",
                "Create instancer object",
                "EMPTY_AXIS",
                1,
            ),
            (
                "STATIC_OVERRIDE",
                "Static Override",
                "Create a static override",
                "LIBRARY_DATA_OVERRIDE_NONEDITABLE",
                2,
            ),
            (
                "EDITABLE_OVERRIDE",
                "Editable Override",
                "Create a fully editable override",
                "LIBRARY_DATA_OVERRIDE",
                3,
            ),
            (
                "APPEND",
                "Append",
                "Append as fully localized asset",
                "APPEND_BLEND",
                4,
            ),
        ),
        name="Mode",
        default="EDITABLE_OVERRIDE",
    )

    @classmethod
    def description(cls, context: Context, properties: OperatorProperties) -> str:
        match properties.mode:
            case "INSTANCE":
                return "Instantiate a cast asset to the scene"
            case "STATIC_OVERRIDE":
                return "Create a static override for a cast asset"
            case "EDITABLE_OVERRIDE":
                return "Create a fully animatable override for a cast asset"
            case "APPEND":
                return "Append a cast asset to the scene"
            case _:
                return "Import a cast asset to the scene, based on its staging state"

    @classmethod
    def poll(cls, context) -> bool:
        """
        Allow only if a project and a shot are selected.

        Args:
            context (Context)

        Returns:
            bool: Project and shot are selected
        """
        return bool(casting.Casting.this().links)

    def execute(self, context: Context) -> OPERATOR_RETURN_ITEMS:
        """
        Fetch the casting for the selected shot.

        Args:
            context (Context)

        Returns:
            set[str]: CANCELLED, FINISHED, INTERFACE, PASS_THROUGH, RUNNING_MODAL
        """
        c = casting.Casting.this()

        # All unlinked assets
        if self.index == -1:
            links = [
                link for link in c.links if link.file_path and not link.library_name
            ]

        # Single asset
        else:
            links = [c.links[self.index]]

        # Link based on mode
        for link in links:
            asset = None
            match self.mode:
                case "AUTO":
                    if link.label == "animate":
                        asset = link.add_override(make_editable=True)
                    else:
                        asset = link.add_instance()
                case "INSTANCE":
                    asset = link.add_instance()
                case "STATIC_OVERRIDE":
                    asset = link.add_override(make_editable=False)
                case "EDITABLE_OVERRIDE":
                    asset = link.add_override(make_editable=True)
                case "APPEND":
                    asset = link.append()

            # Report if failed
            if not asset:
                msg = f"Unable to link asset {link.asset_name}"
                log.error(msg)
                self.report({"ERROR"}, msg)

        bpy.ops.file.make_paths_relative()
        return {"FINISHED"}


@catalog.bpy_register
class SCHALOTTETOOL_OT_SelectPoseBones(Operator):
    """Select pose bones of an object"""

    bl_idname = "schalotte.select_pose_bones"
    bl_label = "Select Pose Bones"
    bl_options = {"REGISTER", "UNDO"}

    object_name: StringProperty(name="Object Name")
    bone_names: StringProperty(name="Pose Bones")
    clear: BoolProperty(name="Clear Selection")

    def execute(self, context: Context) -> OPERATOR_RETURN_ITEMS:
        """
        Select pose bones of an armature object.

        Args:
            context (Context)

        Returns:
            set[str]: CANCELLED, FINISHED, INTERFACE, PASS_THROUGH, RUNNING_MODAL
        """
        obj = bpy.data.objects.get(self.object_name)
        if not obj:
            msg = f"{self.object_name} not found"
            log.error(msg)
            self.report({"ERROR"}, msg)
            return {"CANCELLED"}

        bone_names = utils.string_to_list(self.bone_names)

        try:
            utils.select_pose_bones(obj, bone_names, self.clear, context)
        except RuntimeError:
            msg = f"{obj.name} is not selectable."
            log.error(msg)
            self.report({"ERROR"}, msg)
            return {"CANCELLED"}

        return {"FINISHED"}


@catalog.bpy_register
class SCHALOTTETOOL_OT_FixStoryboardNames(Operator):
    """Reorder shots and rename all names to match the shot order"""

    bl_idname = "schalotte.fix_storyboard_names"
    bl_label = "Fix Storyboard Names"
    bl_options = {"REGISTER", "UNDO"}

    sort_shots: BoolProperty(name="Sort StoryLiner Shots", default=True)
    rename_shots: BoolProperty(name="Rename Shots", default=True)

    def execute(self, context: Context) -> OPERATOR_RETURN_ITEMS:
        """
        Sort StoryLiner shots, rename collections, cameras, rigs, data and actions to
        match the new shot order.

        Args:
            context (Context)

        Returns:
            set[str]: CANCELLED, FINISHED, INTERFACE, PASS_THROUGH, RUNNING_MODAL
        """
        # Sort shots
        if self.sort_shots:
            if hasattr(context.scene, "WkStoryLiner_props"):
                schalotte.sort_storyliner_shots(context.scene)

        # Rename shots
        if self.rename_shots:
            if hasattr(context.scene, "WkStoryLiner_props"):
                schalotte.rename_storyliner_shots(context.scene)
            else:
                # Rename markers
                shot_nb = 0
                for marker in sorted(
                    context.scene.timeline_markers,
                    key=lambda x: x.frame,
                ):
                    if marker.camera:
                        shot_nb += 1
                        marker.name = f"sh{shot_nb:03d}0"

        # Fix camera rig names
        schalotte.fix_cam_rig_names(context.scene)
        # Run twice to ensure unique names
        schalotte.fix_cam_rig_names(context.scene)

        return {"FINISHED"}


@catalog.bpy_register
class SCHALOTTETOOL_OT_AddShot(Operator):
    bl_idname = "schalotte.add_shot"
    bl_label = "Add Shot"
    bl_options = {"REGISTER", "UNDO"}

    use_current_camera: BoolProperty(name="Use Current Camera", default=True)

    @classmethod
    def description(cls, context: Context, properties: OperatorProperties) -> str:
        if properties.use_current_camera:
            return "Add a new shot based on the current camera"
        else:
            return "Add a new shot without camera transforms"

    def execute(self, context: Context) -> OPERATOR_RETURN_ITEMS:
        """
        Append a new camera and create a new StoryLiner shot.

        Args:
            context (Context)

        Returns:
            set[str]: CANCELLED, FINISHED, INTERFACE, PASS_THROUGH, RUNNING_MODAL
        """
        scene = context.scene

        # Append a new camera rig
        new_col, new_rig, new_cam = schalotte.ensure_camera_rig(scene, True)
        if not new_rig or not new_cam:
            msg = "Failed to append camera rig."
            self.report({"ERROR"}, msg)
            log.error(msg)
            return {"CANCELLED"}

        current_rig = None

        # StoryLiner
        if hasattr(scene, "WkStoryLiner_props"):
            props = scene.WkStoryLiner_props  # type: ignore

            # Find the current camera's rig
            if self.use_current_camera:
                try:
                    current_rig = props.getCurrentShot().camera.parent
                except AttributeError:
                    log.error("Unable to not find the current shot's camera rig.")

            # Create the StoryLiner shot
            frame_start = 1
            for shot in props.getShotsList():
                if shot.end > frame_start:
                    frame_start = shot.end + 1
            nb_shots = len(props.getShotsList())
            sh_name = props.getShotPrefix((nb_shots + 1) * 10)

            props.addShot(  # type: ignore
                name=sh_name,
                start=frame_start,
                end=frame_start + 50,
                camera=new_cam,
                color=colorsys.hsv_to_rgb(random.random(), 0.9, 1.0) + (1.0,),
            )
            cam_name = f"cam_{props.sequence_name}_{sh_name}"

        # Camera markers
        else:
            if self.use_current_camera:
                try:
                    current_rig = scene.camera.parent
                except AttributeError:
                    log.error("Unable to not find the current shot's camera rig.")

            # Get last camera marker frame and shot name
            marker_pattern = re.compile(r"sh(\d+)")

            sh_name = None
            frame_start = None
            for marker in scene.timeline_markers:
                if marker.camera:
                    name_match = re.findall(marker_pattern, marker.name)
                    if name_match:
                        sh_name = name_match[0]
                    frame_start = marker.frame

            # Set frame start to 1 if not found
            if frame_start is None:
                frame_start = 1
            # ... use current frame if after last shot, or offset last by 50
            else:
                if scene.frame_current > frame_start:
                    frame_start = scene.frame_current
                else:
                    frame_start += 50

            # Use first shot name or increase by one
            if sh_name is None:
                sh_name = "sh0010"
            else:
                sh_name = f"sh{int(sh_name) + 10:04d}"

            # Create the camera marker
            new_marker = scene.timeline_markers.new(
                name=sh_name,
                frame=frame_start,
            )
            new_marker.camera = new_cam

            # Add sequence name for camera
            cam_name = "cam_"
            sequence = session.Session.this().sequence
            if sequence:
                sq_name = sequence.get("name")
                if sq_name:
                    cam_name += f"{sq_name.lower()}_"
            cam_name += sh_name

        # Rename the new camera
        schalotte.rename_cam_rig(new_cam, cam_name, new_col)

        # Camera settings
        camera.CameraSettings.this().set_up_camera(new_cam.data)  # type: ignore

        # Copy the current camera's rig pose
        if current_rig:
            utils.copy_pose(current_rig, new_rig)

        # Go to the new shot
        context.scene.frame_current = frame_start

        return {"FINISHED"}


@catalog.bpy_register
class SCHALOTTETOOL_OT_RemoveStoryLinerGaps(Operator):
    """Remove all StoryLiner gaps and overlaps to make the sequence perfectly linear"""

    bl_idname = "schalotte.remove_storyliner_gaps"
    bl_label = "Remove Shot Gaps"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context) -> bool:
        """
        Only if StoryLiner is active.

        Args:
            context (Context)

        Returns:
            bool: Scene has StoryLiner properties
        """
        return hasattr(context.scene, "WkStoryLiner_props")

    def execute(self, context: Context) -> OPERATOR_RETURN_ITEMS:
        """
        Remove gaps between StoryLiner shots.

        Args:
            context (Context)

        Returns:
            set[str]: CANCELLED, FINISHED, INTERFACE, PASS_THROUGH, RUNNING_MODAL
        """
        schalotte.remove_storyliner_shot_gaps(context)
        return {"FINISHED"}


@catalog.bpy_register
class SCHALOTTETOOL_OT_CollectSoundFiles(Operator):
    """Move and/or unpack all external sound files"""

    bl_idname = "schalotte.collect_sound_files"
    bl_label = "Collect Sound Files"
    bl_options = set()

    dir_name: StringProperty(
        name="Directory Name",
        description="Name of the target directory next to the current file",
        default="layout_sounds",
    )
    mode: EnumProperty(
        items=(
            ("NONE", "None", "Do not relocate sound files"),
            ("COPY", "Copy", "Copy external files"),
            ("MOVE", "Move", "Move external sound files"),
        ),
        name="Relocation Mode",
        description="The way external files are relocated to their new location",
        default="COPY",
    )
    unpack: BoolProperty(
        name="Unpack",
        description="Unpack all packed sound files",
        default=True,
    )
    expand_external: BoolProperty(
        name="Expand External",
        description="Display external strips list",
    )
    expand_packed: BoolProperty(
        name="Expand Packed",
        description="Display packed strips list",
    )
    external_sounds: set[str] = set()
    packed_sounds: set[str] = set()

    @classmethod
    def poll(cls, context) -> bool:
        """
        Allow only if file is saved and project root is set.

        Args:
            context (Context)

        Returns:
            bool: Project root is set.
        """
        return bool(bpy.data.filepath and session.Session.this().sequence)

    def invoke(self, context: Context, event: Event) -> OPERATOR_RETURN_ITEMS:  # type: ignore
        """
        Check for external sounds.

        Parameters:
            - context (Context)
            - event (Event)

        Returns:
            - set[str]: CANCELLED, FINISHED, INTERFACE, PASS_THROUGH, RUNNING_MODAL
        """
        self.external_sounds.clear()
        scene = context.scene

        # Collect external sound strip file paths
        root_path = schalotte.generate_sound_path(session.Session.this().sequence_id)
        for sound_strip in schalotte.get_external_sound_strips(root_path, scene):
            self.external_sounds.add(sound_strip.sound.filepath)

        # Collect packed sound strip file paths
        for sound_strip in utils.get_packed_sound_strips(scene):
            self.packed_sounds.add(sound_strip.sound.filepath)

        # Finish if none found
        if not self.external_sounds and not self.packed_sounds:
            self.report({"INFO"}, "No external sounds found.")
            return {"FINISHED"}

        return context.window_manager.invoke_props_dialog(self)

    def draw(self, context: Context):
        """
        Draw properties and an expandable lists of files to be relocated and unpacked.

        Args:
            context (Context)
        """
        layout = self.layout
        col = layout.column()

        # Relocate
        if self.external_sounds:
            box_reloc = col.box()
            row_reloc = box_reloc.row()
            if self.mode != "NONE":
                if utils.show_layout(
                    layout=row_reloc,
                    data=self,
                    property="expand_external",
                    text="",
                ):
                    for external_path in sorted(list(self.external_sounds)):
                        box_reloc.row().label(text=Path(external_path).name, icon="DOT")
            else:
                row_reloc_disabled = row_reloc.row()
                row_reloc_disabled.enabled = False
                row_reloc_disabled.label(text="", icon="RIGHTARROW")
            row_reloc_enum = row_reloc.row(align=True)
            if self.packed_sounds:
                row_reloc_enum.prop_enum(self, "mode", "NONE")
            row_reloc_enum.prop_enum(self, "mode", "COPY")
            row_reloc_enum.prop_enum(self, "mode", "MOVE")

        # Unpack
        if self.packed_sounds:
            box_unpack = col.box()
            row_unpack = box_unpack.row()
            if self.unpack:
                if utils.show_layout(
                    layout=row_unpack,
                    data=self,
                    property="expand_packed",
                    text="" if self.external_sounds else "Unpack",
                ):
                    for packed_path in sorted(list(self.packed_sounds)):
                        box_unpack.row().label(text=Path(packed_path).name, icon="DOT")
            else:
                row_unpack_disabled = row_unpack.row()
                row_unpack_disabled.enabled = False
                row_unpack_disabled.label(text="", icon="RIGHTARROW")
            if self.external_sounds:
                row_unpack.prop(self, "unpack")

    def execute(self, context: Context) -> OPERATOR_RETURN_ITEMS:
        """
        Relocate all external sound strips and unpack them if selected.

        Args:
            context (Context)

        Returns:
            set[str]: CANCELLED, FINISHED, INTERFACE, PASS_THROUGH, RUNNING_MODAL
        """
        if TYPE_CHECKING:
            sound_strip: SoundStrip

        if self.mode == "NONE" and not self.unpack:
            self.report({"ERROR_INVALID_INPUT"}, "No operation selected.")
            return {"CANCELLED"}

        scene = context.scene
        root_path = schalotte.generate_sound_path(session.Session.this().sequence_id)
        if not root_path:
            log.error("Could not determine sound path.")
            return {"CANCELLED"}

        if not self.mode == "NONE":
            for sound_strip in schalotte.get_external_sound_strips(root_path, scene):
                if Path(sound_strip.sound.filepath).stem.startswith("Sch_ep"):
                    directory = root_path / "layout_takes"
                else:
                    directory = root_path / "layout_sfx"
                utils.move_datablock_filepath(
                    sound_strip.sound,  # type: ignore
                    directory,
                    relative=True,
                    copy=True if self.mode == "COPY" else False,
                    overwrite=False,
                )
        if self.unpack:
            for sound_strip in utils.get_packed_sound_strips(scene):
                sound_strip.sound.unpack(method="USE_ORIGINAL")

        return {"FINISHED"}


@catalog.bpy_register
class SCHALOTTETOOL_OT_SetMarkerShotPreviewRange(Operator):
    """Set preview range to the current camera marker shot"""

    bl_idname = "schalotte.set_marker_shot_preview_range"
    bl_label = "Set Marker Shot Preview Range"
    bl_options = {"REGISTER", "UNDO"}

    use_toggle: BoolProperty(
        name="Toggle",
        description="Unset if current preview range matches current shot",
        default=True,
    )

    def execute(self, context: Context) -> OPERATOR_RETURN_ITEMS:
        """
        Set or unset preview range to current camera marker shot.

        Args:
            context (Context)

        Returns:
            set[str]: CANCELLED, FINISHED, INTERFACE, PASS_THROUGH, RUNNING_MODAL
        """
        scene = context.scene
        _, start_frame, end_frame = schalotte.get_marker_shot_range(scene)

        # Disable if already set
        if (
            self.use_toggle
            and scene.use_preview_range
            and scene.frame_preview_end == end_frame
            and scene.frame_preview_start == start_frame
        ):
            scene.use_preview_range = False
        else:
            scene.use_preview_range = True
            scene.frame_preview_start = start_frame
            scene.frame_preview_end = end_frame

        return {"FINISHED"}


@catalog.bpy_register
class SCHALOTTETOOL_OT_KeyframeAllRigs(Operator):
    """Set keyframes for all rigs in the current scene"""

    bl_idname = "schalotte.keyframe_all_rigs"
    bl_label = "Keyframe All Rigs"
    bl_options = {"REGISTER", "UNDO"}

    armatures: EnumProperty(
        items=(
            ("ALL", "All", "All rigs found in the current scene"),
            ("SELECTED", "Selected", "Only selected rigs"),
        ),
        name="Rigs",
        description="Which rigs to set all keys for",
    )
    frame: EnumProperty(
        items=(
            ("ZERO", "Zero", "Set the keyframe on frame 0"),
            ("CURRENT", "Current", "Set the keyframe on the current frame"),
        ),
        name="Frame",
        description="On which frame the new keyframes are set",
    )

    def invoke(self, context: Context, event: Event) -> OPERATOR_RETURN_ITEMS:
        """
        Invoke the properties dialog.

        Args:
            context (Context)
            event (Event)

        Returns:
            set[str]: CANCELLED, FINISHED, INTERFACE, PASS_THROUGH, RUNNING_MODAL
        """
        return context.window_manager.invoke_props_dialog(self)

    def draw(self, context: Context):
        """
        Draw operator properties.

        Args:
            context (Context)
        """
        layout = self.layout
        col = layout.column()
        col.use_property_split = True
        col.row().prop(self, "armatures", expand=True)
        col.row().prop(self, "frame", expand=True)

    def execute(self, context: Context) -> OPERATOR_RETURN_ITEMS:
        """
        Set keyframes on all rigs.

        Args:
            context (Context)

        Returns:
            set[str]: CANCELLED, FINISHED, INTERFACE, PASS_THROUGH, RUNNING_MODAL
        """
        # Collect armatures
        if self.armatures == "ALL":
            objs = context.scene.collection.all_objects
        else:
            objs = context.selected_objects

        # Select frame
        if self.frame == "ZERO":
            frame = 0
        else:
            frame = context.scene.frame_current

        # Set keys
        for obj in objs:
            # Skip non-armatures or raw linked
            if obj.type != "ARMATURE" or obj.library:
                continue

            # Only controllers
            for pbone in obj.pose.bones:
                if pbone.name.startswith(("DEF", "MCH", "ORG", "VIS")):
                    continue

                # Set keyframes
                utils.insert_pbone_keyframe(pbone, frame)  # type: ignore

        return {"FINISHED"}


@catalog.bpy_register
class SCHALOTTETOOL_OT_AddAssetLibrary(Operator):
    bl_idname = "schalotte.add_asset_library"
    bl_label = "Add Asset Library"
    bl_options = {"REGISTER", "UNDO"}

    name: StringProperty(name="Name", description="Display name of the asset library")
    path: StringProperty(
        name="Path",
        description="Path to a directory with .blend files to use as an asset library",
    )
    import_method: EnumProperty(
        items=(
            ("LINK", "Link", "Import the assets as linked data-block"),
            ("APPEND", "Append", "Import the asset as copied data-block"),
            (
                "APPEND_REUSE",
                "Append (Reuse Data)",
                "Import as copied data-block, avoiding duplicate data",
            ),
        ),
        name="Import Method",
        description="Determine how the asset will be imported",
    )
    use_relative_path: BoolProperty(
        name="Relative Path",
        description="Use relative path when linking assets from this asset library",
        default=True,
    )

    def execute(self, context: Context) -> OPERATOR_RETURN_ITEMS:
        """
        Select pose bones of an armature object.

        Args:
            context (Context)

        Returns:
            set[str]: CANCELLED, FINISHED, INTERFACE, PASS_THROUGH, RUNNING_MODAL
        """
        asset_library = context.preferences.filepaths.asset_libraries.new(
            name=self.name,
            directory=self.path,
        )
        asset_library.use_relative_path = self.use_relative_path
        asset_library.import_method = self.import_method
        return {"FINISHED"}
