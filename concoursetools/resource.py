# (C) Crown Copyright GCHQ
"""
Resources are the heart and soul of Concourse.They represent all
external inputs to and outputs of :concourse:`jobs` in the pipeline.

Each resource represents a versioned artifact with an external source of truth.
Configuring the same resource in any pipeline on any Concourse cluster will
behave the exact same way. Concourse will continuously check each configured
resource to discover new versions. These versions then flow through the pipeline
via :concourse:`get steps <get-step.get-step>` configured on jobs.

Find out more about resources in the :concourse:`Concourse resource documentation <resources>`.

To learn more about how Concourse resource types are actually implemented under the hood,
check out :concourse:`implementing-resource-types` in Concourse.
"""
from abc import ABC, abstractmethod
import contextlib
import pathlib
import sys
from typing import Generic, List, Optional, Tuple, Type

from concoursetools import parsing
from concoursetools.metadata import BuildMetadata
from concoursetools.typing import Metadata, Params, ResourceConfig
from concoursetools.version import VersionT


class ConcourseResource(ABC, Generic[VersionT]):
    """
    Represents an external input or output to a pipeline.

    The :concourse:`resource-types.schema.resource_type.source`
    defined in a Concourse :concourse:`pipeline <pipelines>` is
    parsed into JSON by Concourse, and will be passed to the initialiser
    of the :class:`ConcourseResource` class.

    All resource logic is contained in three methods to be overloaded:
    :meth:`fetch_new_versions`, :meth:`download_version` and :meth:`publish_new_version`.

    :param version_class: The resource parses all inputs with this version class.

    :Example:

        A resource that looks like this:

        .. code-block:: yaml

          resources:
            - name: my-resource
              type: my-resource-type
              source:
                project_key: concourse
                repo: concourse
                file_path: README.md

        would translate to a resource a little like this:

        .. code-block:: python3

            class MyResource(ConcourseResource):

                def __init__(self, project_key, repo, file_path, host="https://github.com/"):
                    super().__init__(MyVersion)
                    self.project_key = project_key
                    self.repo = repo
                    self.file_path = file_path
                    self.host = host.rstrip("/")

        If the source contains lists or mappings, then these will be passed as
        :class:`list` and :class:`dict` types respectively. The call to
        :code:`super().__init__` sets the version class (a subclass of
        :class:`~concoursetools.version.Version`) to be used by the resource,
        ensuring that output can be properly parsed.

        .. tip::

            Note that the ``__init__`` method has a default value for host,
            meaning that pipeline users need not include it in their source configuration.
            The parameters need not be set as attributes if they can all be combined
            into a single class, such as an API wrapper or other construct.
    """
    def __init__(self, version_class: Type[VersionT]):
        self.version_class = version_class

    @property
    def certs_dir(self) -> pathlib.Path:
        """
        The path to the Concourse worker's certificate directory.

        .. warning::

            This folder may not always exist, depending on how the Concourse runner was configured.

        See the :concourse:`implementing-resource-types.resource-certs` documentation for more information.
        """
        return pathlib.Path("/etc/ssl/certs")

    @abstractmethod
    def fetch_new_versions(self, previous_version: Optional[VersionT] = None) -> List[VersionT]:
        """
        Fetch new versions of the resource.

        The method will be passed the previous version (an instance of the :class:`~concoursetools.version.Version`
        class) if it exists, or :obj:`None` if this is the first version. It should return a list of version instances
        in **chronological order with the oldest first**, "including the requested version if it's still valid.".

        .. attention::

            That means that if nothing has changed, you should return :code:`[previous_version]`.
            Since get steps are cached by Concourse, this will **not** kick anything off.

        .. important::

            If there was no previous version, then this method should **only** return the latest version,
            and **not** every version from the past. This is also the case if it is impossible to determine
            newer versions due to something wrong with the external resource, such as a git repo which has been
            force pushed and can no longer be properly compared.

        :param previous_version: The most recent version of the resource. This will be set to :obj:`None`
                                 if the resource has never been run before.
        :returns: A list of new versions.
        """

    @abstractmethod
    def download_version(self, version: VersionT, destination_dir: pathlib.Path, build_metadata: BuildMetadata) -> Tuple[VersionT, Metadata]:
        """
        Download a version and place its files within the resource directory in your pipeline.

        This method is called on a get step, and the step parameters are passed as additional
        keyword arguments. The method should return the version (unchanged, although *technically*
        one could alter it slightly to no real effect), and a dictionary of metadata (see :ref:`Step Metadata`).

        .. note::

            If the desired resource version is unavailable (for example, if it was deleted),
            the script must exit with error.

        :Example:

            If the resource code looks like this:

            .. code:: python3

                class MyResource(ConcourseResource):

                    def download_version(self, version, destination_dir, build_metadata,
                                         download_metadata=False, metadata_file_name="metadata.json"):
                        ...
                        metadata = {
                            "HTTP Status": 200,
                        }
                        return version, metadata

            then the resource user would invoke it in the pipeline like this:

            .. code:: yaml

              - get: my-resource
                params:
                  download_metadata: true

        .. tip::

            Any version returned by the :meth:`publish_new_version` method is passed to
            this method due to an implicit get step. The pipeline user has the option to
            set some additional parameters for this step, and so if you intend to upload
            something large in your put step, it might be worth including a flag in this
            method to skip re-downloading that data.

        :param version: The version to be downloaded.
        :param destination_dir: A path to a folder into which resource files should be placed.
        :param build_metadata: Metadata associated with this build.
        :returns: The version (most likely unchanged), and a dictionary of metadata.
        """

    @abstractmethod
    def publish_new_version(self, sources_dir: pathlib.Path, build_metadata: BuildMetadata) -> Tuple[VersionT, Metadata]:
        """
        Update a resource by publishing a new version.

        This method is called on a put step, and the step parameters are passed as additional
        keyword arguments. The method should return the new, and a dictionary of metadata
        (see :ref:`Step Metadata`).

        .. warning::

            The ``sources_dir`` argument does **not** behave the same as the ``destination_dir``
            argument passed to the :meth:`~concoursetools.resource.ConcourseResource.download_version`
            method. This is to more easily enable the resource to interact with other resources
            (and task outputs), but makes it difficult to "track down" the files relating to
            *this* resource. This is a deliberate design decision by Concourse, and you should
            expect users to explicitly pass the path to those files should they be needed in this method.

        :Example:

            If the resource code looks like this:

            .. code:: python3

                class MyResource(ConcourseResource):

                    def publish_new_version(self, sources_dir, build_metadata,
                                            file_path, overwrite=False):
                        ...
                        metadata = {
                            "HTTP Status": 200,
                        }
                        return version, metadata

            then the resource user would invoke it in the pipeline like this:

            .. code:: yaml

              - put: my-resource
                params:
                  file_path: path/to/file.txt
                  overwrite: true

        :param sources_dir: A path to folder containing all resources, **not** just this resource.
        :param build_metadata: Metadata associated with this build.
        :returns: The new version, and a dictionary of metadata.
        """

    @classmethod
    def check_main(cls) -> None:
        """
        Check for new versions.

        .. caution::
            This method should not be overloaded.

        :returns: This method only prints output to ``stdout`` and ``stderr``.
        """
        resource, previous_version = cls._parse_check_input()
        with contextlib.redirect_stdout(sys.stderr):
            new_versions = resource.fetch_new_versions(previous_version)
        output = parsing.format_check_output([version.to_flat_dict() for version in new_versions])
        _output(output)

    @classmethod
    def in_main(cls) -> None:
        """
        Fetch a given resource.

        .. caution::
            This method should not be overloaded.

        :returns: This method only prints output to ``stdout`` and ``stderr``.
        """
        resource, version, destination_dir, params = cls._parse_in_input()
        build_metadata = BuildMetadata.from_env()
        with contextlib.redirect_stdout(sys.stderr):
            version, metadata = resource.download_version(version, destination_dir, build_metadata, **params)
        output = parsing.format_in_out_output(version.to_flat_dict(), metadata)
        _output(output)

    @classmethod
    def out_main(cls) -> None:
        """
        Update a resource.

        .. caution::
            This method should not be overloaded.

        :returns: This method only prints output to ``stdout`` and ``stderr``.
        """
        resource, sources_dir, params = cls._parse_out_input()
        build_metadata = BuildMetadata.from_env()
        with contextlib.redirect_stdout(sys.stderr):
            version, metadata = resource.publish_new_version(sources_dir, build_metadata, **params)
        output = parsing.format_in_out_output(version.to_flat_dict(), metadata)
        _output(output)

    @classmethod
    def _parse_check_input(cls) -> Tuple["ConcourseResource[VersionT]", Optional[VersionT]]:
        """Parse input from the command line."""
        check_payload = sys.stdin.read()

        resource_config, previous_version_config = parsing.parse_check_payload(check_payload)

        resource = cls._from_resource_config(resource_config)

        if previous_version_config is None:
            previous_version = None
        else:
            previous_version = resource.version_class.from_flat_dict(previous_version_config)

        return resource, previous_version

    @classmethod
    def _parse_in_input(cls) -> Tuple["ConcourseResource[VersionT]", VersionT, pathlib.Path, Params]:
        """Parse input from the command line."""
        in_payload = sys.stdin.read()

        try:
            destination_dir = pathlib.Path(sys.argv[1])
        except IndexError as error:
            raise ValueError("Path to the destination directory for the resource "
                             "must be passed to the command line") from error

        resource_config, version_config, params = parsing.parse_in_payload(in_payload)

        resource = cls._from_resource_config(resource_config)
        version = resource.version_class.from_flat_dict(version_config)

        return resource, version, destination_dir, params

    @classmethod
    def _parse_out_input(cls) -> Tuple["ConcourseResource[VersionT]", pathlib.Path, Params]:
        """Parse input from the command line."""
        out_payload = sys.stdin.read()

        try:
            sources_dir = pathlib.Path(sys.argv[1])
        except IndexError as error:
            raise ValueError("Path to the directory containing the build's full set of sources "
                             "must be passed to the command line") from error

        resource_config, params = parsing.parse_out_payload(out_payload)

        resource = cls._from_resource_config(resource_config)

        return resource, sources_dir, params

    @classmethod
    def _from_resource_config(cls, resource_config: ResourceConfig) -> "ConcourseResource[VersionT]":
        return cls(**resource_config)


def _output(payload: str) -> None:
    """
    Output data to Concourse to be carried to the next step.

    This function is more or less equivalent to :func:`print`.
    """
    print(payload, file=sys.stdout)
