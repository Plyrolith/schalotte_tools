from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from bpy.types import Context

from pathlib import Path
import bpy
import re
from bpy.props import EnumProperty, StringProperty

from . import catalog, client, logger


log = logger.get_logger(__name__)


@catalog.bpy_window_manager
class Session(catalog.WindowManagerModule):
    """Module for selecting task session context"""

    module: str = "session"

    def enum_open_project_ids(
        self,
        context: Context | None = None,
    ) -> list[tuple[str, str, str]]:
        """
        Get the open projects enumerator.
        """
        projects_enum = [("NONE", "None", "No project selected")]

        c = client.Client.this()
        if c.is_logged_in:
            for p in c.fetch_list("projects/open"):
                projects_enum.append((p["id"], p["name"], p["id"]))

        return projects_enum

    def enum_episode_ids(
        self,
        context: Context | None = None,
    ) -> list[tuple[str, str, str]]:
        """
        Get the list of episodes.
        """
        episodes_enum = [("NONE", "None", "No episode selected")]

        c = client.Client.this()
        if c.is_logged_in and self.project_id != "NONE":
            for e in c.fetch_list(f"projects/{self.project_id}/episodes"):
                episodes_enum.append((e["id"], e["name"], e["id"]))

        return episodes_enum

    def enum_sequence_ids(
        self,
        context: Context | None = None,
    ) -> list[tuple[str, str, str]]:
        """
        Get the list of sequences.
        """
        sequences_enum = [("NONE", "None", "No sequence selected")]

        c = client.Client.this()
        if c.is_logged_in:
            if self.episode_id != "NONE":
                path = f"episodes/{self.episode_id}/sequences"
            elif self.project_id != "NONE":
                path = f"projects/{self.project_id}/sequences"
            else:
                return sequences_enum

            for s in c.fetch_list(path):
                sequences_enum.append((s["id"], s["name"], s["id"]))

        return sequences_enum

    def enum_shot_ids(
        self,
        context: Context | None = None,
    ) -> list[tuple[str, str, str]]:
        """
        Get the list of shots.
        """
        shots_enum = [("NONE", "None", "No shot selected")]

        c = client.Client.this()
        if c.is_logged_in:
            if self.sequence_id != "NONE":
                path = f"sequences/{self.sequence_id}/shots"
            elif self.episode_id != "NONE":
                path = f"episodes/{self.episode_id}/shots"
            elif self.project_id != "NONE":
                path = f"projects/{self.project_id}/shots"
            else:
                return shots_enum

            for s in c.fetch_list(path):
                shots_enum.append((s["id"], s["name"], s["id"]))

        return shots_enum

    def enum_task_ids(
        self,
        context: Context | None = None,
    ) -> list[tuple[str, str, str]]:
        """
        Get the list of episodes.
        """
        tasks_enum = [("NONE", "None", "No task selected")]
        self.storyboard_task = ""

        c = client.Client.this()
        if c.is_logged_in:
            if self.shot_id != "NONE":
                path = f"shots/{self.shot_id}/tasks"
            elif self.sequence_id != "NONE":
                path = f"sequences/{self.sequence_id}/tasks"
            else:
                return tasks_enum

            for t in c.fetch_list(path):
                if t["task_type_name"].lower() == "storyboard":
                    self.storyboard_task = t["id"]
                task_enum = (t["id"], t["task_type_name"], t["id"])
                tasks_enum.append(task_enum)

        return tasks_enum

    project_id: EnumProperty(
        name="Project",
        items=enum_open_project_ids,
        description="Selected project",
    )

    episode_id: EnumProperty(
        name="Episode",
        items=enum_episode_ids,
        description="Selected episode",
    )

    sequence_id: EnumProperty(
        name="Sequence",
        items=enum_sequence_ids,
        description="Selected sequence",
    )

    shot_id: EnumProperty(
        name="Shot",
        items=enum_shot_ids,
        description="Selected shot",
    )

    task_id: EnumProperty(
        name="Task",
        items=enum_task_ids,
        description="Selected task",
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
            log.debug(f"Detected no shot.")

        # Get task from convoluted parent folder
        path_task = re.sub(r"[^a-z]", "", file_path.parents[3].name.lower())
        log.debug(f"Detected task: {path_task}")

        # Project
        projects_enum = self.enum_open_project_ids()
        if len(projects_enum) < 2:
            log.error("No open projects found.")
            return
        for project_enum in projects_enum[1:]:
            if path_pr in project_enum[1].lower():
                self.project_id = project_enum[0]
                break
        else:
            self.project_id = projects_enum[1][0]

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
