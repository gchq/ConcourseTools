# (C) Crown Copyright GCHQ
"""
Concourse Tools contains a number of functions for easier testing.

You can take advantage of the class-based paradigm in Concourse Tools
to test your resource class as a standard Python object. You can call
the functions with specific inputs to check that they are turning the
correct outputs. However, this does limit your ability to mock the
script environment when your code relies on external factors.
"""
from abc import ABC, abstractmethod
from contextlib import contextmanager, redirect_stdout
from io import StringIO
import json
import pathlib
import subprocess
from tempfile import TemporaryDirectory
from typing import Any, Callable, Dict, Generator, Generic, List, Optional, Tuple, Type, TypeVar, Union, cast

from concoursetools import BuildMetadata, ConcourseResource, Version
from concoursetools.dockertools import create_script_file
from concoursetools.mocking import StringIOWrapper, TemporaryDirectoryState, create_env_vars, mock_argv, mock_environ, mock_stdin
from concoursetools.parsing import format_check_input, format_in_input, format_out_input, parse_metadata
from concoursetools.typing import Metadata, MetadataPair, Params, ResourceConfig, VersionConfig, VersionT

T = TypeVar("T")
ContextManager = Generator[T, None, None]
FolderDict = Dict[str, Any]
PathLike = Union[pathlib.Path, str]


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
    :param one_off_build: Set to :obj:`True` if you are testing a one-off build.
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
    def __init__(self, directory_dict: Optional[FolderDict] = None, one_off_build: bool = False,
                 instance_vars: Optional[Dict[str, str]] = None, **env_vars: str) -> None:
        self.mocked_environ = create_env_vars(one_off_build, instance_vars, **env_vars)
        self.directory_dict = directory_dict

        self._debugging_output = StringIOWrapper()
        self._directory_state = TemporaryDirectoryState(self.directory_dict)

    @abstractmethod
    def fetch_new_versions(self) -> Any:
        """Fetch new versions of the resource."""
        ...

    @abstractmethod
    def download_version(self) -> Any:
        """Download a version and place its files within the resource directory in your pipeline."""
        ...

    @abstractmethod
    def publish_new_version(self) -> Any:
        """
        Update a resource by publishing a new version.
        """
        ...

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
    def capture_directory_state(self, starting_state: Optional[FolderDict] = None) -> ContextManager["TemporaryDirectoryState"]:
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
    def _forbid_methods(self, *methods: Callable[..., Any]) -> ContextManager[None]:
        try:
            for method in methods:
                def new_method(*args: Any, **kwargs: Any) -> Any:
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
    :param one_off_build: Set to :obj:`True` if you are testing a one-off build.
    :param instance_vars: Pass optional instance vars to emulate an instanced pipeline.
    :param env_vars: Pass additional environment variables, or overload the default ones.
    """
    def __init__(self, inner_resource: ConcourseResource[VersionT], directory_dict: Optional[FolderDict] = None,
                 one_off_build: bool = False, instance_vars: Optional[Dict[str, str]] = None, **env_vars: str) -> None:
        super().__init__(directory_dict, one_off_build, instance_vars, **env_vars)
        self.inner_resource = inner_resource
        self.mocked_build_metadata = BuildMetadata(**self.mocked_environ)

    def fetch_new_versions(self, previous_version: Optional[VersionT] = None) -> List[VersionT]:
        """
        Fetch new versions of the resource.

        Calls the inner resource whilst capturing debugging output.

        :param previous_version: The most recent version of the resource. This will be set to :obj:`None`
                                 if the resource has never been run before.
        :returns: A list of new versions.
        """
        with self._debugging_output.capture_stdout_and_stderr():
            return self.inner_resource.fetch_new_versions(previous_version=previous_version)

    def download_version(self, version: VersionT, **params: Any) -> Tuple[VersionT, Metadata]:
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

    def publish_new_version(self, **params: Any) -> Tuple[VersionT, Metadata]:
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
    :param one_off_build: Set to :obj:`True` if you are testing a one-off build.
    :param instance_vars: Pass optional instance vars to emulate an instanced pipeline.
    :param env_vars: Pass additional environment variables, or overload the default ones.
    """
    def __init__(self, inner_resource_type: Type[ConcourseResource[VersionT]], inner_resource_config: ResourceConfig,
                 directory_dict: Optional[FolderDict] = None, one_off_build: bool = False,
                 instance_vars: Optional[Dict[str, str]] = None, **env_vars: str) -> None:
        super().__init__(directory_dict, one_off_build, instance_vars, **env_vars)
        self.inner_resource_type = inner_resource_type
        self.inner_resource_config = inner_resource_config

    def fetch_new_versions(self, previous_version_config: Optional[VersionConfig] = None) -> List[VersionConfig]:
        """
        Fetch new versions of the resource.

        Mocks the environment and calls :meth:`~concoursetools.resource.ConcourseResource.check_main`.

        .. caution::
            No environment variables are available to the check script.

        :param previous_version_config: The JSON configuration of the most recent version of the resource.
                                        This will be set to :obj:`None` if the resource has never been run before.
        :returns: A list of new versions configurations.
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
            version_configs: List[VersionConfig] = json.loads(stdout)
        except json.JSONDecodeError as error:
            raise ValueError(f"Unexpected output: {stdout.strip()}") from error
        return version_configs

    def download_version(self, version_config: VersionConfig, params: Optional[Params] = None) -> Tuple[VersionConfig, List[MetadataPair]]:
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
        metadata_pairs: List[MetadataPair] = output["metadata"]
        return new_version_config, metadata_pairs

    def publish_new_version(self, params: Optional[Params] = None) -> Tuple[VersionConfig, List[MetadataPair]]:
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
        metadata_pairs: List[MetadataPair] = output["metadata"]
        return new_version_config, metadata_pairs


class ConversionTestResourceWrapper(JSONTestResourceWrapper[VersionT]):
    """
    A resource wrapper based on :class:`JSONTestResourceWrapper`, yet with the interface of :class:`SimpleTestResourceWrapper`

    All inputs and outputs are instances, but are converted to and from JSON internally.

    .. tip::
        This is best to use if you want easier testing, but are still concerned
        about the conversion of your resource and versions.

    :param inner_resource_type: The :class:`~concoursetools.resource.ConcourseResource` subclass corresponding to the resource.
    :param inner_resource_config: The JSON configuration for the resource.
    :param directory_dict: The initial state of the resource directory. See :class:`~concoursetools.mocking.TemporaryDirectoryState`
    :param one_off_build: Set to :obj:`True` if you are testing a one-off build.
    :param instance_vars: Pass optional instance vars to emulate an instanced pipeline.
    :param env_vars: Pass additional environment variables, or overload the default ones.
    """
    def __init__(self, inner_resource_type: Type[ConcourseResource[VersionT]], inner_resource_config: ResourceConfig,
                 directory_dict: Optional[FolderDict] = None, one_off_build: bool = False,
                 instance_vars: Optional[Dict[str, str]] = None, **env_vars: str) -> None:
        super().__init__(inner_resource_type, inner_resource_config, directory_dict, one_off_build, instance_vars, **env_vars)
        self.mocked_build_metadata = BuildMetadata(**self.mocked_environ)
        inner_resource = inner_resource_type(**inner_resource_config)
        self.inner_version_class = inner_resource.version_class

    def fetch_new_versions(self, previous_version: Optional[VersionT] = None) -> List[VersionT]:
        """
        Fetch new versions of the resource.

        Converts the version (if it exists) to JSON, and then invokes :meth:`~JSONTestResourceWrapper.fetch_new_versions`.
        The response is then converted back to :class:`~concoursetools.version.Version` instances.

        :param previous_version: The most recent version of the resource. This will be set to :obj:`None`
                                 if the resource has never been run before.
        :returns: A list of new versions.
        """
        previous_version_config = None if previous_version is None else previous_version.to_flat_dict()
        version_configs = super().fetch_new_versions(previous_version_config)
        return [self.inner_version_class.from_flat_dict(version_config) for version_config in version_configs]

    def download_version(self, version: VersionT, **params: Any) -> Tuple[VersionT, Metadata]:
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

    def publish_new_version(self, **params: Any) -> Tuple[VersionT, Metadata]:
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
                         Setting to :obj:`None` (default) means that :meth:`fetch_new_versions`
                         raises :class:`NotImplementedError`.
    :param in_script: The path to the external script for the :concourse:`check <implementing-resource-types.resource-in>`.
                      Setting to :obj:`None` (default) means that :meth:`download_version`
                      raises :class:`NotImplementedError`.
    :param out_script: The path to the external script for the :concourse:`check <implementing-resource-types.resource-out>`.
                       Setting to :obj:`None` (default) means that :meth:`publish_new_version`
                       raises :class:`NotImplementedError`.
    :param directory_dict: The initial state of the resource directory. See :class:`~concoursetools.mocking.TemporaryDirectoryState`
    :param one_off_build: Set to :obj:`True` if you are testing a one-off build.
    :param instance_vars: Pass optional instance vars to emulate an instanced pipeline.
    :param env_vars: Pass additional environment variables, or overload the default ones.

    .. caution::
        If any of the paths for the scripts do not resolve, the corresponding methods will raise :class:`NotImplementedError`.
    """
    def __init__(self, inner_resource_config: ResourceConfig, check_script: Optional[pathlib.Path] = None,
                 in_script: Optional[pathlib.Path] = None, out_script: Optional[pathlib.Path] = None,
                 directory_dict: Optional[FolderDict] = None, one_off_build: bool = False,
                 instance_vars: Optional[Dict[str, str]] = None, **env_vars: str) -> None:
        super().__init__(directory_dict, one_off_build, instance_vars, **env_vars)
        self.inner_resource_config = inner_resource_config
        self.check_script, self.in_script, self.out_script = check_script, in_script, out_script

    def fetch_new_versions(self, previous_version_config: Optional[VersionConfig] = None) -> List[VersionConfig]:
        """
        Fetch new versions of the resource.

        Calls the external check script using :meth:`capture_output_from_script` with the correct environment.

        .. caution::
            No environment variables are available to the check script.

        :param previous_version_config: The JSON configuration of the most recent version of the resource.
                                        This will be set to :obj:`None` if the resource has never been run before.
        :returns: A list of new versions configurations.
        """
        if self.check_script is None:
            raise NotImplementedError("Check script not passed.")

        stdin = format_check_input(self.inner_resource_config, previous_version_config)
        stdout, stderr = self.capture_output_from_script(self.check_script, stdin, additional_argv=[], env={})

        self._debugging_output.inner_io.write(stderr)

        try:
            version_configs: List[VersionConfig] = json.loads(stdout)
        except json.JSONDecodeError as error:
            raise ValueError(f"Unexpected output: {stdout.strip()}") from error
        return version_configs

    def download_version(self, version_config: VersionConfig, params: Optional[Params] = None) -> Tuple[VersionConfig, List[MetadataPair]]:
        """
        Download a version and place its files within the resource directory in your pipeline.

        Calls the external in script using :meth:`capture_output_from_script` with the correct environment.

        :param version_config: The JSON configuration of the version.
        :param params: A mapping of additional keyword parameters passed to the inner resource.
        :returns: The version configuration (most likely unchanged), and a list of metadata pairs.
        """
        if self.in_script is None:
            raise NotImplementedError("In script not passed.")

        stdin = format_in_input(self.inner_resource_config, version_config, params)
        with self._directory_state:
            stdout, stderr = self.capture_output_from_script(self.in_script, stdin,
                                                             additional_argv=[str(self._directory_state.path)],
                                                             env=self.mocked_environ.copy())

        self._debugging_output.inner_io.write(stderr)

        try:
            output = json.loads(stdout)
        except json.JSONDecodeError as error:
            raise ValueError(f"Unexpected output: {stdout.strip()}") from error
        new_version_config: VersionConfig = output["version"]
        metadata_pairs: List[MetadataPair] = output["metadata"]
        return new_version_config, metadata_pairs

    def publish_new_version(self, params: Optional[Params] = None) -> Tuple[VersionConfig, List[MetadataPair]]:
        """
        Update a resource by publishing a new version.

        Calls the external out script using :meth:`capture_output_from_script` with the correct environment.

        :param params: A mapping of additional keyword parameters passed to the inner resource.
        :returns: The new version configuration, and a list of metadata pairs.
        """
        if self.out_script is None:
            raise NotImplementedError("Out script not passed.")

        stdin = format_out_input(self.inner_resource_config, params)
        with self._directory_state:
            stdout, stderr = self.capture_output_from_script(self.out_script, stdin,
                                                             additional_argv=[str(self._directory_state.path)],
                                                             env=self.mocked_environ.copy())

        self._debugging_output.inner_io.write(stderr)

        try:
            output = json.loads(stdout)
        except json.JSONDecodeError as error:
            raise ValueError(f"Unexpected output: {stdout.strip()}") from error
        new_version_config: VersionConfig = output["version"]
        metadata_pairs: List[MetadataPair] = output["metadata"]
        return new_version_config, metadata_pairs

    @classmethod
    def from_assets_dir(cls: Type["FileTestResourceWrapper"], inner_resource_config: ResourceConfig, assets_dir: pathlib.Path,
                        directory_dict: Optional[FolderDict] = None, one_off_build: bool = False,
                        instance_vars: Optional[Dict[str, str]] = None, **env_vars: str) -> "FileTestResourceWrapper":
        """
        Create an instance from a single folder of asset files.

        :param inner_resource_config: The JSON configuration for the resource.
        :param assets_dir: The path to a folder containing the external script files.
                           Files are expected to be named ``check``, ``in`` and ``out``.
                           If not found, then no error will be raised unless the corresponding
                           method is called.
        :param directory_dict: The initial state of the resource directory. See :class:`~concoursetools.mocking.TemporaryDirectoryState`
        :param one_off_build: Set to :obj:`True` if you are testing a one-off build.
        :param instance_vars: Pass optional instance vars to emulate an instanced pipeline.
        :param env_vars: Pass additional environment variables, or overload the default ones.
        """
        return cls(inner_resource_config, check_script=assets_dir / "check", in_script=assets_dir / "in",
                   out_script=assets_dir / "out", directory_dict=directory_dict, one_off_build=one_off_build,
                   instance_vars=instance_vars, **env_vars)

    def capture_output_from_script(self, script_path: pathlib.Path, stdin: str, additional_argv: List[str],
                                   env: Dict[str, str], cwd: PathLike = pathlib.Path(".")) -> Tuple[str, str]:
        """
        Run an external script and capture the output.

        The script is run using :func:`subprocess.run`.

        :param script_path: The location of the script to run.
        :param stdin: A string to be passed on :obj:`~sys.stdin`.
        :param additional_argv: Additional strings to pass as :obj:`sys.argv`.
                                The first argument is always the script path.
        :param env: Environment variables to be made available to the script. ``PYTHONPATH`` is added by the method.
        :param cwd: The working directory of the script. Defaults to current working directory.
        :returns: The stdout and stderr of the script.
        :raises FileNotFoundError: If the script path can not be resolved.
        :raises RuntimeError: If the external script exists with a non-zero exit code.
        """
        if not script_path.is_file():
            raise FileNotFoundError(f"No script found at {script_path}")

        env["PYTHONPATH"] = f"{cwd}:$PYTHONPATH"

        argv = [str(script_path)] + additional_argv

        try:
            process = subprocess.run(
                argv,
                env=env,
                cwd=str(cwd),
                check=True,
                input=stdin.encode(),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
        except subprocess.CalledProcessError as error:
            raise RuntimeError(cast(bytes, error.stderr).decode()) from error

        stdout, stderr = process.stdout.decode(), process.stderr.decode()
        return stdout, stderr


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
                     Setting to :obj:`None` (default) will use the user's default encoding.
                     (See :func:`~concoursetools.dockertools.create_script_file`.)
    :param directory_dict: The initial state of the resource directory. See :class:`~concoursetools.mocking.TemporaryDirectoryState`
    :param one_off_build: Set to :obj:`True` if you are testing a one-off build.
    :param instance_vars: Pass optional instance vars to emulate an instanced pipeline.
    :param env_vars: Pass additional environment variables, or overload the default ones.
    """
    def __init__(self, inner_resource_type: Type[ConcourseResource[VersionT]], inner_resource_config: ResourceConfig,
                 executable: str, permissions: int = 0o755, encoding: Optional[str] = None,
                 directory_dict: Optional[FolderDict] = None, one_off_build: bool = False,
                 instance_vars: Optional[Dict[str, str]] = None, **env_vars: str) -> None:
        super().__init__(inner_resource_config, check_script=None, in_script=None, out_script=None,
                         directory_dict=directory_dict, one_off_build=one_off_build, instance_vars=instance_vars, **env_vars)
        self.executable = executable
        self.permissions = permissions
        self.encoding = encoding
        self.inner_resource_type = inner_resource_type
        inner_resource = inner_resource_type(**inner_resource_config)
        self.inner_version_class = inner_resource.version_class

    def fetch_new_versions(self, previous_version: Optional[VersionT] = None) -> List[VersionT]:
        """
        Fetch new versions of the resource.

        Converts the version (if it exists) to JSON, exports the script to an external file,
        and then invokes :meth:`~FileTestResourceWrapper.fetch_new_versions`. The response
        is then converted back to :class:`~concoursetools.version.Version` instances.

        .. caution::
            The external script file only exists for the duration of this method and is not cached.

        :param previous_version: The most recent version of the resource. This will be set to :obj:`None`
                                 if the resource has never been run before.
        :returns: A list of new versions.
        """
        previous_version_config = None if previous_version is None else previous_version.to_flat_dict()
        with self._temporarily_create_script_file("check", self.inner_resource_type.check_main):
            version_configs = super().fetch_new_versions(previous_version_config)
        return [self.inner_version_class.from_flat_dict(version_config) for version_config in version_configs]

    def download_version(self, version: VersionT, **params: Any) -> Tuple[VersionT, Metadata]:
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
        with self._temporarily_create_script_file("in", self.inner_resource_type.in_main):
            new_version_config, metadata_pairs = super().download_version(version_config, params or {})
        new_version = self.inner_version_class.from_flat_dict(new_version_config)
        metadata = parse_metadata(metadata_pairs)
        return new_version, metadata

    def publish_new_version(self, **params: Any) -> Tuple[VersionT, Metadata]:
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
        with self._temporarily_create_script_file("out", self.inner_resource_type.out_main):
            new_version_config, metadata_pairs = super().publish_new_version(params or {})
        new_version = self.inner_version_class.from_flat_dict(new_version_config)
        metadata = parse_metadata(metadata_pairs)
        return new_version, metadata

    @contextmanager
    def _temporarily_create_script_file(self, script_name: str, method: Callable[[], None]) -> ContextManager[None]:
        attribute_name = f"{script_name}_script"
        try:
            with TemporaryDirectory() as temp_dir:
                script_path = pathlib.Path(temp_dir) / script_name
                create_script_file(script_path, method, self.executable, self.permissions, self.encoding)
                setattr(self, attribute_name, script_path)
                yield
        finally:
            setattr(self, attribute_name, None)
