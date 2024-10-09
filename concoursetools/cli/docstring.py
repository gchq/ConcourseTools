# (C) Crown Copyright GCHQ
"""
Concourse Tools uses a custom CLI tool for easier management of command line functions.
"""
from __future__ import annotations

from collections.abc import Callable, Generator
from dataclasses import dataclass
import inspect
import re
from typing import TypeVar

RE_PARAM = re.compile(r":param (.*?):")
RE_WHITESPACE = re.compile(r"\s+")

CLIFunction = Callable[..., None]
CLIFunctionT = TypeVar("CLIFunctionT", bound=CLIFunction)
T = TypeVar("T")


@dataclass(frozen=True)
class Docstring:
    """
    Represents a function docstring.

    :param first_line: The first line of the docstring (separated by double whitespace).
    :param description: The remaining description before any parameters.
    :param parameters: A mapping of parameter name to description, with newlines replaced with whitespace.
    """
    first_line: str
    description: str
    parameters: dict[str, str]

    @classmethod
    def from_object(cls, obj: object) -> "Docstring":
        """
        Parse an object with a docstring.

        :param obj: An object which may have a docstring, such as a function or module.
        """
        raw_docstring = inspect.getdoc(obj) or ""
        return cls.from_string(raw_docstring)

    @classmethod
    def from_string(cls, raw_docstring: str) -> "Docstring":
        """
        Parse a docstring.

        :param raw_docstring: The raw docstring of an object.
        """
        try:
            first_line, remaining_lines = raw_docstring.split("\n\n", maxsplit=1)
        except ValueError:
            if RE_PARAM.match(raw_docstring.strip()):  # all we have are params with no description
                first_line = ""
                remaining_lines = raw_docstring.strip()
            else:
                first_line = raw_docstring.strip()
                return cls(first_line, "", {})

        description, *remaining_params = RE_PARAM.split(remaining_lines.lstrip())
        parameters = {param: " ".join(info.split()).strip() for param, info in _pair_up(remaining_params)}
        return cls(first_line, description.strip(), parameters)


def _pair_up(data: list[str]) -> Generator[tuple[str, str], None, None]:
    """
    Pair up a list of items.

    :param data: A list to be paired.
    :raises ValueError: If there are an odd number of values in the list.

    :Example:
        >>> list(_pair_up([1, 2, 3, 4, 5, 6]))
        [(1, 2), (3, 4), (5, 6)]
    """
    for i in range(0, len(data), 2):
        try:
            yield data[i], data[i+1]
        except IndexError:
            raise ValueError(f"Needed an even number of values, got {len(data)}")
