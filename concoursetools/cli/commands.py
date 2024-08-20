# (C) Crown Copyright GCHQ
"""
Commands for the Concourse Tools CLI.
"""
from pathlib import Path
import textwrap

from concoursetools.cli.parser import CLI
from concoursetools.colour import Colour, colour_print
from concoursetools.dockertools import MethodName, Namespace, ScriptName, create_dockerfile, create_script_file
from concoursetools.importing import import_single_class_from_module
from concoursetools.resource import ConcourseResource

cli = CLI()


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
               class_name: str | None = None, include_rsa: bool = False) -> None:
    """
    Create the Dockerfile.

    :param path: The location to which to write the Dockerfile.
                 Pass '.' to write it to the current directory.
    :param executable: The python executable to place at the top of the file. Defaults to '/usr/bin/env python3'.
    :param resource_file: The path to the module containing the resource class. Defaults to 'concourse.py'.
    :param class_name: The name of the resource class in the module, if there are multiple.
    :param include_rsa: Enable the Dockerfile to (securely) use your RSA private key during building.
    """
    parsed_args = Namespace(path=path, executable=executable, resource_file=resource_file, class_name=class_name,
                            docker=True, include_rsa=include_rsa)
    create_dockerfile(parsed_args)


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
