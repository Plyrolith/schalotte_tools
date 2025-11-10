# Schalotte Tools

Blender add-on providing additional tools for the Schalotte project.

# Installation

Add this repository to your Blender Extensions. In Blender, navigate to:

> **Preferences** > **Get Extensions** > **Repositories** > **+** > **Add Remote Repository...**

- URL:
  `https://raw.githubusercontent.com/plyrolith/schalotte_tools/refs/heads/main/repository/index.json`
- Check for Updates on Start: **True**.
- Require Access Token: **False**.
- Custom Directory: **Optional**.
  Set a path if you like to copy this add-on to a custom location on your machine.

![Add Repository](img/add_repo.png)

After creation, feel free to rename the repository to "Schalotte Tools" by double clicking its name in the repository list.

Install the add-on by searching for "schalotte" and clicking **Install**.

![Add Repository](img/install_addon.png)

# Development

- Install VSCode extensions:
  - Python
    `ext install ms-python.python`
  - Black Formatter
    `ext install ms-python.black-formatter`
- Install [Python Poetry](https://python-poetry.org/docs/#installation)
- Clone this repository and `cd` into it.
- Use Poetry to create a virtual environment and install (development) dependencies:

```bash
poetry env use /path/to/blender/4.5/python/bin/python3.11
poetry install --no-root
```

- Create a PR if you like to contribute!

## Structure

The structure of this addon, sorted by functionality:

### Initialization

- `__init__.py`: Entrypoint for Blender add-on system. Blender calls `register()` and `unregister()` during (de)initialization.
- `catalog.py`: Decorators and functions for automatic class registration. This module simplifies adding new classes to Blender via decorators.
  - `@catalog.bpy.preferences_module`: Use this decorator to register a class to the addon preferences.
    Make sure your class inherits from `PreferencesModule`. The class will be available at `bpy.context.preferences.addons['addon_name'].preferences.class_name`. Useful for long-term storage of properties that persist Blender sessions.
  - `@catalog.bpy_window_manager`: Use this decorator to register a class to the window manager.
    Make sure your class inherits from `WindowManagerModule`. The class will be available at `bpy.context.window_manager.addon_name.class_name`. Useful for storing temporary properties.
  - `@catalog.bpy_register`: Use this decorator to register all other classes (operators, panels, etc.).

### Basic

- `logger`: Central logging definitions.
- `exceptions`: Custom exception types, mostly for the REST API.

### Blender Modules

- `preferences.py`: Add-on preferences and container for other preferences modules.
- `wm_container.py`: Container for all window manager modules.
- `client.py`: Kitsu REST API, implemented as preferences module.
- `session.py`: Window manager module for selecting the task context for the current session.
- `casting.py`: Casting and asset linking functionality, implemented as window manager module.
- `ops.py`: Operator classes.
- `draw.py`: All draw functions.
- `panels.py`: Panel class definitions, calling draw functions from the `draw.py` module.

### Utilites

- `utils.py`: Utilities for Blender.
- `schalotte.py`: Utilities and definitions that are specific to the 'Schalotte' project.
