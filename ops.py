from __future__ import annotations
from typing import Literal, TYPE_CHECKING

if TYPE_CHECKING:
    from bpy.types import Context, Event

from pathlib import Path
import pprint
import tempfile

import bpy
from bpy.props import EnumProperty, IntProperty, StringProperty
from bpy.types import Operator
from . import casting, catalogue, client, logger, schalotte, session, utils

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


@catalogue.bpy_register
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


@catalogue.bpy_register
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


@catalogue.bpy_register
class SCHALOTTETOOL_OT_UploadPreview(Operator):
    """Render a preview and upload it to selected task"""

    bl_idname = "schalotte.upload_preview"
    bl_label = "Upload Preview"
    bl_options = {"REGISTER"}

    def enum_task_statuses(self, context: Context | None) -> list[tuple[str, str, str]]:
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

    task_status: EnumProperty(name="Task Status", items=enum_task_statuses)
    comment: StringProperty(name="Comment")

    @classmethod
    def poll(cls, context) -> bool:
        """
        Allow only if the client is logged in and a task is selected.

        Args:
            context (Context)

        Returns:
            bool: Logged in and task selected
        """
        return (
            client.Client.this().is_logged_in and session.Session.this().task != "NONE"
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
        if self.task_status == "NONE":
            log.error("No task status for feedback request found.")
            return {"CANCELLED"}

        c = client.Client.this()

        # Create new comment
        log.info(f"Creating a new comment.")
        task_id = session.Session.this().task
        data = {"task_status_id": self.task_status, "comment": self.comment}
        comment = c.post(f"actions/tasks/{task_id}/comment", data)

        # Render preview
        temp_dir = Path(tempfile.mkdtemp(prefix=f"{catalogue.get_package_base()}_"))
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


@catalogue.bpy_register
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
        schalotte.setup_storyboard(context.scene)
        return {"FINISHED"}


@catalogue.bpy_register
class SCHALOTTETOOL_OT_GuessSessionFromFilepath(Operator):
    """Guess the current session task context from the file path"""

    bl_idname = "schalotte.guess_session_from_filepath"
    bl_label = "Guess From File Path"
    bl_options = {"REGISTER"}

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


@catalogue.bpy_register
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
        return bool(s.project != "NONE" and s.shot != "NONE")

    def execute(self, context: Context) -> OPERATOR_RETURN_ITEMS:
        """
        Fetch the casting for the selected shot.

        Args:
            context (Context)

        Returns:
            set[str]: CANCELLED, FINISHED, INTERFACE, PASS_THROUGH, RUNNING_MODAL
        """
        s = session.Session.this()
        casting.Casting.this().fetch_entity_breakdown(s.project, s.shot)
        return {"FINISHED"}


@catalogue.bpy_register
class SCHALOTTETOOL_OT_LinkAsset(Operator):
    """Link a cast asset to a scene."""

    bl_idname = "schalotte.link_asset"
    bl_label = "Link Asset"
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
        ),
        name="Mode",
        default="EDITABLE_OVERRIDE",
    )

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

            # Report if failed
            if not asset:
                self.report({"ERROR"}, f"Unable to link asset {link.asset_name}")

        return {"FINISHED"}
