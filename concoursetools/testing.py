# (C) Crown Copyright GCHQ
"""
Concourse Tools contains a number of functions for easier testing.

You can take advantage of the class-based paradigm in Concourse Tools
to test your resource class as a standard Python object. You can call
the functions with specific inputs to check that they are turning the
correct outputs. However, this does limit your ability to mock the
script environment when your code relies on external factors.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Callable, Generator
from contextlib import contextmanager, redirect_stdout
from io import StringIO
import json
from pathlib import Path
import secrets
import subprocess
from tempfile import TemporaryDirectory
from typing import Any, Generic, TypeVar

from concoursetools import BuildMetadata, ConcourseResource, Version
from concoursetools.dockertools import MethodName, ScriptName, create_script_file
from concoursetools.mocking import StringIOWrapper, TemporaryDirectoryState, create_env_vars, mock_argv, mock_environ, mock_stdin
from concoursetools.parsing import format_check_input, format_in_input, format_out_input, parse_metadata
from concoursetools.typing import Metadata, MetadataPair, Params, ResourceConfig, VersionConfig, VersionT

T = TypeVar("T")
ContextManager = Generator[T, None, None]
FolderDict = dict[str, Any]


class TestResourceWrapper(ABC, Generic[VersionT]):
    r"""
    A simplistic resource wrapper designed to reduce test code.

    The most accurate way to test your resource class is to invoke a test wrapper.
    Each one inherits from this class, and exposes a method for each of the three
    resource operations: :meth:`fetch_new_versions`, :meth:`download_version` and
    :meth:`publish_new_version`.

    .. tip::
        Make use of the :meth:`capture_debugging` and :meth:`capture_directory_state`
        methods to capture the debugging output and directory state changes respectively.

    :param directory_dict: The initial state of the resource directory. See :class:`~concoursetools.mocking.TemporaryDirectoryState`
    :param one_off_build: Set to :data:`True` if you are testing a one-off build.
    :param instance_vars: Pass optional instance vars to emulate an instanced pipeline.
    :param env_vars: Pass additional environment variables, or overload the default ones.

    .. caution::
        Each wrapper will use different signatures for these methods to reflect the different ways
        that inputs can be passed to the inner resource. Make sure to select the wrapper which works
        best for how you wish to test your resource.

    :Example:
        >>> from tests.resource import TestResource, TestVersion
        >>> resource = TestResource("git://some-uri")
        >>> wrapper = SimpleTestResourceWrapper(resource)
        >>> version = TestVersion("61cbef")
        >>> with wrapper.capture_debugging() as debugging:
        ...     with wrapper.capture_directory_state() as directory_state:
        ...         _, metadata = wrapper.download_version(version)
        ...     assert directory_state.final_state == {"README.txt": "Downloaded README for ref 61cbef.\n"}
        ...     assert metadata == {"team_name": "my-team"}
        ...     assert debugging == "Downloading.\n"
    """
    def __init__(self, directory_dict: FolderDict | None = None, one_off_build: bool = False,
                 instance_vars: dict[str, str] | None = None, **env_vars: str) -> None:
        self.mocked_environ = create_env_vars(one_off_build, instance_vars, **env_vars)
        self.directory_dict = directory_dict

        self._debugging_output = StringIOWrapper()
        self._directory_state = TemporaryDirectoryState(self.directory_dict)

    @abstractmethod
    def fetch_new_versions(self) -> object:
        """Fetch new versions of the resource."""

    @abstractmethod
    def download_version(self) -> object:
        """Download a version and place its files within the resource directory in your pipeline."""

    @abstractmethod
    def publish_new_version(self) -> object:
        """
        Update a resource by publishing a new version.
        """

    @contextmanager
    def capture_debugging(self) -> ContextManager[StringIOWrapper]:
        """
        Redirect the resource debugging output within a context manager into a variable.

        :seealso: This is done using an instance of :class:`~concoursetools.mocking.StringIOWrapper`.
                  A call is made to :meth:`~concoursetools.mocking.StringIOWrapper.clear` when the
                  context manager is opened.

        .. note::
            The output is directed regardless of whether this is used.
        """
        self._debugging_output.clear()
        yield self._debugging_output

    @contextmanager
    def capture_directory_state(self, starting_state: FolderDict | None = None) -> ContextManager["TemporaryDirectoryState"]:
        """
        Open a context manager to expose the internal state of the resource.

        :param starting_state: Set the starting state of the directory. If not set this defaults to the starting state
                               as passed to the instance via the ``directory_dict`` parameter.

        :seealso: This is done using an instance of :class:`~concoursetools.mocking.TemporaryDirectoryState`.

        .. note::
            It is impossible to call the :meth:`fetch_new_versions` method from within this context manager.
        """
        old_start_state = self._directory_state.starting_state
        with self._forbid_methods(self.fetch_new_versions):
            try:
                if starting_state is not None:
                    self._directory_state.starting_state = starting_state
                yield self._directory_state
            finally:
                self._directory_state.starting_state = old_start_state

    @contextmanager
    def _forbid_methods(self, *methods: Callable[..., object]) -> ContextManager[None]:
        try:
            for method in methods:
                def new_method(*args: object, **kwargs: object) -> object:
                    raise RuntimeError(f"Cannot call {method.__name__} from within this context manager.")
                setattr(self, method.__name__, new_method)
            yield
        finally:
            for method in methods:
                setattr(self, method.__name__, method)


class SimpleTestResourceWrapper(TestResourceWrapper[VersionT]):
    """
    A simplistic resource wrapper designed to reduce test code.

    The only real functionality of this wrapper is to mock arguments
    such as the :ref:`Build Metadata` and the directory paths.

    .. tip::
        This is best to use if want to invoke your resource code with as little effort as possible.

    :param inner_resource: The resource to be wrapped.
    :param directory_dict: The initial state of the resource directory. See :class:`~concoursetools.mocking.TemporaryDirectoryState`
    :param one_off_build: Set to :data:`True` if you are testing a one-off build.
    :param instance_vars: Pass optional instance vars to emulate an instanced pipeline.
    :param env_vars: Pass additional environment variables, or overload the default ones.
    """
    def __init__(self, inner_resource: ConcourseResource[VersionT], directory_dict: FolderDict | None = None,
                 one_off_build: bool = False, instance_vars: dict[str, str] | None = None, **env_vars: str) -> None:
        super().__init__(directory_dict, one_off_build, instance_vars, **env_vars)
        self.inner_resource = inner_resource
        self.mocked_build_metadata = BuildMetadata(**self.mocked_environ)

    def fetch_new_versions(self, previous_version: VersionT | None = None) -> list[VersionT]:
        """
        Fetch new versions of the resource.

        Calls the inner resource whilst capturing debugging output.

        :param previous_version: The most recent version of the resource. This will be set to :data:`None`
                                 if the resource has never been run before.
        :returns: A list of new versions.
        """
        with self._debugging_output.capture_stdout_and_stderr():
            return self.inner_resource.fetch_new_versions(previous_version=previous_version)

    def download_version(self, version: VersionT, **params: object) -> tuple[VersionT, Metadata]:
        """
        Download a version and place its files within the resource directory in your pipeline.

        Calls the inner resource whilst capturing debugging output and passing a temporary
        directory as the destination directory.

        :param version: The version to be downloaded.
        :param params: Additional keyword parameters passed to the inner resource.
        :returns: The version (most likely unchanged), and a dictionary of metadata.
        """
        with self._debugging_output.capture_stdout_and_stderr():
            with self._directory_state:
                return self.inner_resource.download_version(version, self._directory_state.path, self.mocked_build_metadata, **params)

    def publish_new_version(self, **params: object) -> tuple[VersionT, Metadata]:
        """
        Update a resource by publishing a new version.

        Calls the inner resource whilst capturing debugging output and passing a temporary
        directory as the sources directory.

        :param params: Additional keyword parameters passed to the inner resource.
        :returns: The new version, and a dictionary of metadata.
        """
        with self._debugging_output.capture_stdout_and_stderr():
            with self._directory_state:
                return self.inner_resource.publish_new_version(self._directory_state.path, self.mocked_build_metadata, **params)


class JSONTestResourceWrapper(TestResourceWrapper[VersionT]):
    """
    A resource wrapper which interfaces directly with JSON configuration and :ref:`Main Scripts`.

    .. tip::
        This is best to use if you are concerned about the conversion of your resource and versions.

    :param inner_resource_type: The :class:`~concoursetools.resource.ConcourseResource` subclass corresponding to the resource.
    :param inner_resource_config: The JSON configuration for the resource.
    :param directory_dict: The initial state of the resource directory. See :class:`~concoursetools.mocking.TemporaryDirectoryState`
    :param one_off_build: Set to :data:`True` if you are testing a one-off build.
    :param instance_vars: Pass optional instance vars to emulate an instanced pipeline.
    :param env_vars: Pass additional environment variables, or overload the default ones.
    """
    def __init__(self, inner_resource_type: type[ConcourseResource[VersionT]], inner_resource_config: ResourceConfig,
                 directory_dict: FolderDict | None = None, one_off_build: bool = False,
                 instance_vars: dict[str, str] | None = None, **env_vars: str) -> None:
        super().__init__(directory_dict, one_off_build, instance_vars, **env_vars)
        self.inner_resource_type = inner_resource_type
        self.inner_resource_config = inner_resource_config

    def fetch_new_versions(self, previous_version_config: VersionConfig | None = None) -> list[VersionConfig]:
        """
        Fetch new versions of the resource.

        Mocks the environment and calls :meth:`~concoursetools.resource.ConcourseResource.check_main`.

        .. caution::
            No environment variables are available to the check script.

        :param previous_version_config: The JSON configuration of the most recent version of the resource.
                                        This will be set to :data:`None` if the resource has never been run before.
        :returns: A list of new version configurations.
        """
        stdin = format_check_input(self.inner_resource_config, previous_version_config)

        with redirect_stdout(StringIO()) as stdout_buffer:
            with self._debugging_output.capture_stderr():
                with mock_stdin(stdin):
                    with mock_argv("/opt/resource/check"):
                        with mock_environ({}):
                            self.inner_resource_type.check_main()
                stdout = stdout_buffer.getvalue()

        try:
            version_configs: list[VersionConfig] = json.loads(stdout)
        except json.JSONDecodeError as error:
            raise ValueError(f"Unexpected output: {stdout.strip()}") from error
        return version_configs

    def download_version(self, version_config: VersionConfig, params: Params | None = None) -> tuple[VersionConfig, list[MetadataPair]]:
        """
        Download a version and place its files within the resource directory in your pipeline.

        Mocks the environment and calls :meth:`~concoursetools.resource.ConcourseResource.in_main`.

        :param version_config: The JSON configuration of the version.
        :param params: A mapping of additional keyword parameters passed to the inner resource.
        :returns: The version configuration (most likely unchanged), and a list of metadata pairs.
        """
        stdin = format_in_input(self.inner_resource_config, version_config, params)

        with redirect_stdout(StringIO()) as stdout_buffer:
            with self._debugging_output.capture_stderr():
                with self._directory_state:
                    with mock_stdin(stdin):
                        with mock_argv("/opt/resource/in", str(self._directory_state.path)):
                            with mock_environ(self.mocked_environ):
                                self.inner_resource_type.in_main()
                stdout = stdout_buffer.getvalue()

        try:
            output = json.loads(stdout)
        except json.JSONDecodeError as error:
            raise ValueError(f"Unexpected output: {stdout.strip()}") from error
        new_version_config: VersionConfig = output["version"]
        metadata_pairs: list[MetadataPair] = output["metadata"] or []
        return new_version_config, metadata_pairs

    def publish_new_version(self, params: Params | None = None) -> tuple[VersionConfig, list[MetadataPair]]:
        """
        Update a resource by publishing a new version.

        Mocks the environment and calls :meth:`~concoursetools.resource.ConcourseResource.out_main`.

        :param params: A mapping of additional keyword parameters passed to the inner resource.
        :returns: The new version configuration, and a list of metadata pairs.
        """
        stdin = format_out_input(self.inner_resource_config, params)

        with redirect_stdout(StringIO()) as stdout_buffer:
            with self._debugging_output.capture_stderr():
                with self._directory_state:
                    with mock_stdin(stdin):
                        with mock_argv("/opt/resource/out", str(self._directory_state.path)):
                            with mock_environ(self.mocked_environ):
                                self.inner_resource_type.out_main()
                stdout = stdout_buffer.getvalue()

        try:
            output = json.loads(stdout)
        except json.JSONDecodeError as error:
            raise ValueError(f"Unexpected output: {stdout.strip()}") from error
        new_version_config: VersionConfig = output["version"]
        metadata_pairs: list[MetadataPair] = output["metadata"] or []
        return new_version_config, metadata_pairs


class ConversionTestResourceWrapper(JSONTestResourceWrapper[VersionT]):
    """
    A resource wrapper based on :class:`JSONTestResourceWrapper`, yet with the interface of :class:`SimpleTestResourceWrapper`.

    All inputs and outputs are instances, but are converted to and from JSON internally.

    .. tip::
        This is best to use if you want easier testing, but are still concerned
        about the conversion of your resource and versions.

    :param inner_resource_type: The :class:`~concoursetools.resource.ConcourseResource` subclass corresponding to the resource.
    :param inner_resource_config: The JSON configuration for the resource.
    :param directory_dict: The initial state of the resource directory. See :class:`~concoursetools.mocking.TemporaryDirectoryState`
    :param one_off_build: Set to :data:`True` if you are testing a one-off build.
    :param instance_vars: Pass optional instance vars to emulate an instanced pipeline.
    :param env_vars: Pass additional environment variables, or overload the default ones.
    """
    def __init__(self, inner_resource_type: type[ConcourseResource[VersionT]], inner_resource_config: ResourceConfig,
                 directory_dict: FolderDict | None = None, one_off_build: bool = False,
                 instance_vars: dict[str, str] | None = None, **env_vars: str) -> None:
        super().__init__(inner_resource_type, inner_resource_config, directory_dict, one_off_build, instance_vars, **env_vars)
        self.mocked_build_metadata = BuildMetadata(**self.mocked_environ)
        inner_resource = inner_resource_type(**inner_resource_config)
        self.inner_version_class = inner_resource.version_class

    def fetch_new_versions(self, previous_version: VersionT | None = None) -> list[VersionT]:
        """
        Fetch new versions of the resource.

        Converts the version (if it exists) to JSON, and then invokes :meth:`~JSONTestResourceWrapper.fetch_new_versions`.
        The response is then converted back to :class:`~concoursetools.version.Version` instances.

        :param previous_version: The most recent version of the resource. This will be set to :data:`None`
                                 if the resource has never been run before.
        :returns: A list of new versions.
        """
        previous_version_config = None if previous_version is None else previous_version.to_flat_dict()
        version_configs = super().fetch_new_versions(previous_version_config)
        return [self.inner_version_class.from_flat_dict(version_config) for version_config in version_configs]

    def download_version(self, version: VersionT, **params: object) -> tuple[VersionT, Metadata]:
        """
        Download a version and place its files within the resource directory in your pipeline.

        Converts the version to JSON, and then invokes :meth:`~JSONTestResourceWrapper.download_version`
        with the additional params as a :class:`dict`. The returned version configuration is then converted
        back to a :class:`~concoursetools.version.Version` instance, and the metadata pairs converted to
        a standard :class:`dict`.

        :param version: The version to be downloaded.
        :param params: Additional keyword parameters passed to the inner resource.
        :returns: The version (most likely unchanged), and a dictionary of metadata.
        """
        version_config = version.to_flat_dict()
        new_version_config, metadata_pairs = super().download_version(version_config, params or {})
        new_version = self.inner_version_class.from_flat_dict(new_version_config)
        metadata = parse_metadata(metadata_pairs)
        return new_version, metadata

    def publish_new_version(self, **params: object) -> tuple[VersionT, Metadata]:
        """
        Update a resource by publishing a new version.

        Invokes :meth:`~JSONTestResourceWrapper.publish_new_version` with the additional
        params as a :class:`dict`. The returned version configuration is then converted
        to a :class:`~concoursetools.version.Version` instance, and the metadata pairs
        converted to a standard :class:`dict`.

        :param params: Additional keyword parameters passed to the inner resource.
        :returns: The new version, and a dictionary of metadata.
        """
        new_version_config, metadata_pairs = super().publish_new_version(params or {})
        new_version = self.inner_version_class.from_flat_dict(new_version_config)
        metadata = parse_metadata(metadata_pairs)
        return new_version, metadata


class FileTestResourceWrapper(TestResourceWrapper[Version]):
    """
    A resource wrapper which calls arbitrary scripts.

    .. tip::
        This is best to use if your resource uses external scripts for any of the steps.

    :param inner_resource_config: The JSON configuration for the resource.
    :param check_script: The path to the external script for the :concourse:`check <implementing-resource-types.resource-check>`.
                         Setting to :data:`None` (default) means that :meth:`fetch_new_versions`
                         raises :class:`NotImplementedError`.
    :param in_script: The path to the external script for the :concourse:`check <implementing-resource-types.resource-in>`.
                      Setting to :data:`None` (default) means that :meth:`download_version`
                      raises :class:`NotImplementedError`.
    :param out_script: The path to the external script for the :concourse:`check <implementing-resource-types.resource-out>`.
                       Setting to :data:`None` (default) means that :meth:`publish_new_version`
                       raises :class:`NotImplementedError`.
    :param directory_dict: The initial state of the resource directory. See :class:`~concoursetools.mocking.TemporaryDirectoryState`
    :param one_off_build: Set to :data:`True` if you are testing a one-off build.
    :param instance_vars: Pass optional instance vars to emulate an instanced pipeline.
    :param env_vars: Pass additional environment variables, or overload the default ones.

    .. caution::
        If any of the paths for the scripts do not resolve, the corresponding methods will raise :class:`NotImplementedError`.
    """
    def __init__(self, inner_resource_config: ResourceConfig, check_script: Path | None = None,
                 in_script: Path | None = None, out_script: Path | None = None,
                 directory_dict: FolderDict | None = None, one_off_build: bool = False,
                 instance_vars: dict[str, str] | None = None, **env_vars: str) -> None:
        super().__init__(directory_dict, one_off_build, instance_vars, **env_vars)
        self.inner_resource_config = inner_resource_config
        self.check_script, self.in_script, self.out_script = check_script, in_script, out_script

    def fetch_new_versions(self, previous_version_config: VersionConfig | None = None) -> list[VersionConfig]:
        """
        Fetch new versions of the resource.

        Calls the external check script using :func:`run_script` with the correct environment.

        .. caution::
            No environment variables are available to the check script.

        :param previous_version_config: The JSON configuration of the most recent version of the resource.
                                        This will be set to :data:`None` if the resource has never been run before.
        :returns: A list of new version configurations.
        """
        if self.check_script is None:
            raise NotImplementedError("Check script not passed.")

        env = {}
        env["PYTHONPATH"] = f"{Path.cwd()}:$PYTHONPATH"

        stdin = format_check_input(self.inner_resource_config, previous_version_config)
        stdout, stderr = run_script(self.check_script, additional_args=[], env=env, stdin=stdin)

        self._debugging_output.inner_io.write(stderr)

        try:
            version_configs: list[VersionConfig] = json.loads(stdout)
        except json.JSONDecodeError as error:
            raise ValueError(f"Unexpected output: {stdout.strip()}") from error
        return version_configs

    def download_version(self, version_config: VersionConfig, params: Params | None = None) -> tuple[VersionConfig, list[MetadataPair]]:
        """
        Download a version and place its files within the resource directory in your pipeline.

        Calls the external in script using :func:`run_script` with the correct environment.

        :param version_config: The JSON configuration of the version.
        :param params: A mapping of additional keyword parameters passed to the inner resource.
        :returns: The version configuration (most likely unchanged), and a list of metadata pairs.
        """
        if self.in_script is None:
            raise NotImplementedError("In script not passed.")

        env = self.mocked_environ.copy()
        env["PYTHONPATH"] = f"{Path.cwd()}:$PYTHONPATH"

        stdin = format_in_input(self.inner_resource_config, version_config, params)
        with self._directory_state:
            stdout, stderr = run_script(self.in_script, additional_args=[str(self._directory_state.path)],
                                        env=env, stdin=stdin)

        self._debugging_output.inner_io.write(stderr)

        try:
            output = json.loads(stdout)
        except json.JSONDecodeError as error:
            raise ValueError(f"Unexpected output: {stdout.strip()}") from error
        new_version_config: VersionConfig = output["version"]
        metadata_pairs: list[MetadataPair] = output["metadata"] or []
        return new_version_config, metadata_pairs

    def publish_new_version(self, params: Params | None = None) -> tuple[VersionConfig, list[MetadataPair]]:
        """
        Update a resource by publishing a new version.

        Calls the external out script using :func:`run_script` with the correct environment.

        :param params: A mapping of additional keyword parameters passed to the inner resource.
        :returns: The new version configuration, and a list of metadata pairs.
        """
        if self.out_script is None:
            raise NotImplementedError("Out script not passed.")

        env = self.mocked_environ.copy()
        env["PYTHONPATH"] = f"{Path.cwd()}:$PYTHONPATH"

        stdin = format_out_input(self.inner_resource_config, params)
        with self._directory_state:
            stdout, stderr = run_script(self.out_script, additional_args=[str(self._directory_state.path)],
                                        env=env, stdin=stdin)

        self._debugging_output.inner_io.write(stderr)

        try:
            output = json.loads(stdout)
        except json.JSONDecodeError as error:
            raise ValueError(f"Unexpected output: {stdout.strip()}") from error
        new_version_config: VersionConfig = output["version"]
        metadata_pairs: list[MetadataPair] = output["metadata"] or []
        return new_version_config, metadata_pairs

    @classmethod
    def from_assets_dir(cls: type["FileTestResourceWrapper"], inner_resource_config: ResourceConfig, assets_dir: Path,
                        directory_dict: FolderDict | None = None, one_off_build: bool = False,
                        instance_vars: dict[str, str] | None = None, **env_vars: str) -> "FileTestResourceWrapper":
        """
        Create an instance from a single folder of asset files.

        :param inner_resource_config: The JSON configuration for the resource.
        :param assets_dir: The path to a folder containing the external script files.
                           Files are expected to be named ``check``, ``in`` and ``out``.
                           If not found, then no error will be raised unless the corresponding
                           method is called.
        :param directory_dict: The initial state of the resource directory. See :class:`~concoursetools.mocking.TemporaryDirectoryState`
        :param one_off_build: Set to :data:`True` if you are testing a one-off build.
        :param instance_vars: Pass optional instance vars to emulate an instanced pipeline.
        :param env_vars: Pass additional environment variables, or overload the default ones.
        """
        return cls(inner_resource_config, check_script=assets_dir / "check", in_script=assets_dir / "in",
                   out_script=assets_dir / "out", directory_dict=directory_dict, one_off_build=one_off_build,
                   instance_vars=instance_vars, **env_vars)


class FileConversionTestResourceWrapper(FileTestResourceWrapper, Generic[VersionT]):
    """
    A resource wrapper which converts the resource class to arbitrary scripts for execution.

    This wrapper converts the resource class to its external scripts
    using :func:`~concoursetools.dockertools.create_script_file`. Inputs
    are then converted to JSON and passed as in :class:`FileTestResourceWrapper`.

    .. tip::
        This is best to use if you want easier testing, but are concerned about the conversion
        of resource class to external scripts.

    :param inner_resource_type: The :class:`~concoursetools.resource.ConcourseResource` subclass corresponding to the resource.
    :param inner_resource_config: The JSON configuration for the resource.
    :param executable: The executable to use for the script (at the top).
                       (See :func:`~concoursetools.dockertools.create_script_file`.)
    :param permissions: The (Linux) permissions the file should have. Defaults to ``rwxr-xr-x``.
                        (See :func:`~concoursetools.dockertools.create_script_file`.)
    :param encoding: The encoding of the file as passed to :meth:`~pathlib.Path.write_text`.
                     Setting to :data:`None` (default) will use the user's default encoding.
                     (See :func:`~concoursetools.dockertools.create_script_file`.)
    :param directory_dict: The initial state of the resource directory. See :class:`~concoursetools.mocking.TemporaryDirectoryState`
    :param one_off_build: Set to :data:`True` if you are testing a one-off build.
    :param instance_vars: Pass optional instance vars to emulate an instanced pipeline.
    :param env_vars: Pass additional environment variables, or overload the default ones.
    """
    def __init__(self, inner_resource_type: type[ConcourseResource[VersionT]], inner_resource_config: ResourceConfig,
                 executable: str, permissions: int = 0o755, encoding: str | None = None,
                 directory_dict: FolderDict | None = None, one_off_build: bool = False,
                 instance_vars: dict[str, str] | None = None, **env_vars: str) -> None:
        super().__init__(inner_resource_config, check_script=None, in_script=None, out_script=None,
                         directory_dict=directory_dict, one_off_build=one_off_build, instance_vars=instance_vars, **env_vars)
        self.executable = executable
        self.permissions = permissions
        self.encoding = encoding
        self.inner_resource_type = inner_resource_type
        inner_resource = inner_resource_type(**inner_resource_config)
        self.inner_version_class = inner_resource.version_class

    def fetch_new_versions(self, previous_version: VersionT | None = None) -> list[VersionT]:
        """
        Fetch new versions of the resource.

        Converts the version (if it exists) to JSON, exports the script to an external file,
        and then invokes :meth:`~FileTestResourceWrapper.fetch_new_versions`. The response
        is then converted back to :class:`~concoursetools.version.Version` instances.

        .. caution::
            The external script file only exists for the duration of this method and is not cached.

        :param previous_version: The most recent version of the resource. This will be set to :data:`None`
                                 if the resource has never been run before.
        :returns: A list of new versions.
        """
        previous_version_config = None if previous_version is None else previous_version.to_flat_dict()
        with self._temporarily_create_script_file("check", "check_main"):
            version_configs = super().fetch_new_versions(previous_version_config)
        return [self.inner_version_class.from_flat_dict(version_config) for version_config in version_configs]

    def download_version(self, version: VersionT, **params: object) -> tuple[VersionT, Metadata]:
        """
        Download a version and place its files within the resource directory in your pipeline.

        Converts the version to JSON, exports the script to an external file, and then invokes
        :meth:`~FileTestResourceWrapper.download_version` with the additional params as a :class:`dict`.
        The returned version configuration is then converted back to a :class:`~concoursetools.version.Version`
        instance, and the metadata pairs converted to a standard :class:`dict`.

        .. caution::
            The external script file only exists for the duration of this method and is not cached.

        :param version: The version to be downloaded.
        :param params: Additional keyword parameters passed to the inner resource.
        :returns: The version (most likely unchanged), and a dictionary of metadata.
        """
        version_config = version.to_flat_dict()
        with self._temporarily_create_script_file("in", "in_main"):
            new_version_config, metadata_pairs = super().download_version(version_config, params or {})
        new_version = self.inner_version_class.from_flat_dict(new_version_config)
        metadata = parse_metadata(metadata_pairs)
        return new_version, metadata

    def publish_new_version(self, **params: object) -> tuple[VersionT, Metadata]:
        """
        Update a resource by publishing a new version.

        Exports the script to an external file and then invokes :meth:`~FileTestResourceWrapper.publish_new_version`
        with the additional params as a :class:`dict`. The returned version configuration is then converted to a
        :class:`~concoursetools.version.Version` instance, and the metadata pairs converted to a standard :class:`dict`.

        .. caution::
            The external script file only exists for the duration of this method and is not cached.

        :param params: Additional keyword parameters passed to the inner resource.
        :returns: The new version, and a dictionary of metadata.
        """
        with self._temporarily_create_script_file("out", "out_main"):
            new_version_config, metadata_pairs = super().publish_new_version(params or {})
        new_version = self.inner_version_class.from_flat_dict(new_version_config)
        metadata = parse_metadata(metadata_pairs)
        return new_version, metadata

    @contextmanager
    def _temporarily_create_script_file(self, script_name: ScriptName, method_name: MethodName) -> ContextManager[None]:
        attribute_name = f"{script_name}_script"
        try:
            with TemporaryDirectory() as temp_dir:
                script_path = Path(temp_dir) / script_name
                create_script_file(script_path, self.inner_resource_type, method_name, self.executable, self.permissions, self.encoding)
                setattr(self, attribute_name, script_path)
                yield
        finally:
            setattr(self, attribute_name, None)


class DockerTestResourceWrapper(TestResourceWrapper[Version]):
    """
    A resource wrapper which calls a Docker image.

    The container only persists for the duration of the method call.

    .. tip::
        This is best to use if you want to be sure that your Docker image has been built properly,
        or to test resource types which have **not** been built with Concourse Tools.

    :param inner_resource_config: The JSON configuration for the resource.
    :param image: The Docker image to use, which must exist in the local cache. Passed verbatim to ``docker run``.
    :param directory_dict: The initial state of the resource directory. See :class:`~concoursetools.mocking.TemporaryDirectoryState`
    :param one_off_build: Set to :data:`True` if you are testing a one-off build.
    :param instance_vars: Pass optional instance vars to emulate an instanced pipeline.
    :param env_vars: Pass additional environment variables, or overload the default ones.

    .. caution::
        If the image does not exist in the local cache, a :class:`RuntimeError` will be raised.

    .. note::
        The working directory is explicitly set to ``/`` within the container to ensure that
        the resource is properly accounting for the paths it is passed.
    """
    def __init__(self, inner_resource_config: ResourceConfig, image: str,
                 directory_dict: FolderDict | None = None, one_off_build: bool = False,
                 instance_vars: dict[str, str] | None = None, **env_vars: str) -> None:
        super().__init__(directory_dict, one_off_build, instance_vars, **env_vars)
        self.inner_resource_config = inner_resource_config
        self.image = image

    def fetch_new_versions(self, previous_version_config: VersionConfig | None = None) -> list[VersionConfig]:
        """
        Fetch new versions of the resource.

        Calls the ``/opt/resource/check`` script within the Docker container using :func:`run_docker_container`.

        .. caution::
            No environment variables are available to the check script.

        :param previous_version_config: The JSON configuration of the most recent version of the resource.
                                        This will be set to :data:`None` if the resource has never been run before.
        :returns: A list of new version configurations.
        """
        stdin = format_check_input(self.inner_resource_config, previous_version_config)
        with self._directory_state:
            stdout, stderr = run_docker_container(self.image, "/opt/resource/check", additional_args=[], env={},
                                                  cwd=Path("/"), stdin=stdin, hostname="resource")

        self._debugging_output.inner_io.write(stderr)

        try:
            version_configs: list[VersionConfig] = json.loads(stdout)
        except json.JSONDecodeError as error:
            raise ValueError(f"Unexpected output: {stdout.strip()}") from error
        return version_configs

    def download_version(self, version_config: VersionConfig, params: Params | None = None) -> tuple[VersionConfig, list[MetadataPair]]:
        """
        Download a version and place its files within the resource directory in your pipeline.

        Calls the ``/opt/resource/in`` script within the Docker container using :func:`run_docker_container`.

        :param version_config: The JSON configuration of the version.
        :param params: A mapping of additional keyword parameters passed to the inner resource.
        :returns: The version configuration (most likely unchanged), and a list of metadata pairs.
        """
        stdin = format_in_input(self.inner_resource_config, version_config, params)
        inner_temp_dir = f"/tmp/{secrets.token_hex(4)}"
        with self._directory_state:
            stdout, stderr = run_docker_container(self.image, "/opt/resource/in", additional_args=[inner_temp_dir],
                                                  env=self.mocked_environ.copy(), cwd=Path("/"), stdin=stdin,
                                                  dir_mapping={self._directory_state.path: inner_temp_dir},
                                                  hostname="resource")

        self._debugging_output.inner_io.write(stderr)

        try:
            output = json.loads(stdout)
        except json.JSONDecodeError as error:
            raise ValueError(f"Unexpected output: {stdout.strip()}") from error
        new_version_config: VersionConfig = output["version"]
        metadata_pairs: list[MetadataPair] = output["metadata"] or []
        return new_version_config, metadata_pairs

    def publish_new_version(self, params: Params | None = None) -> tuple[VersionConfig, list[MetadataPair]]:
        """
        Update a resource by publishing a new version.

        Calls the ``/opt/resource/out`` script within the Docker container using :func:`run_docker_container`.

        :param params: A mapping of additional keyword parameters passed to the inner resource.
        :returns: The new version configuration, and a list of metadata pairs.
        """
        stdin = format_out_input(self.inner_resource_config, params)
        inner_temp_dir = f"/tmp/{secrets.token_hex(4)}"
        with self._directory_state:
            stdout, stderr = run_docker_container(self.image, "/opt/resource/out", additional_args=[inner_temp_dir],
                                                  env=self.mocked_environ.copy(), cwd=Path("/"), stdin=stdin,
                                                  dir_mapping={self._directory_state.path: inner_temp_dir},
                                                  hostname="resource")

        self._debugging_output.inner_io.write(stderr)

        try:
            output = json.loads(stdout)
        except json.JSONDecodeError as error:
            raise ValueError(f"Unexpected output: {stdout.strip()}") from error
        new_version_config: VersionConfig = output["version"]
        metadata_pairs: list[MetadataPair] = output["metadata"] or []
        return new_version_config, metadata_pairs


class DockerConversionTestResourceWrapper(DockerTestResourceWrapper, Generic[VersionT]):
    """
    A resource wrapper based on :class:`DockerTestResourceWrapper`, yet with the interface of :class:`SimpleTestResourceWrapper`.

    Inputs are converted to JSON and passed as in :class:`DockerTestResourceWrapper`.
    The container only persists for the duration of the method call.

    .. tip::
        This is best to use if you want easier testing, but are concerned about the Dockerfile.

    :param inner_resource_type: The :class:`~concoursetools.resource.ConcourseResource` subclass corresponding to the resource.
    :param inner_resource_config: The JSON configuration for the resource.
    :param image: The Docker image to use, which must exist in the local cache. Passed verbatim to ``docker run``.
    :param directory_dict: The initial state of the resource directory. See :class:`~concoursetools.mocking.TemporaryDirectoryState`
    :param one_off_build: Set to :data:`True` if you are testing a one-off build.
    :param instance_vars: Pass optional instance vars to emulate an instanced pipeline.
    :param env_vars: Pass additional environment variables, or overload the default ones.
    """
    def __init__(self, inner_resource_type: type[ConcourseResource[VersionT]], inner_resource_config: ResourceConfig,
                 image: str, directory_dict: FolderDict | None = None, one_off_build: bool = False,
                 instance_vars: dict[str, str] | None = None, **env_vars: str) -> None:
        super().__init__(inner_resource_config, image, directory_dict=directory_dict, one_off_build=one_off_build,
                         instance_vars=instance_vars, **env_vars)
        self.inner_resource_type = inner_resource_type
        inner_resource = inner_resource_type(**inner_resource_config)
        self.inner_version_class = inner_resource.version_class

    def fetch_new_versions(self, previous_version: VersionT | None = None) -> list[VersionT]:
        """
        Fetch new versions of the resource.

        Converts the version (if it exists) to JSON and then invokes :meth:`~DockerTestResourceWrapper.fetch_new_versions`.
        The response is then converted back to :class:`~concoursetools.version.Version` instances.

        :param previous_version: The most recent version of the resource. This will be set to :data:`None`
                                 if the resource has never been run before.
        :returns: A list of new versions.
        """
        previous_version_config = None if previous_version is None else previous_version.to_flat_dict()
        version_configs = super().fetch_new_versions(previous_version_config)
        return [self.inner_version_class.from_flat_dict(version_config) for version_config in version_configs]

    def download_version(self, version: VersionT, **params: object) -> tuple[VersionT, Metadata]:
        """
        Download a version and place its files within the resource directory in your pipeline.

        Converts the version to JSON and then invokes :meth:`~DockerTestResourceWrapper.download_version`
        with the additional params as a :class:`dict`. The returned version configuration is then converted back to a
        :class:`~concoursetools.version.Version` instance, and the metadata pairs converted to a standard :class:`dict`.

        :param version: The version to be downloaded.
        :param params: Additional keyword parameters passed to the inner resource.
        :returns: The version (most likely unchanged), and a dictionary of metadata.
        """
        version_config = version.to_flat_dict()
        new_version_config, metadata_pairs = super().download_version(version_config, params or {})
        new_version = self.inner_version_class.from_flat_dict(new_version_config)
        metadata = parse_metadata(metadata_pairs)
        return new_version, metadata

    def publish_new_version(self, **params: object) -> tuple[VersionT, Metadata]:
        """
        Update a resource by publishing a new version.

        Converts the version to JSON and then invokes :meth:`~DockerTestResourceWrapper.publish_new_version`
        with the additional params as a :class:`dict`. The returned version configuration is then converted back to a
        :class:`~concoursetools.version.Version` instance, and the metadata pairs converted to a standard :class:`dict`.

        :param params: Additional keyword parameters passed to the inner resource.
        :returns: The new version, and a dictionary of metadata.
        """
        new_version_config, metadata_pairs = super().publish_new_version(params or {})
        new_version = self.inner_version_class.from_flat_dict(new_version_config)
        metadata = parse_metadata(metadata_pairs)
        return new_version, metadata


def run_docker_container(image: str, command: str, additional_args: list[str] | None = None,
                         env: dict[str, str] | None = None, cwd: Path | None = None,
                         stdin: str | None = None, rm: bool = True, interactive: bool = True,
                         dir_mapping: dict[Path, Path | str] | None = None,
                         hostname: str | None = None, local_only: bool = True) -> tuple[str, str]:
    """
    Run a command within the Docker container.

    .. caution::
        Mounted directory paths are not checked for actually being directories.

    .. danger::
        Directories are **not** mounted in "read-only" mode.

    .. caution::
        Parameters of this function are meant to refer to the command within the Docker container,
        and **not** the external command used to run the image.

    :param image: The Docker image to use for the container, which must exist in the local cache.
                  Passed verbatim to ``docker run``.
    :param command: The command to be passed to ``docker run``. Can also be a path to a script within the container.
    :param additional_args: Additional arguments to pass to the command.
    :param env: Environment variables to be made available to the script.
    :param cwd: Pass a path within the container to set the working directory, or else use the image default.
    :param stdin: A string to be passed on :data:`~sys.stdin`.
    :param rm: Set to :data:`True` to automatically remove the container when it exits.
                Equivalent to passing ``--rm``.
    :param interactive: Set to :data:`True` to keep ``stdin`` open even if not attached.
                        Equivalent to passing ``-i`` or ``--interactive``.
    :param dir_mapping: A mapping of directories to paths to mount within the container. Values can be paths or strings.
    :param hostname: Specify a hostname inside the container. Defaults to the container ID.
    :param local_only: When set to :data:`True` (default), only locally cached images can be used.
    :returns: The stdout and stderr of the script.
    :raises RuntimeError: If the external script exits with a non-zero exit code.
    :seealso: This function will call :func:`run_command`.
    """
    docker_args: list[str] = ["run"]

    if rm:
        docker_args.append("--rm")

    if interactive:
        docker_args.append("--interactive")

    if dir_mapping:
        for outer, inner in dir_mapping.items():
            docker_args.extend(["--volume", f"{outer.absolute()!s}:{inner!s}"])

    if cwd:
        docker_args.extend(["--workdir", str(cwd)])

    if hostname is not None:
        docker_args.extend(["--hostname", hostname])

    if local_only is True:
        docker_args.extend(["--pull", "never"])

    if env:
        for key, value in env.items():
            docker_args.extend(["--env", f"{key}={value}"])

    docker_args.append(image)
    docker_args.append(command)

    if additional_args:
        docker_args.extend(additional_args)

    return run_command("docker", docker_args, stdin=stdin)


def run_script(script_path: Path, additional_args: list[str] | None = None, env: dict[str, str] | None = None,
               cwd: Path | None = None, stdin: str | None = None) -> tuple[str, str]:
    """
    Run an external script.

    :param script_path: The path to the script to be run.
    :param additional_args: Additional arguments to be passed to the script.
    :param env: Environment variables to be made available to the script.
    :param cwd: The working directory of the script. Defaults to current working directory.
    :param stdin: A string to be passed on :data:`~sys.stdin`.
    :returns: The stdout and stderr of the script.
    :raises FileNotFoundError: If the script does not exist.
    :raises RuntimeError: If the external script exits with a non-zero exit code.
    :seealso: This function will call :func:`run_command`.
    """
    if not script_path.is_file():
        raise FileNotFoundError(f"No script found at {script_path}")

    return run_command(str(script_path), additional_args, env=env, cwd=cwd, stdin=stdin)


def run_command(command: str, additional_args: list[str] | None = None, env: dict[str, str] | None = None,
                cwd: Path | None = None, stdin: str | None = None) -> tuple[str, str]:
    """
    Run an external command.

    :param command: The external command to be run.
    :param additional_args: Additional arguments to be passed to the command.
    :param env: Environment variables to be made available to the command.
    :param cwd: The working directory of the command. Defaults to current working directory.
    :param stdin: A string to be passed on :data:`~sys.stdin`.
    :returns: The stdout and stderr of the command.
    :raises RuntimeError: If the external command exits with a non-zero exit code.
    :seealso: This function is broadly equivalent to :func:`subprocess.run`.
    """
    try:
        process = subprocess.run(
            [command] + (additional_args or []),
            env=env,
            cwd=cwd,
            check=True,
            input=stdin.encode() if stdin is not None else None,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
    except subprocess.CalledProcessError as error:
        error_message: bytes = error.stderr
        raise RuntimeError(error_message.decode()) from error

    stdout, stderr = process.stdout.decode(), process.stderr.decode()
    return stdout, stderr
