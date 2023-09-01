# (C) Crown Copyright GCHQ
"""
Concourse Tools contains a number of utility functions for mocking various parts of the process for testing purposes.
"""
from contextlib import contextmanager, redirect_stderr, redirect_stdout
from io import StringIO
import json
import os
import pathlib
import sys
from tempfile import TemporaryDirectory
from types import TracebackType
from typing import Any, Dict, Generator, Optional, Type, TypeVar, Union
from unittest import mock

from concoursetools import BuildMetadata

T = TypeVar("T")
ContextManager = Generator[T, None, None]
FolderDict = Dict[str, Any]
PathLike = Union[pathlib.Path, str]


def create_env_vars(one_off_build: bool = False, instance_vars: Optional[Dict[str, str]] = None, **env_vars: str) -> Dict[str, str]:
    """
    Create fake environment variables for a Concourse stage.

    :param one_off_build: Set to :obj:`True` if you are testing a one-off build.
    :param instance_vars: Pass optional instance vars to emulate an instanced pipeline.
    :param env_vars: Pass additional environment variables, or overload the default ones.

    :Example:
        >>> for key, value in create_env_vars().items():
        ...     print(key, value)
        BUILD_ID 12345678
        BUILD_NAME 42
        BUILD_TEAM_NAME my-team
        ATC_EXTERNAL_URL https://ci.myconcourse.com
        BUILD_JOB_NAME my-job
        BUILD_PIPELINE_NAME my-pipeline
        >>> for key, value in create_env_vars(one_off_build=True).items():
        ...     print(key, value)
        BUILD_ID 12345678
        BUILD_NAME 42
        BUILD_TEAM_NAME my-team
        ATC_EXTERNAL_URL https://ci.myconcourse.com
    """
    env = {
        "BUILD_ID": "12345678",
        "BUILD_NAME": "42",
        "BUILD_TEAM_NAME": "my-team",
        "ATC_EXTERNAL_URL": "https://ci.myconcourse.com",
    }
    if one_off_build:
        return env

    env.update({
        "BUILD_JOB_NAME": "my-job",
        "BUILD_PIPELINE_NAME": "my-pipeline",
    })

    if instance_vars is not None:
        env["BUILD_PIPELINE_INSTANCE_VARS"] = json.dumps(instance_vars)

    env.update(env_vars)

    return env


class TestBuildMetadata(BuildMetadata):
    """
    Build metadata for testing Concourse resources.

    Equivalent to:

    .. code:: python

        >>> metadata = BuildMetadata(**create_env_vars(...))

    :param one_off_build: Set to :obj:`True` if you are testing a one-off build.
    :param instance_vars: Pass optional instance vars to emulate an instanced pipeline.
    :param env_vars: Pass additional environment variables, or overload the default ones.
    """
    def __init__(self, one_off_build: bool = False, instance_vars: Optional[Dict[str, str]] = None, **env_vars: str):
        test_env_vars = create_env_vars(one_off_build, instance_vars, **env_vars)
        super().__init__(**test_env_vars)


class TemporaryDirectoryState:
    """
    A class representing the state of a temporary directory, to be used as a context manager.

    :param starting_state: The starting state of the directory.Keys of the dictionary are strings
                           (relative to that level, so the *name* of a folder instead of a full path.)
                           For the values, we have the following:

                           * A **file** is represented by a string containing the contents of the file.
                             An empty string represents an empty file.
                           * A **folder** is represented by a dictionary yielding more files and folders.
    :param max_depth: The maximum depth into which the function can descend. A value of 1 will not enter any subdirectories,
                      a value of 2 will not enter any sub-subdirectories etc.
    :param encoding: The encoding to be used to open the files. Will use the system by default when not set.
    :param kwargs: Keyword arguments to be passed to :class:`~tempfile.TemporaryDirectory`.

    :Example:
        >>> folder_state = {
        ...     "folder_1": {},
        ...     "folder_2": {
        ...         "folder_3": {
        ...             "file_3": "Testing 3",
        ...         },
        ...         "file_2": "Testing 2",
        ...     },
        ...     "file_1": "Testing 1",
        ... }
        >>> with TemporaryDirectoryState(folder_state) as temp_dir:
        ...     file_2 = temp_dir.path / "folder_2" / "file_2"
        ...     print(file_2.read_text())
        Testing 2
        >>> file_2.read_text()  # doctest: +ELLIPSIS
        Traceback (most recent call last):
        ...
        FileNotFoundError: [Errno 2] No such file or directory: '.../folder_2/file_2'
    """
    def __init__(self, starting_state: Optional[FolderDict] = None, max_depth: int = 2, encoding: Optional[str] = None, **kwargs: Any):
        self.starting_state = starting_state or {}
        self.max_depth = max_depth
        self.encoding = encoding
        self.temporary_directory_kwargs = kwargs

        self._temp_dir: Optional[TemporaryDirectory[str]] = None
        self._final_state: Optional[FolderDict] = None

    @property
    def path(self) -> pathlib.Path:
        """
        Return the path to the temporary directory.

        :raises RuntimeError: If the temporary directory is currently closed.
        """
        if self._temp_dir is not None:
            return pathlib.Path(self._temp_dir.name)
        else:
            raise RuntimeError("Cannot fetch the path when the directory is closed.")

    @property
    def final_state(self) -> FolderDict:
        """
        Return the final state of the directory when it closed.

        :raises RuntimeError: If the temporary directory is currently open.
        """
        if self._final_state is None:
            raise RuntimeError("Final state is not set whilst temporary directory is still open.")
        return self._final_state

    def __enter__(self) -> "TemporaryDirectoryState":
        self._temp_dir = TemporaryDirectory(**self.temporary_directory_kwargs)
        self._set_folder_from_dict(self.path, self.starting_state, encoding=self.encoding)
        return self

    def __exit__(self, exc_type: Optional[Type[BaseException]], exc_val: Optional[BaseException], exc_tb: Optional[TracebackType]) -> None:
        if self._temp_dir is None:
            raise RuntimeError("Temporary directory missing from instance.")
        self._final_state = self._get_folder_as_dict(self.path, self.max_depth, self.encoding)
        self._temp_dir.__exit__(exc_type, exc_val, exc_tb)

    def _get_folder_as_dict(self, folder_path: pathlib.Path, max_depth: int = 2, encoding: Optional[str] = None,
                            byte_limit: int = 16) -> Union[Any, FolderDict]:
        """
        Return the recursive contents of a folder as a nested dictionary.

        Keys of the dictionary are strings (relative to that level, so the *name* of a folder instead of a full path.)
        For the values, we have the following:

            * A **file** is represented by a string or containing the contents of the file.
              If the file cannot be read with the given encoding, then the first few bytes
              of the file will be used instead.
            * A **folder** is represented by a dictionary yielding more files and folders.

        If a folder has not been descended into (due to the depth limit) then it is represented by an :obj:`Ellipsis` (``...``).

        :param folder_path: The path to the folder.
        :param max_depth: The maximum depth into which the function can descend. A value of 1 will not enter any subdirectories,
                        a value of 2 will not enter any sub-subdirectories etc.
        :param encoding: The encoding to be used to open the files. Will use the system by default when not set.
        :param byte_limit: The number of bytes to "head" from a file which cannot be opened with the encoding.
        """
        if max_depth == 0:
            return ...

        folder_dict: Dict[str, Any] = {}

        for item in folder_path.iterdir():
            if item.is_file():
                try:
                    folder_dict[item.name] = item.read_text(encoding)
                except UnicodeDecodeError:
                    with open(item, "rb") as rf:
                        first_chunk = rf.read(byte_limit)
                    folder_dict[item.name] = first_chunk
            elif item.is_dir():
                folder_dict[item.name] = self._get_folder_as_dict(item, max_depth=max_depth-1, encoding=encoding)
        return folder_dict

    def _set_folder_from_dict(self, folder_path: pathlib.Path, folder_dict: FolderDict, encoding: Optional[str] = None) -> None:
        """
        Set the contents of a folder using a recursive dictionary.

        Keys of the dictionary are strings (relative to that level, so the *name* of a folder instead of a full path.)
        For the values, we have the following:

            * A **file** is represented by a string containing the contents of the file.
            * A **folder** is represented by a dictionary yielding more files and folders.

        :param folder_path: The path to the folder.
        :param folder_dict: The contents of the folder will be set to this directory.
        :param encoding: The encoding to be used to open the files. Will use the system by default when not set.
        """
        for name, value in folder_dict.items():
            path = folder_path / name
            if isinstance(value, str):
                path.write_text(value, encoding)
            elif isinstance(value, dict):
                path.mkdir(exist_ok=False)
                self._set_folder_from_dict(path, value, encoding=encoding)


class StringIOWrapper:
    r"""
    A basic wrapper around a :class:`~io.StringIO` instance for capturing :obj:`~sys.stdout` and :obj:`~sys.stderr`.

    An instance of this class acts a bit like a string, to the extent that
    ``==`` will compare the :attr:`value` of the instance to a string.

    :Example:
        Capture :obj:`~sys.stderr` with :meth:`capture_stderr`:

        >>> output = StringIOWrapper()
        >>> with output.capture_stderr():
        ...     print("abc")
        ...     print("def", file=sys.stderr)
        abc
        >>> output == "def\n"
        True

        Or capture both :obj:`~sys.stdout` and :obj:`~sys.stderr` with :meth:`capture_stdout_and_stderr`:

        >>> output = StringIOWrapper()
        >>> with output.capture_stdout_and_stderr():
        ...     print("abc")
        ...     print("def", file=sys.stderr)
        >>> output == "abc\ndef\n"
        True
    """
    def __init__(self) -> None:
        self.inner_io = StringIO()

    def __eq__(self, __value: object) -> bool:
        return self.value == __value

    def __repr__(self) -> str:
        return repr(self.value)

    @property
    def value(self) -> str:
        """
        Return the current value of the inner buffer.

        :seealso: :meth:`io.StringIO.getvalue`
        """
        return self.inner_io.getvalue()

    def clear(self) -> None:
        """Clear the buffer."""
        self.inner_io = StringIO()

    @contextmanager
    def capture_stdout_and_stderr(self) -> ContextManager["StringIOWrapper"]:
        """
        Capture both :obj:`~sys.stdout` and :obj:`~sys.stderr`.

        :seealso: :func:`contextlib.redirect_stdout`, :func:`contextlib.redirect_stderr`
        """
        with redirect_stdout(self.inner_io):
            with self.capture_stderr():
                yield self

    @contextmanager
    def capture_stderr(self) -> ContextManager["StringIOWrapper"]:
        """
        Capture :obj:`~sys.stderr`.

        :seealso: :func:`contextlib.redirect_stderr`
        """
        with redirect_stderr(self.inner_io):
            yield self


@contextmanager
def mock_environ(new_environ: Dict[str, str]) -> ContextManager[None]:
    """
    Mock :obj:`os.environ` in a context manager.

    :param new_environ: The new environment variables. No existing environment variables are carried forward.

    :Example:
        >>> with mock_environ({"ENV_VAR": "my-env"}):
        ...     for key, value in os.environ.items():
        ...         print(key, value)
        ENV_VAR my-env
    """
    with mock.patch.object(os, "environ", new_environ):
        yield


@contextmanager
def mock_stdin(stdin: str) -> ContextManager[None]:
    """
    Mock :obj:`~sys.stdin` in a context manager.

    :param stdin: A new string to be used for the stdin.

    :Example:
        >>> with mock_stdin("new_stdin"):
        ...     print(sys.stdin.read())
        new_stdin

    .. warning::
        As it's a :term:`file object`, :obj:`sys.stdin`
        is only mocked once by this decorator, and subsequent calls to
        :meth:`~io.TextIOBase.read` will return :obj:`None`.
    """
    with mock.patch.object(sys, "stdin", StringIO(stdin)):
        yield


@contextmanager
def mock_argv(*args: str) -> ContextManager[None]:
    """
    Mock :obj:`sys.argv` in a context manager.

    :param args: New args to be used.

    :Example:
        >>> with mock_argv("/my/script.py", "input1"):
        ...     print(sys.argv)
        ['/my/script.py', 'input1']
    """
    with mock.patch.object(sys, "argv", list(args)):
        yield
