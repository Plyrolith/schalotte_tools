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

![Install Add-on](img/install_addon.png)

# Development

- Install VSCode extensions:
  - Python
    `ext install ms-python.python`
  - Ruff
    `ext install charliermarsh.ruff`
  - Gitmoji
    `ext install seatonjiang.gitmoji-vscode`
- Install [Python Poetry](https://python-poetry.org/docs/#installation)
- Clone this repository and `cd` into it.
- Use Poetry to create a virtual environment and install (development) dependencies:

```bash
poetry env use /path/to/blender/4.5/python/bin/python3.11
poetry install --no-root
```

- Work in the `development` branch or create a new feature branch.
- Make sure there are no type checking or linter errors before commiting.
  Use `# type: ignore` if necessary.
- Please use Gitmoji for commit messages to increase readability.
- Merges into `main` require a PR!

## Build/Pack/Publish

- Make sure you're on `development` or your feature branch.
  Consider merging your feature branch into `development` first.
- Upgrade the version in `blender_manifest.toml` and `pyproject.toml` in a separate commit.
- Run `create_package`. This will create the zip file `build/schalotte_tools-X.X.X.zip` and update the repository index JSON.
- Create another commit to push the updated repository.
- Create a [new release on Github](https://github.com/Plyrolith/schalotte_tools/releases/new).
  - Create the version tag.
  - Select your branch.
  - Leave title and description empty.
  - Attach the zip file.
  - Publish the release.
- Create the PR. As soon as it is merged, your repository update will go live and point to your new package.

## Structure

The structure of this addon, sorted by functionality:

### Initialization

- `__init__.py`: Entrypoint for Blender add-on system. Blender calls `register()` and `unregister()` during (de)initialization.
- `catalog.py`: Decorators and functions for automatic class registration. More in [Class Registration](#class-registration).

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


## Class Registration

The `catalog.py` module simplifies adding new classes to Blender via decorators.
After adding the decorators, all you need to do is ensure your new module is loaded in `__init__.py`.

### `@catalog.bpy.preferences_module`

- Use this decorator to register a class to the addon preferences.
- Useful for long-term storage of properties that persist Blender sessions.
- Make sure your class inherits from `PreferencesModule`.
- The class will be available at:
  `bpy.context.preferences.addons['addon_name'].preferences.class_name`

### `@catalog.bpy_window_manager`

- Use this decorator to register a class to the window manager.
- Useful for storing temporary properties.
- Make sure your class inherits from `WindowManagerModule`.
- The class will be available at:
  `bpy.context.window_manager.addon_name.class_name`

### `@catalog.bpy_register`

- Use this decorator to register all other classes (operators, panels, etc.).

### Examples

```python
from bpy.types import Operator, Panel
from . import catalog


# A module that will be registered in the window manager


@catalog.bpy_window_manager
class MyWmModule(catalog.WindowManagerModule):
    module: str = "my_wm_module"


# Another module that will be registered in the add-on's preferences


@catalog.bpy_preferences
class MyPrefsModule(catalog.PreferencesModule):
    module: str = "my_prefs_module"


# Other classes that are registered with Blender: Operators, panels, lists, etc.


@catalog.bpy_register
class SCHALOTTETOOLS_OT_MyOperator(Operator):
    bl_idname = "schalotte.my_operator"
    bl_label = "My Operator"

    def execute(self, context):
        return {"FINISHED"}


@catalog.bpy_register
class SCHALOTTE_PT_my_panel(Panel):
    bl_idname = "SCHALOTTE_PT_my_panel"
    bl_category = "Schalotte Tools"
    bl_label = "My Panel"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"

    def draw(self, context):
        self.layout.label(text="A Panel")

```