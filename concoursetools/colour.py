# (C) Crown Copyright GCHQ
"""
The Concourse web UI will interpret :wikipedia:`ANSI colour codes <ANSI_escape_code#Colors>`,
and so a handful of rudimentary functions for formatting with colour are include in
:mod:`concoursetools.colour`.

.. tip::
    There are plenty of more mature libraries for printing coloured output,
    such as `termcolor <https://pypi.org/project/termcolor/>`_ and
    `Rich <https://rich.readthedocs.io/en/stable/console.html#color-systems>`_.
    Concourse Tools specifically has no external dependencies, and so these
    must be actively installed and managed by a user.
"""
from contextlib import contextmanager
from typing import Any, Generator

END_COLOUR = "\033[0m"
BOLD = "\033[1m"
UNDERLINE = "\033[4m"


class _NoPrint(str):

    def __str__(self) -> str:
        raise TypeError("Can't print!")

    def __repr__(self) -> str:
        return f"{type(self).__name__}()"


MISSING_COLOUR = _NoPrint()


def colourise(string: str, colour: str) -> str:
    """
    Convert a string into a string which will be coloured on print.

    This enables coloured output within an f-string or similar. It is not recommended for
    colouring complete strings, as it is far less efficient than the other functions.

    :param string: The string to be colourised.
    :param colour: The :wikipedia:`ANSI colour escape code <ANSI_escape_code#Colors>`
                   for the required colour.

    :Example:

        >>> print(f"Hello {colourise('world', colour=Colour.RED)}")
    """
    return f"{colour}{string}{END_COLOUR}"


def colour_print(*values: Any, colour: str = MISSING_COLOUR, bold: bool = False, underline: bool = False,
                 **print_kwargs: Any) -> None:
    """
    Print something in colour.

    This function behaves exactly like :func:`print`, just with more functionality:

    :param colour: The :wikipedia:`ANSI colour escape code <ANSI_escape_code#Colors>` for the required colour.
    :param bold: Print the text in **bold**.
    :param underline: Print the text with an underline.

    :Example:

        >>> colour_print(1, 2, 3, sep="-", colour=Colour.GREEN)
    """
    try:
        with print_in_colour(colour, bold=bold, underline=underline):
            print(*values, **print_kwargs)
    except TypeError as error:
        if colour is MISSING_COLOUR:
            raise ValueError("You forgot to pass the colour as a keyword argument") from error
        raise


@contextmanager
def print_in_colour(colour: str, bold: bool = False, underline: bool = False) -> Generator[None, None, None]:
    """
    Print anything in colour within a :ref:`context manager <context-managers>`.

    This is especially useful for colourising output from other external functions
    which you cannot control.

    :param colour: The :wikipedia:`ANSI colour escape code <ANSI_escape_code#Colors>` for the required colour.
    :param bold: Print the text in **bold**.
    :param underline: Print the text with an underline.

    :Example:

        >>> with print_in_colour(Colour.BLUE, bold=True):
        ...     print("Hello!")
    """
    try:
        print(colour, end="")
        if bold:
            print(BOLD, end="")
        if underline:
            print(UNDERLINE, end="")
        yield
    finally:
        print(END_COLOUR, end="")


class Colour:
    """
    A few common ANSI colours.
    """
    BLUE = "\033[94m"
    CYAN = "\033[96m"
    GREEN = "\033[92m"
    PURPLE = "\033[95m"
    RED = "\033[91m"
    YELLOW = "\033[93m"
