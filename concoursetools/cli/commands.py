# (C) Crown Copyright GCHQ
"""
Commands for the Concourse Tools CLI.
"""
from pathlib import Path
import textwrap

from concoursetools.cli.parser import CLI
from concoursetools.colour import Colour, colour_print
from concoursetools.dockertools import Namespace, create_asset_scripts, create_dockerfile
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
    create_asset_scripts(Path(path), resource_class, executable)


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
    parsed_args = Namespace(path=path, executable=executable, resource_file=resource_file, class_name=class_name,
                            docker=docker, include_rsa=include_rsa)
    if parsed_args.docker:
        create_dockerfile(parsed_args)
        return

    assets(path, executable=executable, resource_file=resource_file, class_name=class_name)
