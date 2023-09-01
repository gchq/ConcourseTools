# (C) Crown Copyright GCHQ
"""
Concourse Tools comes with some additional resource type "patterns" to cover some common requirements.
"""
from abc import abstractmethod
from dataclasses import dataclass
from datetime import datetime
import json
import pathlib
from typing import Any, Dict, Generic, List, Optional, Set, Tuple, Type

from concoursetools import ConcourseResource
from concoursetools.metadata import BuildMetadata
from concoursetools.typing import Metadata, MultiVersionT, ResourceConfig, SortableVersionT, VersionConfig, VersionT
from concoursetools.version import TypedVersion, Version


class OutOnlyConcourseResource(ConcourseResource[VersionT]):
    """
    A version-less Concourse resource which can only run "out" code.

    This resource implements check and in as "no-ops". It can not be used
    in a get step, or to trigger builds. If you only need your resource to
    run code on a put step, then it is useful to inherit from this class
    instead to avoid needing to think about the relevant methods.

    :param version_class: The resource parses all inputs with this version class.
    """
    def fetch_new_versions(self, previous_version: Optional[VersionT] = None) -> List[VersionT]:
        return []

    def download_version(self, version: VersionT, destination_dir: pathlib.Path, build_metadata: BuildMetadata) -> Tuple[VersionT, Metadata]:
        metadata: Dict[str, str] = {}
        return version, metadata


@dataclass(unsafe_hash=True)
class DatetimeVersion(TypedVersion):
    """
    A placeholder version containing only the time at which it was created.
    """
    execution_date: datetime

    @classmethod
    def now(cls) -> "DatetimeVersion":
        """Return the version corresponding to now."""
        return cls(datetime.now())


class InOnlyConcourseResource(ConcourseResource[DatetimeVersion]):
    """
    A version-less Concourse resource which acts like an external function.

    The common use-case of a :class:`OutOnlyConcourseResource` in a Concourse pipeline
    is to run a "function". The only way that this can "return" anything is if the
    result of the run is stored externally in your resource. This resource allows the
    user to "fetch" something from an external resource when this is *not* the case.

    .. note::

        The user should overload :meth:`download_data` instead of
        :meth:`~concoursetools.resource.ConcourseResource.download_version`.

    The correct use case of this resource is to execute a
    :concourse:`put-step.put-step`, and then place parameters
    in the :concourse:`put-step.schema.put.get_params` section:

    .. code:: yaml

        - put: app-image
          get_params:
            skip_download: true

    .. note::
        This resource used a pre-defined version consisting of a single
        :class:`~datetime.datetime` object to ensure unique, non-empty versions.
    """
    def __init__(self) -> None:
        super().__init__(DatetimeVersion)

    def fetch_new_versions(self, previous_version: Optional[DatetimeVersion] = None) -> List[DatetimeVersion]:
        return []

    def download_version(self, version: DatetimeVersion, destination_dir: pathlib.Path, build_metadata: BuildMetadata,
                         **kwargs: Any) -> Tuple[DatetimeVersion, Metadata]:
        metadata = self.download_data(destination_dir, build_metadata, **kwargs)
        return version, metadata

    def publish_new_version(self, sources_dir: pathlib.Path, build_metadata: BuildMetadata) -> Tuple[DatetimeVersion, Metadata]:
        version = DatetimeVersion.now()
        return version, {}

    @abstractmethod
    def download_data(self, destination_dir: pathlib.Path, build_metadata: BuildMetadata) -> Metadata:
        """
        Download resource data and place files within the resource directory in your pipeline.

        .. note::
            This method is deliberately **not** passed a :class:`~concoursetools.version.Version` instance.

        :Example:

            Consider a resource to download an image from an unversioned URL.

            .. code:: python3

                import requests

                class MyResource(InOnlyConcourseResource):

                    def __init__(self, image_url: str):
                        super().__init__()
                        self.image_url = image_url

                    def download_data(self, destination_dir, build_metadata,
                                      name: str = "image", chunk_size: int = 1024):
                        response = requests.get(self.image_url, stream=True)
                        response.raise_for_status()

                        image_path = destination_dir / name
                        with open(image_path, "wb") as wf:
                            for chunk in response.iter_content(chunk_size):
                                wf.write(chunk)

                        metadata = {
                            "HTTP Status": response.status_code,
                        }
                        return metadata

            then the resource user would invoke it in the pipeline like this:

            .. code:: yaml

              - put: my-resource
                get_params:
                  name: my_image.png

        :param destination_dir: A path to a folder into which resource files should be placed.
        :param build_metadata: Metadata associated with this build.
        :returns: A dictionary of metadata.
        """


class TriggerOnChangeConcourseResource(ConcourseResource[VersionT]):
    """
    A Concourse resource which emits a new version whenever something has changed.

    Only use this resource if you will never have any intermittent versions,
    and if linear versioning is not valid in this scenario. You should ensure that
    two instances of the version class can be :ref:`checked for equality <Version Comparisons>`.
    If the latest version and the previous version match, then this resource will **not**
    emit a version, even if changes technically occurred between checks.

    .. note::

        The user should overload :meth:`fetch_latest_version` instead of
        :meth:`~concoursetools.resource.ConcourseResource.fetch_new_versions`.

    :param version_class: The resource parses all inputs with this version class.
    """
    def fetch_new_versions(self, previous_version: Optional[VersionT] = None) -> List[VersionT]:
        latest_version = self.fetch_latest_version()

        if previous_version is None:
            versions = [latest_version]
        elif latest_version == previous_version:
            versions = [previous_version]
        else:
            versions = [previous_version, latest_version]

        return versions

    @abstractmethod
    def fetch_latest_version(self) -> VersionT:
        """
        Fetch the latest version of the resource.

        :returns: The latest version of the resource.
        """


class MultiVersion(Version, Generic[SortableVersionT]):
    """
    Wraps multiple versions into a single class.

    .. caution::
        Users shouldn't invoke this version outside of the :class:`MultiVersionConcourseResource` class.

    :param versions: A (specifically unordered) collection of subversions to be contained in a single version.

    .. tip::
        Two multi-versions are equal if their respective set of subversions are also equal.
    """
    _key: str = "versions"
    _sub_version_class: Type[SortableVersionT] = Version  # type: ignore[assignment]

    def __init__(self, versions: Set[SortableVersionT]):
        self.versions = versions

    def __eq__(self, other: Any) -> bool:
        return bool(self.versions == other.versions)

    @property
    def key(self) -> str:
        """Return the key used for the JSON encoded version data."""
        return self._key

    @property
    def sub_version_class(self) -> Type[SortableVersionT]:
        """Return the class used to parse the subversions."""
        return self._sub_version_class

    @property
    def sub_version_data(self) -> List[VersionConfig]:
        """
        Return a list of flattened subversions.

        This is created by calling :meth:`~concoursetools.version.Version.to_flat_dict` on each subversion.
        """
        sorted_versions = sorted(self.versions)
        return [version.to_flat_dict() for version in sorted_versions]

    def to_flat_dict(self) -> VersionConfig:
        """
        Convert the instance to a dictionary with string fields.

        The resulting version has a single key/value pair, mapping
        :attr:`key` to the :attr:`sub_version_data` as a JSON-encoded string.
        """
        return {
            self.key: json.dumps(self.sub_version_data),
        }

    @classmethod
    def from_flat_dict(cls: "Type[MultiVersion[SortableVersionT]]", version_dict: VersionConfig) -> "MultiVersion[SortableVersionT]":
        """
        Load an instance from a dictionary representing the version.

        This works by extracting the key (given by :attr:`key`)
        from the mapping, decoding the corresponding JSON blob
        and loading each sub-configuration using the :attr:`sub_version_class`.

        :param version_dict: A string-only key/value dictionary representing the multi-version.
        """
        data = version_dict[cls._key]
        sub_version_dicts: List[VersionConfig] = json.loads(data)
        versions = {cls._sub_version_class.from_flat_dict(sub_version_dict) for sub_version_dict in sub_version_dicts}
        return cls(versions)


def _create_multi_version_class(key: str, sub_version_class: Type[SortableVersionT]) -> Type[MultiVersion[SortableVersionT]]:
    """Create a new version subclass containing multiple sub-versions."""
    class NewMultiVersion(MultiVersion[SortableVersionT]):
        _key = key
        _sub_version_class = sub_version_class

    return NewMultiVersion


class MultiVersionConcourseResource(TriggerOnChangeConcourseResource[MultiVersionT]):
    """
    A Concourse resource type designed to trigger to a change in available versions.

    Sometimes a resource is designed to track a set of available items at any given time,
    and to emit a new version when that set changes. This resource treats each item as a "sub-version",
    and tracks the set of these sub-versions at the source through an implicit "multi-version" class.

    The default behaviour for :meth:`download_version` is to create a JSON file containing a list
    of the flattened versions, which can be used within the pipeline. By default this resource does
    not publish new versions.

    :param key: When the multi-version class is flattened, the sub-versions are cast to a sorted list
                and encoded as a JSON string. The final version consists of a single key/value pair,
                with the value being the JSON string and the key being this one.
    :param sub_version_class: A subclass of :class:`~concoursetools.version.Version` to be used for each sub-version.
                              Equality of these classes is what checks that the total set has changed.
                              This class **must** be sortable.

    .. warning::
        The sub-version class **must** be :ref:`sortable <Ordering>`. Sub-versions are sorted prior to flattening
        to ensure consistency in the final flattened payload.

    .. tip::
        This resource class is best suited to resources used in conjunction
        with the :concourse:`set-pipeline-step`.
    """
    def __init__(self, key: str, sub_version_class: Type[SortableVersionT]):
        self.key = key
        multi_version_class = _create_multi_version_class(key, sub_version_class)
        super().__init__(multi_version_class)

    def fetch_latest_version(self) -> MultiVersionT:
        latest_sub_versions = self.fetch_latest_sub_versions()
        multi_version = self.version_class(latest_sub_versions)
        return multi_version

    @abstractmethod
    def fetch_latest_sub_versions(self) -> Set[Version]:
        """
        Fetch the latest sub versions from the resource.

        :returns: A set of the latest subversions from the resource.
        """
        ...

    def download_version(self, version: MultiVersionT, destination_dir: pathlib.Path, build_metadata: BuildMetadata,
                         file_name: Optional[str] = None, indent: Optional[int] = None) -> Tuple[MultiVersionT, Metadata]:
        """
        Download a JSON file containing the sub-version data.

        :param version: The version to be downloaded.
        :param destination_dir: A path to a folder into which resource files should be placed.
        :param build_metadata: Metadata associated with this build.
        :param file_name: The name of the file. Defaults to the ``key`` parameter passed to the resource class.
        :param indent: An optional indent for the JSON file. Only useful if you care about formatting.
        :returns: The unchanged version and an empty dictionary of metadata.
        """
        file_path = destination_dir / f"{file_name or self.key}.json"
        file_path.write_text(json.dumps(version.sub_version_data, indent=indent))
        return version, {}

    def publish_new_version(self, sources_dir: pathlib.Path, build_metadata: BuildMetadata) -> Tuple[MultiVersionT, Metadata]:
        raise TypeError("Publishing new versions of this resource is not permitted.")


class SelfOrganisingConcourseResource(ConcourseResource[SortableVersionT]):
    """
    A Concourse resource which orders and filters versions on your behalf.

    Users should rely on the resource to deduce the new versions from a list of
    all versions, and the order in which they should be presented. This is useful
    for simplifying logic in certain scenarios, but requires that versions can be
    :ref:`ordered <Version Comparisons>`.

    .. note::

        The user should overload :meth:`fetch_all_versions` instead of
        :meth:`~concoursetools.resource.ConcourseResource.fetch_new_versions`.

    .. caution::
        This is not always easy to do when chronology is determined by the ordering
        of a web response, for example, instead of a value within the version itself.
        However, it does avoid the need to remember the order in which new versions
        should be returned.

    :param version_class: The resource parses all inputs with this version class.
    """
    def fetch_new_versions(self, previous_version: Optional[SortableVersionT] = None) -> List[SortableVersionT]:
        all_versions = self.fetch_all_versions()
        try:
            newest_version = max(all_versions)
        except ValueError as error:
            if not all_versions:
                return []
            raise RuntimeError("Could not compare versions as expected.") from error

        if previous_version is None:
            return [newest_version]

        versions = sorted(version for version in all_versions if previous_version < version)
        if not versions:
            versions = [previous_version]

        return versions

    @abstractmethod
    def fetch_all_versions(self) -> Set[SortableVersionT]:
        """
        Fetch every available version of the resource.

        .. note::

            As usual, If there are no new versions, the list of new versions
            should only include the previous version.

        :returns: A list of every resource version.
        """


class _PseudoConcourseResource(ConcourseResource[VersionT]):

    def __new__(cls) -> "_PseudoConcourseResource[VersionT]":
        raise TypeError(f"Cannot instantiate a {cls.__name__} type")


def combine_resource_types(resources: Dict[str, Type[ConcourseResource[VersionT]]],
                           param_key: str = "resource") -> Type[_PseudoConcourseResource[VersionT]]:
    """
    Return a pseudo-resource which will delegate to other resources depending on a flag.

    Returns a pseudo-:class:`~concoursetools.resource.ConcourseResource` class which delegates to other resources
    depending on the flag passed in the resource config.

    .. warning::
        This pseudo-resource cannot be instantiated as normal, and can only be run via the :ref:`Main Scripts`.

    :param resources: A mapping of key to :class:`~concoursetools.resource.ConcourseResource` subclass.
                      The delegated user is selected with the key.
    :param param_key: The key in the resource config used to select the resource from ``resources``.
                      The value is popped from the config before it is passed to the delegate.

    :Example:
        >>> resources = {
        ...     "A": ResourceA,
        ...     "B": ResourceB,
        ... }
        >>> CombinedResource = combine_resource_types(resources)

        This is then instantiated like so:

        .. code:: yaml

            resources:
              - name: my-resource
                type: multi-resource-type
                source:
                  resource: A
                  ...
    """
    class MultiResourceConcourseResource(_PseudoConcourseResource[VersionT]):
        """
        A special Resource class which delegates to multiple other resource classes.
        """
        @classmethod
        def _from_resource_config(cls, resource_config: ResourceConfig) -> "ConcourseResource[VersionT]":
            try:
                resource_key = resource_config.pop(param_key)
            except KeyError:
                raise ValueError(f"Missing flag: {param_key!r}")

            try:
                resource_class = resources[resource_key]
            except KeyError:
                possible = set(resources)
                raise KeyError(f"Couldn't find resource matching {resource_key!r}: possible options: {possible}")

            return resource_class(**resource_config)

    return MultiResourceConcourseResource
