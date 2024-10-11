# (C) Crown Copyright GCHQ
"""
Commands for the Concourse Tools CLI.
"""
from __future__ import annotations

from pathlib import Path
import sys
import textwrap

from concoursetools import dockertools
from concoursetools.cli.parser import CLI
from concoursetools.colour import Colour, colour_print
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

    file_name_to_method_name: dict[dockertools.ScriptName, dockertools.MethodName] = {
        "check": "check_main",
        "in": "in_main",
        "out": "out_main",
    }
    for file_name, method_name in file_name_to_method_name.items():
        file_path = assets_folder / file_name
        dockertools.create_script_file(file_path, resource_class, method_name, executable)


@cli.register(allow_short={"executable", "class_name", "resource_file"})
def dockerfile(path: str, /, *, executable: str = "/usr/bin/env python3", suffix: str | None = None,
               resource_file: str = "concourse.py", class_name: str | None = None, include_rsa: bool = False,
               encoding: str | None = None, no_venv: bool = False, dev: bool = False) -> None:
    """
    Create the Dockerfile.

    :param path: The location to which to write the Dockerfile.
                 Pass '.' to write it to the current directory.
    :param executable: The python executable to place at the top of the file. Defaults to '/usr/bin/env python3'.
    :param suffix: An optional suffix to combine with the tag to create the full tag.
    :param resource_file: The path to the module containing the resource class. Defaults to 'concourse.py'.
    :param class_name: The name of the resource class in the module, if there are multiple.
    :param include_rsa: Enable the Dockerfile to (securely) use your RSA private key during building.
    :param encoding: The encoding of the created file. If not passed, Concourse Tools will use the user's default encoding.
    :param no_venv: Pass to explicitly not use a virtual environment within the image. This is not recommended and exists
                    to ensure legacy behaviour.
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
    if suffix is None:
        tag = DEFAULT_PYTHON_VERSION
    else:
        tag = f"{DEFAULT_PYTHON_VERSION}-{suffix}"

    final_dockerfile = dockertools.Dockerfile()

    final_dockerfile.new_instruction_group(
        dockertools.FromInstruction(image="python", tag=tag),
    )

    if no_venv:
        if dev:
            raise ValueError("Can only specify --no-venv in production mode")
    else:
        final_dockerfile.new_instruction_group(
            dockertools.RunInstruction(["python3 -m venv /opt/venv"]),
            dockertools.Comment("Activate venv"),
            dockertools.EnvInstruction({"PATH": "/opt/venv/bin:$PATH"}),
        )

    final_dockerfile.new_instruction_group(
        dockertools.CopyInstruction("requirements.txt"),
    )

    if include_rsa:
        mounts: list[dockertools.Mount] | None = [
            dockertools.SecretMount(
                secret_id="private_key",
                target="/root/.ssh/id_rsa",
                mode=0o600,
                required=True,
            ),
            dockertools.SecretMount(
                secret_id="known_hosts",
                target="/root/.ssh/known_hosts",
                mode=0o644,
            ),
        ]
    else:
        mounts = None

    if dev:
        final_dockerfile.new_instruction_group(
            dockertools.CopyInstruction("concoursetools"),
        )
        final_dockerfile.new_instruction_group(
            dockertools.MultiLineRunInstruction([
                "python3 -m pip install --upgrade pip",
                "pip install ./concoursetools",
                "pip install -r requirements.txt --no-deps",
            ], mounts=mounts),
        )
    else:
        final_dockerfile.new_instruction_group(
            dockertools.MultiLineRunInstruction([
                "python3 -m pip install --upgrade pip",
                "pip install -r requirements.txt --no-deps",
            ], mounts=mounts),
        )

    final_dockerfile.new_instruction_group(
        dockertools.WorkDirInstruction("/opt/resource/"),
        dockertools.CopyInstruction(resource_file, f"./{resource_file}"),
        dockertools.RunInstruction([cli_command]),
    )

    final_dockerfile.new_instruction_group(
        dockertools.EntryPointInstruction(["python3"]),
    )

    final_dockerfile.write_to_file(file_path, encoding=encoding)


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
        return dockerfile(path, suffix="alpine", executable=executable, resource_file=resource_file, class_name=class_name,
                          include_rsa=include_rsa, no_venv=True)
    assets(path, executable=executable, resource_file=resource_file, class_name=class_name)
