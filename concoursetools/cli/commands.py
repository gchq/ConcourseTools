# (C) Crown Copyright GCHQ
"""
Commands for the Concourse Tools CLI.
"""
from __future__ import annotations

from pathlib import Path
import sys
import textwrap

from concoursetools.cli.parser import CLI
from concoursetools.colour import Colour, colour_print
from concoursetools.dockertools import MethodName, ScriptName, create_script_file
from concoursetools.importing import import_single_class_from_module
from concoursetools.resource import ConcourseResource

cli = CLI()

DEFAULT_PYTHON_VERSION = f"{sys.version_info.major}.{sys.version_info.minor}"


@cli.register(allow_short={"executable", "class_name", "resource_file"})
def assets(path: str, /, *, executable: str = "/usr/bin/env python3", resource_file: str = "concourse.py",
           class_name: str | None = None) -> None:
    """
    Create the assets script directory.

    :param path: The location at which to the script files will be written.
                 Pass '.' to write scripts to the current directory.
    :param executable: The python executable to place at the top of the file. Defaults to '/usr/bin/env python3'.
    :param resource_file: The path to the module containing the resource class. Defaults to 'concourse.py'.
    :param class_name: The name of the resource class in the module, if there are multiple.
    """
    resource_class = import_single_class_from_module(Path(resource_file), parent_class=ConcourseResource,  # type: ignore[type-abstract]
                                                     class_name=class_name)
    assets_folder = Path(path)
    assets_folder.mkdir(parents=True, exist_ok=True)

    file_name_to_method_name: dict[ScriptName, MethodName] = {
        "check": "check_main",
        "in": "in_main",
        "out": "out_main",
    }
    for file_name, method_name in file_name_to_method_name.items():
        file_path = assets_folder / file_name
        create_script_file(file_path, resource_class, method_name, executable)


@cli.register(allow_short={"executable", "class_name", "resource_file"})
def dockerfile(path: str, /, *, executable: str = "/usr/bin/env python3", resource_file: str = "concourse.py",
               class_name: str | None = None, include_rsa: bool = False, encoding: str | None = None,
               dev: bool = False) -> None:
    """
    Create the Dockerfile.

    :param path: The location to which to write the Dockerfile.
                 Pass '.' to write it to the current directory.
    :param executable: The python executable to place at the top of the file. Defaults to '/usr/bin/env python3'.
    :param resource_file: The path to the module containing the resource class. Defaults to 'concourse.py'.
    :param class_name: The name of the resource class in the module, if there are multiple.
    :param include_rsa: Enable the Dockerfile to (securely) use your RSA private key during building.
    :param encoding: The encoding of the created file. If not passed, Concourse Tools will use the user's default encoding.
    :param dev: Pass to copy a local version of Concourse Tools to the image, instead of installing from PyPI.
                The onus is on the user to ensure that the "concoursetools" exists in the working directory at
                Docker build time.
    """
    directory_path = Path(path)
    if directory_path.is_dir():
        file_path = directory_path / "Dockerfile"
    else:
        file_path = directory_path

    cli_split_command = ["python3", "-m", "concoursetools", "assets", ".", "-r", resource_file]
    if class_name is not None:
        cli_split_command.extend(["-c", class_name])

    cli_command = " ".join(cli_split_command)

    if dev is False:
        pip_install_command = """
        RUN python3 -m pip install --upgrade pip && \\
            pip install -r requirements.txt --no-deps
        """.strip()
    else:
        pip_install_command = """
        COPY concoursetools concoursetools

        RUN python3 -m pip install --upgrade pip && \\
            pip install ./concoursetools && \\
            pip install -r requirements.txt --no-deps
        """.strip()

    if include_rsa:
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
        COPY {resource_file} ./{resource_file}
        RUN {cli_command}

        ENTRYPOINT ["python3"]
        """).lstrip()
    else:
        contents = textwrap.dedent(f"""
        FROM python:{DEFAULT_PYTHON_VERSION}-alpine

        COPY requirements.txt requirements.txt

        {pip_install_command}

        WORKDIR /opt/resource/
        COPY {resource_file} ./{resource_file}
        RUN {cli_command}

        ENTRYPOINT ["python3"]
        """).lstrip()

    file_path.write_text(contents, encoding=encoding)


@cli.register(allow_short={"executable", "class_name", "resource_file"})
def legacy(path: str, /, *, executable: str = "/usr/bin/env python3", resource_file: str = "concourse.py",
           class_name: str | None = None, docker: bool = False, include_rsa: bool = False) -> None:
    """
    Invoke the legacy CLI.

    :param path: The location at which to place the scripts.
    :param executable: The python executable to place at the top of the file. Defaults to '/usr/bin/env python3'.
    :param resource_file: The path to the module containing the resource class. Defaults to 'concourse.py'.
    :param class_name: The name of the resource class in the module, if there are multiple.
    :param docker: Pass to create a skeleton Dockerfile at the path instead.
    :param include_rsa: Enable the Dockerfile to (securely) use your RSA private key during building.
    """
    colour_print(textwrap.dedent("""
    The legacy CLI has been deprecated.
    Please refer to the documentation or help pages for the up to date CLI.
    This CLI will be removed in version 0.10.0, or in version 1.0.0, whichever is sooner.
    """), colour=Colour.RED)
    if docker:
        return dockerfile(path, executable=executable, resource_file=resource_file, class_name=class_name,
                          include_rsa=include_rsa)
    assets(path, executable=executable, resource_file=resource_file, class_name=class_name)
