from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from typing import Literal

    from bpy.types import Context

import re
from pathlib import Path

import bpy
from bpy.props import EnumProperty, StringProperty

from . import catalog, client, logger, schalotte, utils

log = logger.get_logger(__name__)


NOT_LOGGED_IN = [("NONE", "Unavailable", "Please log in first")]
NO_PROJECT = [("NONE", "Project Required", "No project selected")]


@catalog.bpy_window_manager
class Session(catalog.WindowManagerModule):
    """Module for selecting task session context"""

    module: str = "session"

    def enum_project_ids(
        self,
        context: Context | None = None,
    ) -> list[tuple[str, str, str]]:
        """
        Get the open projects enumerator.
        """
        c = client.Client.this()
        if not c.is_logged_in:
            return NOT_LOGGED_IN

        projects_enum = []
        for p in c.fetch_list("projects/open"):
            projects_enum.append((p["id"], p["name"], p["id"]))

        if projects_enum:
            return projects_enum

        return [("NONE", "No Projects Available", "No open projects found")]

    def enum_episode_ids(
        self,
        context: Context | None = None,
    ) -> list[tuple[str, str, str]]:
        """
        Get the list of episodes.
        """
        c = client.Client.this()
        if not c.is_logged_in:
            return NOT_LOGGED_IN

        if self.project_id == "NONE":
            return NO_PROJECT

        episodes_enum = []
        for e in c.fetch_list(f"projects/{self.project_id}/episodes"):
            episodes_enum.append((e["id"], e["name"], e["id"]))

        if episodes_enum:
            return [("NONE", "All", "No episode selected")] + episodes_enum

        return [("NONE", "No Episodes Available", "No episodes found in project")]

    def enum_sequence_ids(
        self,
        context: Context | None = None,
    ) -> list[tuple[str, str, str]]:
        """
        Get the list of sequences.
        """
        c = client.Client.this()
        if not c.is_logged_in:
            return NOT_LOGGED_IN

        if self.episode_id != "NONE":
            path = f"episodes/{self.episode_id}/sequences"
        elif self.project_id != "NONE":
            path = f"projects/{self.project_id}/sequences"
        else:
            return NO_PROJECT

        sequences_enum = []
        for s in c.fetch_list(path):
            sequences_enum.append((s["id"], s["name"], s["id"]))

        if sequences_enum:
            return [("NONE", "All", "No sequence selected")] + sequences_enum

        return [("NONE", "No Sequences Available", "No sequences found for selection")]

    def enum_shot_ids(
        self,
        context: Context | None = None,
    ) -> list[tuple[str, str, str]]:
        """
        Get the list of shots.
        """
        c = client.Client.this()
        if not c.is_logged_in:
            return NOT_LOGGED_IN

        if self.sequence_id != "NONE":
            path = f"sequences/{self.sequence_id}/shots"
        elif self.episode_id != "NONE":
            path = f"episodes/{self.episode_id}/shots"
        elif self.project_id != "NONE":
            path = f"projects/{self.project_id}/shots"
        else:
            return NO_PROJECT

        shots_enum = []
        for s in c.fetch_list(path):
            shots_enum.append((s["id"], s["name"], s["id"]))

        if shots_enum:
            return [("NONE", "None", "No shot selected")] + shots_enum

        return [("NONE", "No Shots Available", "No shots found for selection")]

    def enum_task_ids(
        self,
        context: Context | None = None,
    ) -> list[tuple[str, str, str]]:
        """
        Get the list of episodes.
        """
        c = client.Client.this()
        if not c.is_logged_in:
            return NOT_LOGGED_IN

        if self.shot_id != "NONE":
            path = f"shots/{self.shot_id}/tasks"
        elif self.sequence_id != "NONE":
            path = f"sequences/{self.sequence_id}/tasks"
        else:
            return [("NONE", "Shot or Sequence Required", "Select shot or sequence")]

        tasks_enum = []
        for t in c.fetch_list(path):
            task_enum = (t["id"], t["task_type_name"], t["id"])
            tasks_enum.append(task_enum)

        if tasks_enum:
            return [("NONE", "Select", "No task selected")] + tasks_enum

        return [("NONE", "No Tasks Available", "No tasks found for selected")]

    def update_project_id(self, context: Context):
        """
        Reset episode ID.
        """
        self.episode_id = "NONE"

    def update_episode_id(self, context: Context):
        """
        Reset sequence ID.
        """
        self.sequence_id = "NONE"

    def update_sequence_id(self, context: Context):
        """
        Reset shot and task IDs.
        """
        self.shot_id = "NONE"
        self.task_id = "NONE"

    def update_shot_id(self, context: Context):
        """
        Reset task ID.
        """
        self.task_id = "NONE"

    def update_task_id(self, context: Context):
        """
        Set existing or expected file path.
        """
        self.current_file_path = bpy.data.filepath
        self.work_file_path = ""
        if not self.task_id or self.task_id == "NONE":
            self.work_file_status = "NONE"
            return

        task_path = schalotte.generate_shot_blend_path(self.task_id)
        if not task_path:
            log.debug("Task path cannot be generated.")
            self.work_file_status = "INVALID"
            return
        self.work_file_path = task_path.as_posix()

        if self.current_file_path and utils.are_same_paths(
            self.current_file_path, task_path
        ):
            log.debug("Current file matches task path.")
            self.work_file_status = "ACTIVE"

        elif task_path.exists():
            log.debug("Work file exists but is not loaded.")
            self.work_file_status = "EXISTS"

        else:
            log.debug("Work file has not been created yet.")
            self.work_file_status = "MISSING"

    project_id: EnumProperty(
        name="Project",
        items=enum_project_ids,
        description="Selected project",
        update=update_project_id,
    )

    episode_id: EnumProperty(
        name="Episode",
        items=enum_episode_ids,
        description="Selected episode",
        update=update_episode_id,
    )

    sequence_id: EnumProperty(
        name="Sequence",
        items=enum_sequence_ids,
        description="Selected sequence",
        update=update_sequence_id,
    )

    shot_id: EnumProperty(
        name="Shot",
        items=enum_shot_ids,
        description="Selected shot",
        update=update_shot_id,
    )

    task_id: EnumProperty(
        name="Task",
        items=enum_task_ids,
        description="Selected task",
        update=update_task_id,
    )

    current_file_path: StringProperty(name="Current File Path", subtype="FILE_PATH")

    work_file_path: StringProperty(name="Work File Path", subtype="FILE_PATH")

    work_file_status: EnumProperty(
        items=(
            ("NONE", "No Task Selected", "No Task Selected"),
            ("INVALID", "Invalid", "Invalid"),
            ("MISSING", "Missing", "Missing"),
            ("EXISTS", "Existing", "Existing"),
            ("ACTIVE", "Active", "Active"),
        ),
        name="Work File Status",
    )

    @property
    def project(self) -> dict | None:
        return client.STORE.get(self.project_id)

    @property
    def episode(self) -> dict | None:
        return client.STORE.get(self.episode_id)

    @property
    def sequence(self) -> dict | None:
        return client.STORE.get(self.sequence_id)

    @property
    def shot(self) -> dict | None:
        return client.STORE.get(self.shot_id)

    @property
    def task(self) -> dict | None:
        return client.STORE.get(self.task_id)

    def get_work_file_status(
        self,
    ) -> Literal["NONE", "INVALID", "MISSING", "EXISTS", "ACTIVE"]:
        """
        Get the work file status of the session and update if the open file has changed.

        Returns:
            Literal["NONE", "INVALID", "MISSING", "EXISTS", "ACTIVE"]:
            The updated work file status.
        """
        if bpy.data.filepath != self.current_file_path:
            self.update_task_id(bpy.context)
        return self.work_file_status

    def guess_from_filepath(self, file_path: str | Path | None = None):
        """
        Try to guess the current context based on given (or open) file path.

        Args:
            file_path (str | Path): The file path to check, .blend file if not set
        """
        if not file_path:
            file_path = bpy.data.filepath
            if not file_path:
                log.error("No file path given.")
                return

        file_path = Path(file_path)

        # Project name from file prefix
        stem_parts = file_path.stem.split("_")
        path_pr = stem_parts[0].lower()
        log.debug(f"Detected project: {path_pr}")

        # Get episode and sequence from parent folders
        path_ep = re.sub(r"[^0-9a-z]", "", file_path.parents[1].name.lower())
        log.debug(f"Detected episode: {path_ep}")
        path_sq = re.sub(r"[^0-9a-z]", "", file_path.parents[0].name.lower())
        log.debug(f"Detected sequence: {path_sq}")

        # Get shot from file name
        sh_match = re.search(r"_(sh\d+)", file_path.name)
        if sh_match:
            path_sh = sh_match.groups()[0]
            log.debug(f"Detected shot: {path_sh}")
        else:
            path_sh = None
            log.debug("Detected no shot.")

        # Get task from convoluted parent folder
        path_task = re.sub(r"[^a-z]", "", file_path.parents[3].name.lower())
        log.debug(f"Detected task: {path_task}")

        # Project
        projects_enum = self.enum_project_ids()
        if len(projects_enum) < 1:
            log.error("No open projects found.")
            return
        for project_enum in projects_enum:
            if path_pr in project_enum[1].lower():
                self.project_id = project_enum[0]
                break
        else:
            self.project_id = projects_enum[0][0]

        # Episode
        episodes_enum = self.enum_episode_ids()
        if len(episodes_enum) < 2:
            log.error("No episodes found")
        for episode_enum in episodes_enum[1:]:
            if path_ep == episode_enum[1].lower():
                self.episode_id = episode_enum[0]
                break
        else:
            log.error(f"Could not find episode {path_ep}.")

        # Sequence
        sequences_enum = self.enum_sequence_ids()
        if len(sequences_enum) < 2:
            log.error("No sequences found")
        for sequence_enum in sequences_enum[1:]:
            if path_sq == sequence_enum[1].lower():
                self.sequence_id = sequence_enum[0]
                break
        else:
            log.error(f"Could not find sequence {path_sq}.")

        # Shot
        shots_enum = self.enum_shot_ids()
        if len(shots_enum) < 2:
            log.error("No shots found")
        for shot_enum in shots_enum[1:]:
            # Real shot
            if path_sh:
                if path_sh == shot_enum[1].lower():
                    self.shot_id = shot_enum[0]
                    break
            # Sequence shot
            else:
                if shot_enum[1].startswith("_"):
                    self.shot_id = shot_enum[0]
                    break
        else:
            log.error(f"Could not find shot {path_sh or path_sq}.")

        # Task
        tasks_enum = self.enum_task_ids()
        for task_enum in tasks_enum[1:]:
            task_name = task_enum[1].lower().strip()
            if " " in task_name:
                task_name = task_name.split(" ")[0]

            if task_name in path_task:
                self.task_id = task_enum[0]
                break
        else:
            log.error("Could not find task.")
