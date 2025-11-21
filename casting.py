from __future__ import annotations
from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from bpy.types import Collection, Library, Object, Scene, ViewLayer

from pathlib import Path
import bpy
from bpy.props import CollectionProperty, IntProperty, StringProperty
from bpy.types import PropertyGroup

from . import catalog, client, logger, schalotte, utils


log = logger.get_logger(__name__)


@catalog.bpy_register
class CastingLink(PropertyGroup):
    """Single casting link, representing an asset"""

    # Kitsu properties
    asset_id: StringProperty(name="Asset ID")
    asset_name: StringProperty(name="Asset Name")
    asset_type_name: StringProperty(name="Asset Type Name")
    episode_id: StringProperty(name="Episode ID")
    is_shared: bool = False
    label: StringProperty(name="Label")
    nb_occurrences: IntProperty(name="Number of occurrences")
    preview_file_id: StringProperty(name="Preview File ID")
    project_id: StringProperty(name="Project ID")
    ready_for: StringProperty(name="Ready for")

    # System properties
    file_path: StringProperty(name="File Path")
    library_name: StringProperty(name="Library Name")

    def from_dict(self, data: dict[str, Any]):
        """
        Populate the properties of this object from a dictionary.
        """
        for key, value in data.items():
            if value and key in self.__annotations__:
                setattr(self, key, value)

    def get_library(self) -> Library | None:
        """
        Get the library for this asset, if already linked.

        Returns:
            Library | None
        """
        # Check if library is already set
        library = bpy.data.libraries.get(self.library_name)
        if library:
            return library

        # Check if library is linked
        for library in bpy.data.libraries:
            if utils.are_same_paths(self.file_path, library.filepath):
                log.debug(f"Found linked library {library.name} for {self.asset_name}")
                self.library_name = library.name
                return library

    def check(self):
        """
        Check if this asset's file exists and is already linked.
        """
        file_path = schalotte.find_asset_blend(
            self.asset_name,
            self.asset_type_name,
        )
        if not file_path:
            return
        self.file_path = file_path.as_posix()

        # Check if the asset is linked
        if not self.get_library():
            log.debug(f"Asset {self.asset_name} is not linked yet.")

    def link(self) -> Library | None:
        """
        Link this asset.

        Returns:
            Library | None: The asset's library
        """
        log.debug(f"Linking {self.file_path}")
        with bpy.data.libraries.load(  # type: ignore
            filepath=self.file_path,
            link=True,
            relative=True,
        ) as (data_from, data_to):
            data_to.collections = data_from.collections

        return self.get_library()

    def get_or_link_asset_collection(self) -> Collection | None:
        """
        Get or link this asset's main collection.

        Returns:
            Collection | None: The asset's main collection
        """
        library = self.get_library()
        if not library:
            library = self.link()
            if not library:
                return
        for collection in bpy.data.collections:
            if collection.library is library and collection.name.startswith("#"):
                return collection

        log.error(f"Could not find {self.asset_name} collection")

    def get_target_collection(self) -> Collection | None:
        """
        Find the target collection for this asset.

        Returns:
            Collection | None
        """
        target_collection = schalotte.find_asset_type_collection(self.asset_type_name)
        if target_collection:
            return target_collection
        log.error(
            f"Cannot find collection for {self.asset_name}: {self.asset_type_name}"
        )

    def add_instance(self) -> Object | None:
        """
        Add an instance of this asset's collection.

        Args:
            Collection

        Returns:
            Object | None: The instance object
        """
        asset_collection = self.get_or_link_asset_collection()
        if not asset_collection:
            return
        target_collection = self.get_target_collection()
        if not target_collection:
            return

        instance_obj = bpy.data.objects.new(self.asset_name, None)
        instance_obj.instance_type = "COLLECTION"
        instance_obj.instance_collection = asset_collection
        target_collection.objects.link(instance_obj)
        return instance_obj

    def add_override(
        self,
        make_editable: bool = True,
        scene: Scene | None = None,
        view_layer: ViewLayer | None = None,
    ) -> Collection | None:
        """
        Add an override of this asset's collection.

        Args:
            make_editable (bool): Whether to make the instance editable
            scene (Scene): Scene to use for the override, if not context
            view_layer (ViewLayer): View layer to use for the override, if not context

        Returns:
            Collection | None: The override collection
        """
        asset_collection = self.get_or_link_asset_collection()
        if not asset_collection:
            return
        target_collection = self.get_target_collection()
        if not target_collection:
            return

        if not scene:
            scene = bpy.context.scene
        if not view_layer:
            view_layer = bpy.context.view_layer

        override_collection = asset_collection.override_hierarchy_create(
            scene,  # type: ignore
            view_layer,  # type: ignore
            do_fully_editable=make_editable,
        )

        # Unlink from scene collection
        scene.collection.children.unlink(override_collection)

        # Link to target collection
        target_collection.children.link(override_collection)

        return override_collection

    def append(self) -> Collection | None:
        """
        Append this asset's collection.

        Returns:
            Collection | None: The override collection
        """
        asset_collection = self.get_or_link_asset_collection()
        if not asset_collection:
            return
        target_collection = self.get_target_collection()
        if not target_collection:
            return

        # Append collection
        col = utils.append_collection(self.file_path, asset_collection.name)
        if not col:
            return

        # Link to target
        target_collection.children.link(col)

        return col


@catalog.bpy_window_manager
class Casting(catalog.WindowManagerModule):
    """Module fetch and manage shot breakdown casting"""

    module: str = "casting"

    links: CollectionProperty(type=CastingLink)
    breakdown_file: StringProperty(name="Breakdown File", subtype="FILE_PATH")

    if TYPE_CHECKING:
        links: list[CastingLink]

    def fetch_entity_breakdown(self, project_id: str, entity_id: str):
        """
        Fetch the breakdown of a given entity (project or episode).
        """
        if TYPE_CHECKING:
            link: CastingLink

        self.links.clear()
        self.breakdown_file = bpy.data.filepath

        casting = client.Client.this().fetch_list(
            f"projects/{project_id}/entities/{entity_id}/casting",
            {"skip_cache": True},
        )

        for link_dict in casting:
            link = self.links.add()  # type: ignore
            link.from_dict(link_dict)
            link.check()
