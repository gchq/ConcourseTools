# (C) Crown Copyright GCHQ
"""
Functions for creating the Dockerfile or asset files.
"""
from __future__ import annotations

from dataclasses import dataclass
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


def create_dockerfile(args: "Namespace", encoding: str | None = None,
                      concoursetools_path: Path | None = None) -> None:
    """
    Create a skeleton dockerfile.

    :param args: The CLI args.
    :param encoding: The encoding of the file as passed to :meth:`~pathlib.Path.write_text`.
                     Setting to :data:`None` (default) will use the user's default encoding.
    :param concoursetools_path: A path to a local copy of concoursetools. If not set to :data:`None`, this directory
                                will be copied over an installed before any requirements. Path should be relative to
                                the current directory.
    """
    directory_path = Path(args.path)
    if directory_path.is_dir():
        file_path = directory_path / "Dockerfile"
    else:
        file_path = directory_path

    cli_split_command = ["python3", "-m", "concoursetools", "assets", ".", "-r", args.resource_file]
    if args.class_name is not None:
        cli_split_command.extend(["-c", args.class_name])

    cli_command = " ".join(cli_split_command)

    if concoursetools_path is None:
        pip_install_command = """
        RUN python3 -m pip install --upgrade pip && \\
            pip install -r requirements.txt --no-deps
        """.strip()
    else:
        pip_install_command = f"""
        COPY {str(concoursetools_path)} concoursetools

        RUN python3 -m pip install --upgrade pip && \\
            pip install ./concoursetools && \\
            pip install -r requirements.txt --no-deps
        """.strip()

    if args.include_rsa:
        contents = textwrap.dedent(f"""
        FROM python:{DEFAULT_PYTHON_VERSION}-alpine as builder

        ARG ssh_known_hosts
        ARG ssh_private_key

        RUN mkdir -p /root/.ssh && chmod 0700 /root/.ssh
        RUN echo "$ssh_known_hosts" > /root/.ssh/known_hosts && chmod 600 /root/.ssh/known_hosts
        RUN echo "$ssh_private_key" > /root/.ssh/id_rsa && chmod 600 /root/.ssh/id_rsa

        COPY requirements.txt requirements.txt

        RUN python3 -m venv /opt/venv
        # Activate venv
        ENV PATH="/opt/venv/bin:$PATH"

        {pip_install_command}


        FROM python:{DEFAULT_PYTHON_VERSION}-alpine as runner
        COPY --from=builder /opt/venv /opt/venv
        # Activate venv
        ENV PATH="/opt/venv/bin:$PATH"

        WORKDIR /opt/resource/
        COPY {args.resource_file} ./{args.resource_file}
        RUN {cli_command}

        ENTRYPOINT ["python3"]
        """).lstrip()
    else:
        contents = textwrap.dedent(f"""
        FROM python:{DEFAULT_PYTHON_VERSION}-alpine

        COPY requirements.txt requirements.txt

        {pip_install_command}

        WORKDIR /opt/resource/
        COPY {args.resource_file} ./{args.resource_file}
        RUN {cli_command}

        ENTRYPOINT ["python3"]
        """).lstrip()

    file_path.write_text(contents, encoding=encoding)


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


@dataclass
class Namespace:
    """
    Represents the parsed args for typing purposes.

    :param path: The location at which to place the scripts.
    :param executable: The python executable to place at the top of the file.
    :param resource_file: The path to the module containing the resource class.
    :param class_name: The name of the resource class in the module, if there are multiple.
    :param docker: Pass to create a skeleton Dockerfile at the path instead.
    :param include_rsa: Enable the Dockerfile to (securely) use your RSA private key during building.
    """
    path: str
    executable: str = DEFAULT_EXECUTABLE
    resource_file: str = "concourse.py"
    class_name: str | None = None
    docker: bool = False
    include_rsa: bool = False

    @property
    def resource_path(self) -> Path:
        """Return a path object pointing to the resource file."""
        return Path(self.resource_file)
