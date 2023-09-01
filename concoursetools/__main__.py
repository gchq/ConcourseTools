# (C) Crown Copyright GCHQ
"""
Create the correct entry scripts for the Concourse resource.

Once you have copied the resource module across to /opt/resource in your Dockerfile,
change to within the directory and run the following to create the asset scripts:

    python3 -m concoursetools /opt/resource

Alternatively, create a skeleton Dockerfile with the following:

    python3 -m concoursetools --docker .

To see additional options, run:

    python3 -m concoursetools -h
"""
import argparse
import pathlib
import sys
from typing import List

from concoursetools.dockertools import Namespace, create_asset_scripts, create_dockerfile, import_resource_class_from_module


def main(args: List[str] = sys.argv[1:]) -> None:  # pylint: disable=dangerous-default-value
    """Run the main function."""
    parsed_args = parse_args(args)
    if parsed_args.docker:
        create_dockerfile(parsed_args)
        return

    resource_class = import_resource_class_from_module(parsed_args.resource_path, parsed_args.class_name)
    create_asset_scripts(pathlib.Path(parsed_args.path), resource_class, parsed_args.executable)


def parse_args(args: List[str]) -> Namespace:
    """Parse command line args."""
    parser = argparse.ArgumentParser()
    parser.add_argument("path", type=str, help="The location at which to place the scripts")
    parser.add_argument("-e", "--executable", type=str, default="/usr/bin/env python3",
                        help="The python executable to place at the top of the file")
    parser.add_argument("-r", "--resource-file", type=str, default="concourse.py",
                        help="The path to the module containing the resource class")
    parser.add_argument("-c", "--class-name", type=str,
                        help="The name of the resource class in the module, if there are multiple")
    parser.add_argument("--docker", action="store_true",
                        help="Pass to create a skeleton Dockerfile at the path instead")
    parser.add_argument("--include-rsa", action="store_true",
                        help="Enable the Dockerfile to (securely) use your RSA private key during building")
    parsed_args = parser.parse_args(args)
    namespace = Namespace(**dict(parsed_args._get_kwargs()))
    return namespace


if __name__ == "__main__":
    main()
