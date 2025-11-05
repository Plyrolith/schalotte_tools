from __future__ import annotations
from typing import Callable, TypeVar

import bpy

from . import logger

T = TypeVar("T")
BPY_REGISTER_TYPE = (
    bpy.types.Header
    | bpy.types.KeyingSetInfo
    | bpy.types.Menu
    | bpy.types.Operator
    | bpy.types.Panel
    | bpy.types.PropertyGroup
    | bpy.types.RenderEngine
    | bpy.types.UIList
)


log = logger.get_logger(__name__)


# Initialization lists
pre_register_functions: list[Callable] = []
bpy_register_classes: list[BPY_REGISTER_TYPE] = []
bpy_window_manager_classes: list[WindowManagerModule] = []
bpy_preferences_classes: list[PreferencesModule] = []
post_register_functions: list[Callable] = []
post_initialization_functions: list[Callable] = []
pre_deregister_functions: list[Callable] = []


# Decorators for add-on initialization


def bpy_register(cls: T) -> T:
    """
    Add an object to the global catalogue to mark for registration with bpy.

    ### Use as decorator.

    Args:
        cls (anything): bpy object class

    Returns:
        anything: Unchanged object
    """
    if cls not in bpy_register_classes:
        bpy_register_classes.append(cls)  # type: ignore

    return cls


def bpy_window_manager(cls: T) -> T:
    """
    Add a PropertyGroup to the global catalogue to mark for registration with
    bpy and add a PointerProperty to the add-on window_manager group to point at it.

    ### Use as decorator.

    Required property:
        module (str): Snake case module name for PointerProperty

    Args:
        cls (PropertyGroup): bpy property group object

    Returns:
        anything: Unchanged object
    """
    assert hasattr(cls, "module") and cls.module, f"{cls} has invalid module property"  # type: ignore

    if cls not in bpy_window_manager_classes:
        bpy_window_manager_classes.append(cls)  # type: ignore

    return cls


def bpy_preferences(cls: T) -> T:
    """
    Add a PropertyGroup to the global catalogue to mark for registration with
    bpy and add a PointerProperty to the add-on preferences to point at it.

    ### Use as decorator.

    Required property:
        module (str): Snake case module name for PointerProperty

    Args:
        cls (PropertyGroup): bpy property group object

    Returns:
        anything: Unchanged object
    """
    assert hasattr(cls, "module") and cls.module, f"{cls} has invalid module property"  # type: ignore

    if cls not in bpy_preferences_classes:
        bpy_preferences_classes.append(cls)  # type: ignore

    return cls


# Module classes


class PreferencesModule(bpy.types.PropertyGroup):
    """Base class for module property groups registered with the userprefs"""

    module: str = ""

    @classmethod
    def this(cls: type[T]) -> T:
        """
        Return Blender's initiated instance of this module.
        """
        addons = bpy.context.preferences.addons
        return getattr(addons[__package__].preferences, cls.module)  # type: ignore


class WindowManagerModule(bpy.types.PropertyGroup):
    """Base class for module property groups registered with the window manager"""

    module: str = ""

    @classmethod
    def this(cls: type[T]) -> T:
        """
        Return Blender's initiated instance of this module.
        """
        wm = bpy.context.window_manager
        return getattr(getattr(wm, __package__), cls.module)  # type: ignore


# Catalog functions


def register_bpy():
    """
    Loop through all collected classes and register them with bpy.
    """
    for bpy_cls in bpy_register_classes:
        try:
            bpy.utils.register_class(bpy_cls)  # type: ignore
        except Exception as e:
            log.error(f"Failed to register class {bpy_cls}: {e}")
            raise e


def deregister_bpy():
    """
    Loop through all collected classes and deregister them with bpy.
    """
    for bpy_cls in reversed(
        bpy_preferences_classes + bpy_window_manager_classes + bpy_register_classes
    ):
        try:
            bpy.utils.unregister_class(bpy_cls)  # type: ignore
        except Exception as e:
            log.error(f"Failed to unregister class {bpy_cls}: {e}")
            raise e
