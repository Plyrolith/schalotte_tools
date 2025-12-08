from __future__ import annotations
from typing import Literal, TYPE_CHECKING

if TYPE_CHECKING:
    from bpy.types import Context, Event

import colorsys
from pathlib import Path
import pprint
import random
import tempfile

import bpy
from bpy_extras.io_utils import ImportHelper
from bpy.props import (
    BoolProperty,
    CollectionProperty,
    EnumProperty,
    IntProperty,
    StringProperty,
)
from bpy.types import Operator, OperatorFileListElement, OperatorProperties
from . import casting, catalog, client, logger, schalotte, session, utils


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
        return context.window_manager.invoke_props_dialog(self)

    def execute(self, context: Context) -> OPERATOR_RETURN_ITEMS:
        """
        Create a new comment, render the shot and upload the video to it.

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
        log.info(f"Creating a new comment.")
        task_id = session.Session.this().task_id
        data = {"task_status_id": self.task_status_id, "comment": self.comment}
        comment = c.post(f"actions/tasks/{task_id}/comment", data)

        # Render preview
        temp_dir = Path(tempfile.mkdtemp(prefix=f"{catalog.get_package_base()}_"))
        log.info(f"Creating temp dir at {temp_dir}")
        stem = Path(bpy.data.filepath).stem
        if not stem:
            stem = "untitled"
        file_path = temp_dir / f"{stem}.mp4"
        log.info(f"Rendering video to {file_path}")
        utils.render_scene(file_path, context.scene, use_stamp=True)

        # Upload preview
        log.info("Creating a new preview.")
        preview = c.post(
            f"actions/tasks/{task_id}/comments/{comment['id']}/add-preview",
            {},
        )
        log.info(f"Uploading video to preview {preview['id']}")
        c.upload(
            f"pictures/preview-files/{preview['id']}?normalize=false",
            file_path.as_posix(),
        )

        # Delete
        log.info("Cleaning up temp dir.")
        file_path.unlink()
        temp_dir.rmdir()

        return {"FINISHED"}


@catalog.bpy_register
class SCHALOTTETOOL_OT_SetupStoryboard(Operator):
    """Set up the current scene for storyboarding"""

    bl_idname = "schalotte.setup_storyboard"
    bl_label = "Storyboard Setup"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context) -> bool:
        """
        Only if file is saved and the current task is of the 'storyboard' type.

        Args:
            context (Context)

        Returns:
            bool: File is saved, task is active and type is 'storyboard'
        """
        s = session.Session.this()
        return bool(
            bpy.data.filepath
            and s.task
            and s.task.get("task_type_name", "").lower() == "storyboard"
        )

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
        if file_path:
            layout_takes = Path(file_path).parents[1] / "layout_takes"
            if layout_takes.is_dir():
                self.directory = layout_takes.as_posix()
            else:
                self.directory = Path(file_path).parent.as_posix()
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
            filepath = Path(self.directory, file.name)

            # Check if already imported
            if filepath.resolve() in existing_paths:
                log.info(f"Skipping existing file: {filepath}")
                continue

            # Check if the file exists
            if not filepath.is_file():
                log.error(f"{filepath} does not exist")
                continue

            # Make relative
            filepath = filepath.as_posix()
            if self.relative_path:
                filepath = bpy.path.relpath(filepath)

            # Create strip
            sequence = sequence_editor.strips.new_sound(
                name="audio",
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
            links = [l for l in c.links if l.file_path and not l.library_name]

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
    """Reorder StoryLiner shots and rename all names to match the shot order"""

    bl_idname = "schalotte.fix_storyboard_names"
    bl_label = "Fix Storyboard Names"
    bl_options = {"REGISTER", "UNDO"}

    sort_shots: BoolProperty(name="Sort StoryLiner Shots", default=True)
    rename_shots: BoolProperty(name="Rename Storyboarder Shots", default=True)

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
            schalotte.sort_storyliner_shots(context.scene)

        # Rename shots
        if self.rename_shots:
            schalotte.rename_storyliner_shots(context.scene)

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
            return "Add a new StoryLiner shot based on the current camera"
        else:
            return "Add a new StoryLiner shot without camera transforms"

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
        Append a new camera and create a new StoryLiner shot.

        Args:
            context (Context)

        Returns:
            set[str]: CANCELLED, FINISHED, INTERFACE, PASS_THROUGH, RUNNING_MODAL
        """
        # Append a new camera rig
        new_col, new_rig, new_cam = schalotte.ensure_camera_rig(context.scene, True)
        if not new_rig or not new_cam:
            msg = "Failed to append camera rig."
            self.report({"ERROR"}, msg)
            log.error(msg)
            return {"CANCELLED"}

        # Find the current camera's rig
        props = context.scene.WkStoryLiner_props  # type: ignore
        current_rig = None
        if self.use_current_camera:
            try:
                current_rig = props.getCurrentShot().camera.parent
            except AttributeError:
                log.error("Unable to not find the current shot's camera rig.")

        # Create the StoryLiner shot
        frame_start = props.get_frame_end() + 1
        nb_shots = len(props.getShotsList())
        shot_name = props.getShotPrefix((nb_shots + 1) * 10)

        props.addShot(  # type: ignore
            name=shot_name,
            start=frame_start,
            end=frame_start + 50,
            camera=new_cam,
            color=colorsys.hsv_to_rgb(random.random(), 0.9, 1.0) + (1.0,),
        )

        # Rename the new camera
        schalotte.rename_cam_rig(new_cam, f"cam_{shot_name}", new_col)

        # Copy the current camera's rig pose
        if current_rig:
            utils.copy_pose(current_rig, new_rig)

        # Go to the new shot
        context.scene.frame_current = frame_start

        return {"FINISHED"}


@catalog.bpy_register
class SCHALOTTETOOL_OT_RemoveStoryLinerGaps(Operator):

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
