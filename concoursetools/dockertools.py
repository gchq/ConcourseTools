# (C) Crown Copyright GCHQ
"""
Functions for creating the Dockerfile or asset files.
"""
from __future__ import annotations

import inspect
from pathlib import Path
import sys
import textwrap
from types import MethodType
from typing import Any, Literal, TypeVar

from concoursetools import ConcourseResource

T = TypeVar("T")
ScriptName = Literal["check", "in", "out"]
MethodName = Literal["check_main", "in_main", "out_main"]

DEFAULT_EXECUTABLE = "/usr/bin/env python3"
DEFAULT_PYTHON_VERSION = f"{sys.version_info.major}.{sys.version_info.minor}"


def create_script_file(path: Path, resource_class: type[ConcourseResource[Any]], method_name: MethodName,
                       executable: str = DEFAULT_EXECUTABLE, permissions: int = 0o755,
                       encoding: str | None = None) -> None:
    """
    Create a script file at a given path.

    :param path: The path at which the file will be created.
    :param resource_class: The :class:`~concoursetools.resource.ConcourseResource` class to be exported.
    :param method_name: The name of the method to be invoked.
    :param executable: The executable to use for the script (at the top).
    :param permissions: The (Linux) permissions the file should have. Defaults to ``rwxr-xr-x``.
    :param encoding: The encoding of the file as passed to :meth:`~pathlib.Path.write_text`.
                     Setting to :data:`None` (default) will use the user's default encoding.
    """
    method: MethodType = getattr(resource_class, method_name)
    docstring = inspect.getdoc(method) or ""
    docstring_header, *_ = docstring.split("\n")

    contents = textwrap.dedent(f"""
    #!{executable}
    \"\"\"
    {docstring_header}
    \"\"\"
    from {resource_class.__module__} import {resource_class.__name__}


    if __name__ == "__main__":
        {resource_class.__name__}.{method_name}()
    """).lstrip()

    path.write_text(contents, encoding=encoding)
    path.chmod(permissions)
