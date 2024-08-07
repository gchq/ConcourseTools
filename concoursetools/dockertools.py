# (C) Crown Copyright GCHQ
"""
Functions for creating the Dockerfile or asset files.
"""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
import importlib
import inspect
from pathlib import Path
import sys
import textwrap
from types import MethodType
from typing import cast

from concoursetools import ConcourseResource
from concoursetools.typing import VersionProtocol, VersionT

DEFAULT_EXECUTABLE = "/usr/bin/env python3"
DEFAULT_PYTHON_VERSION = f"{sys.version_info.major}.{sys.version_info.minor}"


def create_dockerfile(args: "Namespace", encoding: str | None = None,
                      concoursetools_path: Path | None = None) -> None:
    """
    Create a skeleton dockerfile.

    :param args: The CLI args.
    :param encoding: The encoding of the file as passed to :meth:`~pathlib.Path.write_text`.
                     Setting to :obj:`None` (default) will use the user's default encoding.
    :param concoursetools_path: A path to a local copy of concoursetools. If not set to :obj:`None`, this directory
                                will be copied over an installed before any requirements. Path should be relative to
                                the current directory.
    """
    directory_path = Path(args.path)
    if directory_path.is_dir():
        file_path = directory_path / "Dockerfile"
    else:
        file_path = directory_path

    cli_split_command = ["python3", "-m", "concoursetools", ".", "-r", args.resource_file]
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


def create_asset_scripts(assets_folder: Path, resource_class: type[ConcourseResource],  # type: ignore[type-arg]
                         executable: str = DEFAULT_EXECUTABLE) -> None:
    """
    Create the scripts in a given folder.

    :param assets_folder: The location to which the assets folder will be written.
                          The folder will be created if it doesn't yet exist.
    :param resource_class: A :class:`~concoursetools.resource.ConcourseResource` subclass
                           whose methods will be passed to :func:`create_script_file`.
    :param executable: The executable to use for the script (at the top).
    """
    assets_folder.mkdir(parents=True, exist_ok=True)

    file_to_method: dict[str, Callable[[], None]] = {
        "check": resource_class.check_main,
        "in": resource_class.in_main,
        "out": resource_class.out_main,
    }
    for file_name, method in file_to_method.items():
        file_path = assets_folder / file_name
        create_script_file(file_path, method, executable)


def create_script_file(path: Path, method: Callable[[], None], executable: str = DEFAULT_EXECUTABLE,
                       permissions: int = 0o755, encoding: str | None = None) -> None:
    """
    Create a script file at a given path.

    :param path: The path at which the file will be created.
    :param method: The method of the :class:`~concoursetools.resource.ConcourseResource` to be exported.
    :param executable: The executable to use for the script (at the top).
    :param permissions: The (Linux) permissions the file should have. Defaults to ``rwxr-xr-x``.
    :param encoding: The encoding of the file as passed to :meth:`~pathlib.Path.write_text`.
                     Setting to :obj:`None` (default) will use the user's default encoding.
    """
    docstring = inspect.getdoc(method) or ""
    docstring_header, *_ = docstring.split("\n")

    method = cast(MethodType, method)
    resource_class = cast(type[ConcourseResource[VersionProtocol]], method.__self__)
    method_name = method.__name__

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


def file_path_to_import_path(file_path: Path) -> str:
    """
    Convert a file path to an import path.

    :param file_path: The path to a Python file.
    :raises ValueError: If the path doesn't end in a '.py' extension.

    :Example:
        >>> file_path_to_import_path(Path("module.py"))
        'module'
        >>> file_path_to_import_path(Path("path/to/module.py"))
        'path.to.module'
    """
    *path_components, file_name = file_path.parts
    module_name, extension = file_name.split(".")
    if extension != "py":
        raise ValueError(f"{file_path!r} does not appear to be a valid Python module")

    path_components.append(module_name)
    import_path = ".".join(path_components)
    return import_path


def import_resource_class_from_module(file_path: Path, class_name: str | None = None,
                                      parent_class: type[ConcourseResource[VersionT]] = ConcourseResource) -> type[ConcourseResource[VersionT]]:
    """
    Import the resource class from the module.

    Similar to :func:`import_resource_classes_from_module`, but ensures only one class is returned.

    :param file_path: The location of the module as a file path.
    :param class_name: The name of the class to extract. Required if multiple are returned.
    :param parent_class: All subclasses of this class defined within the module
                         (not imported from elsewhere) will be extracted.
    :returns: The extracted class.
    :raises RuntimeError: If too many or too few classes are available in the module, unless the class name is specified.
    """
    possible_resource_classes = import_resource_classes_from_module(file_path, parent_class=parent_class)

    if class_name is None:
        if len(possible_resource_classes) == 1:
            _, resource_class = possible_resource_classes.popitem()
        else:
            if len(possible_resource_classes) == 0:
                raise RuntimeError(f"No subclasses of {parent_class.__name__!r} found in {file_path}")
            raise RuntimeError(f"Multiple subclasses of {parent_class.__name__!r} found in {file_path}:"
                               f" {set(possible_resource_classes)}")
    else:
        resource_class = possible_resource_classes[class_name]

    return resource_class


def import_resource_classes_from_module(file_path: Path,
                                        parent_class: type[ConcourseResource[VersionT]] = ConcourseResource
                                        ) -> dict[str, type[ConcourseResource[VersionT]]]:
    """
    Import all available resource classes from the module.

    :param file_path: The location of the module as a file path.
    :param parent_class: All subclasses of this class defined within the module
                         (not imported from elsewhere) will be extracted.
    :returns: A mapping of class name to class.
    """
    import_path = file_path_to_import_path(file_path)

    try:
        module = importlib.import_module(import_path)
    except ModuleNotFoundError as error:
        if not file_path.exists():
            raise FileNotFoundError(file_path) from error
        raise

    possible_resource_classes: dict[str, type[ConcourseResource[VersionT]]] = {}
    for _, cls in inspect.getmembers(module, predicate=inspect.isclass):
        try:
            class_is_subclass_of_parent = issubclass(cls, parent_class)
        except TypeError:
            class_is_subclass_of_parent = False

        class_is_defined_in_this_module = (cls.__module__ == import_path)
        class_is_not_private = (not cls.__name__.startswith("_"))

        if class_is_subclass_of_parent and class_is_defined_in_this_module and class_is_not_private:
            possible_resource_classes[cls.__name__] = cls

    return possible_resource_classes


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
