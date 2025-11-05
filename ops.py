from __future__ import annotations
from typing import Literal, TYPE_CHECKING

if TYPE_CHECKING:
    from bpy.types import Context

import pprint
import bpy
from bpy.types import Operator
from . import catalogue, client, logger

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
        Allow operator to run if the active scene has a sequencer.

        Args:
            context (Context)

        Returns:
            bool: Whether the active scene has a sequencer or not
        """
        c = client.Client.this()
        return bool(c.host and c.username and c.password)

    def execute(self, context: Context) -> OPERATOR_RETURN_ITEMS:
        """
        Add multiple videos as a sequence of movie strips to the sequencer.

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
        Allow operator to run if the active scene has a sequencer.

        Args:
            context (Context)

        Returns:
            bool: Whether the active scene has a sequencer or not
        """
        return client.Client.this().is_logged_in

    def execute(self, context: Context) -> OPERATOR_RETURN_ITEMS:
        """
        Add multiple images as a sequence of image strips to the sequencer.

        Args:
            context (Context)

        Returns:
            set[str]: CANCELLED, FINISHED, INTERFACE, PASS_THROUGH, RUNNING_MODAL
        """
        client.Client.this().log_out()
        log.info("Session ended.")
        return {"FINISHED"}
