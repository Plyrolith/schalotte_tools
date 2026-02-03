import bpy

from . import (
    casting,  # noqa: F401
    catalog,
    client,
    logger,
    ops,  # noqa: F401
    panels,  # noqa: F401
    preferences,
    wm_container,
)

log = logger.get_logger(__name__)


def register():
    """
    Main registration.
    """
    log.info("Registering bpy classes")
    catalog.register_bpy()

    # Register property groups for preferences pointers
    for prefs_cls in catalog.bpy_preferences_classes:
        log.info(f"Registering module {prefs_cls.module}")

        # Register class with bpy
        bpy.utils.register_class(prefs_cls)  # type: ignore

        # Add to add-on preferences
        preferences.Preferences.__annotations__[prefs_cls.module] = (
            bpy.props.PointerProperty(type=prefs_cls)  # type: ignore
        )

    # Register preferences
    log.info("Registering add-on main class")
    bpy.utils.register_class(preferences.Preferences)

    # Set log level
    log.info("Setting log level")
    preferences.set_log_level()

    # Register property groups for window manager pointers
    for wm_cls in catalog.bpy_window_manager_classes:
        log.info(f"Registering window manager pointer {wm_cls.module}")

        # Register class with bpy
        bpy.utils.register_class(wm_cls)  # type: ignore

        # Add to window manager
        wm_container.WmContainer.__annotations__[wm_cls.module] = (
            bpy.props.PointerProperty(type=wm_cls)  # type: ignore
        )

    # Register window manager
    log.info("Registering window manager container")
    bpy.utils.register_class(wm_container.WmContainer)

    # Set pointer on window manager
    wm_pointer = bpy.props.PointerProperty(type=wm_container.WmContainer)
    setattr(bpy.types.WindowManager, catalog.get_package_base(), wm_pointer)  # type: ignore

    # Try to get the current user to ensure login state
    client.Client.this().get_current_user()


def unregister():
    """
    De-registration.
    """
    # Unregister preferences
    log.info("Unregistering add-on main class")
    bpy.utils.unregister_class(preferences.Preferences)

    # Unregister window manager
    log.info("Unregistering window manager container")
    bpy.utils.unregister_class(wm_container.WmContainer)

    # Classes un-registration
    log.info("Unregistering bpy classes")
    catalog.deregister_bpy()
