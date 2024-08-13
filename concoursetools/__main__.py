# (C) Crown Copyright GCHQ
"""
The main entrypoint for the Concourse Tools CLI:

    $ python3 -m concoursetools --help
"""
import sys

from concoursetools.cli import cli


def main() -> int:
    """Run the main function."""
    cli.invoke(sys.argv[1:])
    return 0


if __name__ == "__main__":
    main()
