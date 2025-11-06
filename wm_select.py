from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from bpy.types import Context

from bpy.props import EnumProperty

from . import catalogue, client


@catalogue.bpy_window_manager
class WmSelect(catalogue.WindowManagerModule):
    """Module to store task selection progress"""

    module: str = "select"

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
