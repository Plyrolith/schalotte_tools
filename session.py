from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from bpy.types import Context

from pathlib import Path
import bpy
import re
from bpy.props import EnumProperty

from . import catalog, client, logger


log = logger.get_logger(__name__)


@catalog.bpy_window_manager
class Session(catalog.WindowManagerModule):
    """Module for selecting task session context"""

    module: str = "session"

    def enum_open_projects(
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

    def enum_episodes(
        self,
        context: Context | None = None,
    ) -> list[tuple[str, str, str]]:
        """
        Get the list of episodes.
        """
        episodes_enum = [("NONE", "None", "No episode selected")]
        c = client.Client.this()
        if c.is_logged_in and self.project != "NONE":
            for e in c.fetch_list(f"projects/{self.project}/episodes"):
                episodes_enum.append((e["id"], e["name"], e["id"]))
        return episodes_enum

    def enum_sequences(
        self,
        context: Context | None = None,
    ) -> list[tuple[str, str, str]]:
        """
        Get the list of sequences.
        """
        sequences_enum = [("NONE", "None", "No sequence selected")]
        c = client.Client.this()
        if c.is_logged_in:
            if self.episode != "NONE":
                for s in c.fetch_list(f"episodes/{self.episode}/sequences"):
                    sequences_enum.append((s["id"], s["name"], s["id"]))
            elif self.project != "NONE":
                for s in c.fetch_list(f"projects/{self.project}/sequences"):
                    sequences_enum.append((s["id"], s["name"], s["id"]))
        return sequences_enum

    def enum_shots(
        self,
        context: Context | None = None,
    ) -> list[tuple[str, str, str]]:
        """
        Get the list of shots.
        """
        shots_enum = [("NONE", "None", "No shot selected")]
        c = client.Client.this()
        if c.is_logged_in:
            if self.sequence != "NONE":
                for s in c.fetch_list(f"sequences/{self.sequence}/shots"):
                    shots_enum.append((s["id"], s["name"], s["id"]))
            elif self.episode != "NONE":
                for s in c.fetch_list(f"episodes/{self.episode}/shots"):
                    shots_enum.append((s["id"], s["name"], s["id"]))
            elif self.project != "NONE":
                for s in c.fetch_list(f"projects/{self.project}/shots"):
                    shots_enum.append((s["id"], s["name"], s["id"]))
        return shots_enum

    def enum_tasks(
        self,
        context: Context | None = None,
    ) -> list[tuple[str, str, str]]:
        """
        Get the list of episodes.
        """
        tasks_enum = [("NONE", "None", "No task selected")]
        c = client.Client.this()
        if c.is_logged_in:
            if self.shot != "NONE":
                for t in c.fetch_list(f"shots/{self.shot}/tasks"):
                    task_enum = (t["id"], t["task_type_name"], t["id"])
                    tasks_enum.append(task_enum)
            elif self.sequence != "NONE":
                for t in c.fetch_list(f"sequences/{self.sequence}/tasks"):
                    task_enum = (t["id"], t["task_type_name"], t["id"])
                    tasks_enum.append(task_enum)
        return tasks_enum

    project: EnumProperty(
        name="Project",
        items=enum_open_projects,
        description="Selected project",
    )

    episode: EnumProperty(
        name="Episode",
        items=enum_episodes,
        description="Selected episode",
    )

    sequence: EnumProperty(
        name="Sequence",
        items=enum_sequences,
        description="Selected sequence",
    )

    shot: EnumProperty(
        name="Shot",
        items=enum_shots,
        description="Selected shot",
    )

    task: EnumProperty(
        name="Task",
        items=enum_tasks,
        description="Selected task",
    )

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
        projects_enum = self.enum_open_projects()
        if len(projects_enum) < 2:
            log.error("No open projects found.")
            return
        for project_enum in projects_enum[1:]:
            if path_pr in project_enum[1].lower():
                self.project = project_enum[0]
                break
        else:
            self.project = projects_enum[1][0]

        # Episode
        episodes_enum = self.enum_episodes()
        if len(episodes_enum) < 2:
            log.error("No episodes found")
        for episode_enum in episodes_enum[1:]:
            if path_ep == episode_enum[1].lower():
                self.episode = episode_enum[0]
                break
        else:
            log.error(f"Could not find episode {path_ep}.")

        # Sequence
        sequences_enum = self.enum_sequences()
        if len(sequences_enum) < 2:
            log.error("No sequences found")
        for sequence_enum in sequences_enum[1:]:
            if path_sq == sequence_enum[1].lower():
                self.sequence = sequence_enum[0]
                break
        else:
            log.error(f"Could not find sequence {path_sq}.")

        # Shot
        shots_enum = self.enum_shots()
        if len(shots_enum) < 2:
            log.error("No shots found")
        for shot_enum in shots_enum[1:]:
            # Real shot
            if path_sh:
                if path_sh == shot_enum[1].lower():
                    self.shot = shot_enum[0]
                    break
            # Sequence shot
            else:
                if shot_enum[1].startswith("_"):
                    self.shot = shot_enum[0]
                    break
        else:
            log.error(f"Could not find shot {path_sh or path_sq}.")

        # Task
        tasks_enum = self.enum_tasks()
        for task_enum in tasks_enum[1:]:
            task_name = task_enum[1].lower().strip()
            if " " in task_name:
                task_name = task_name.split(" ")[0]

            if task_name in path_task:
                self.task = task_enum[0]
                break
        else:
            log.error("Could not find task.")
