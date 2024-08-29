# (C) Crown Copyright GCHQ
"""
Concourse Tools uses a custom CLI tool for easier management of command line functions.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from argparse import ArgumentParser
from collections.abc import Callable, Generator
from dataclasses import dataclass
import inspect
import shutil
import sys
import textwrap
from typing import Any, Generic, TypeVar

from concoursetools import __version__
from concoursetools.cli.docstring import Docstring

_CURRENT_PYTHON_VERSION = (sys.version_info.major, sys.version_info.minor)

if _CURRENT_PYTHON_VERSION >= (3, 10):
    from types import UnionType
    _ANNOTATIONS_TO_TYPES: dict[type[Any] | UnionType | str, type] = {}
else:
    _ANNOTATIONS_TO_TYPES: dict[type[Any] | Any | str, type] = {}  # type: ignore[no-redef]

CLIFunction = Callable[..., None]
CLIFunctionT = TypeVar("CLIFunctionT", bound=CLIFunction)
T = TypeVar("T")

_AVAILABLE_TYPES = (str, bool, int, float)

for type_ in _AVAILABLE_TYPES:
    _ANNOTATIONS_TO_TYPES.update({
        type_: type_,
        type_.__name__: type_,
        f"{type_.__name__} | None": type_,
    })
    if _CURRENT_PYTHON_VERSION >= (3, 10):
        _ANNOTATIONS_TO_TYPES[type_ | None] = type_


class _CLIParser(ABC):

    @abstractmethod
    def invoke(self, args: list[str]) -> None:
        """
        Invoke the CLI.

        :param args: Arguments to be parsed.
        """
        ...

    def print_help_page(self, usage_string: str, help_sections: dict[str, dict[str, str | None]], spacing: int = 2,
                        separation: int = 1) -> None:
        max_key_width = max(self._max_key_length(d) for _, d in help_sections.items())

        self.print_help_section("Usage", {usage_string: None}, key_width=max_key_width, spacing=spacing)

        separator = "\n" * separation
        print(separator, end="")

        for title, options in help_sections.items():
            self.print_help_section(title, options, key_width=max_key_width, spacing=spacing)
            print(separator, end="")

    def print_help_section(self, title: str, options: dict[str, str | None], spacing: int = 2,
                           key_width: int | None = None, sort_keys: bool = False) -> None:
        """
        Print a section in the help page.

        :param title: The title of the section.
        :param options: Keys and values for the options.
        :param spacing: The size of the indent for the keys and values, as well as the minimum spacing between keys and values.
        :param key_width: The width of the key column. If set to :data:`None`, the width will be determined as the maximum length of all of the keys.
        :param sort_keys: Set to :data:`True` to sort the keys before printing. Otherwise they are printed in dictionary order.
        """
        print(f"{title}:")
        margin = " " * spacing
        if key_width is None:
            key_width = self._max_key_length(options)

        if sort_keys:
            items = sorted(options.items())
        else:
            items = list(options.items())

        total_indent_length = (spacing + key_width + spacing)
        max_width, _ = shutil.get_terminal_size()
        wrapper = textwrap.TextWrapper(width=max_width, subsequent_indent=" " * total_indent_length)

        usage_suffix = " \\"
        usage_wrapper = textwrap.TextWrapper(width=max_width - len(usage_suffix), subsequent_indent=" " * (spacing + 2))

        for key, value in items:
            if value is None:  # this is for the usage string
                unwrapped_line = margin + key.ljust(key_width)
                *lines, final_line = usage_wrapper.wrap(unwrapped_line)
                for line in lines:
                    print(line + usage_suffix)
                print(final_line)
            else:
                unwrapped_line = margin + key.ljust(key_width) + margin + value
                for line in wrapper.wrap(unwrapped_line):
                    print(line)

    @staticmethod
    def _max_key_length(d: dict[str, Any]) -> int:
        return max((len(key) for key in d), default=0)


class CLI(_CLIParser):
    """
    Represents a command line interface.
    """
    def __init__(self) -> None:
        self.commands: dict[str, CLICommand] = {}

    def invoke(self, args: list[str]) -> None:
        """
        Invoke the CLI.

        :param args: Arguments to be parsed.
        """
        try:
            command_name, *remaining_args = args
        except ValueError:
            if args:
                raise
            return self.print_help()
        try:
            command = self.commands[command_name]
        except KeyError:
            if command_name in set(HELP_OPTION.aliases):
                return self.print_help()
            elif command_name in set(VERSION_OPTION.aliases):
                return self.print_version()
            return self.invoke(["legacy"] + args)
        command.invoke(remaining_args)

    def register(self, allow_short: set[str] | None = None) -> Callable[[CLIFunctionT], CLIFunctionT]:
        """
        Decorate a function.

        The decorated function will be registered as a command. Positional-only parameters will become arguments
        and keyword-only parameters will become options. All parameters must be one or the other.

        :param allow_short: A set of function parameters that are allowed a one-letter alias. By default,
                            the parameter ``my_parameter`` becomes ``--my-parameter``, but by including
                            ``my_parameter`` in this set, ``-m`` will also be valid on the command line.
        """
        def decorator(func: CLIFunctionT) -> CLIFunctionT:
            self.register_function(func, allow_short=allow_short)
            return func
        return decorator

    def register_function(self, func: CLIFunction, allow_short: set[str] | None = None) -> None:
        """
        Manually register a function.

        :param func: A function to be registered as a command. Positional-only parameters will become arguments
                     and keyword-only parameters will become options. All parameters must be one or the other.
        :param allow_short: A set of function parameters that are allowed a one-letter alias. By default,
                            the parameter ``my_parameter`` becomes ``--my-parameter``, but by including
                            ``my_parameter`` in this set, ``-m`` will also be valid on the command line.
        """
        if allow_short is None:
            allow_short = set()

        cli_command = CLICommand.from_function(func, allow_short)
        self.commands[cli_command.name] = cli_command

    def print_help(self, spacing: int = 2, separation: int = 1) -> None:
        """
        Print the help page.

        :param spacing: The size of the indent for the keys and values, as well as the minimum spacing
                        between keys and values.
        :param separation: The number of new lines between help sections.
        """
        usage_string = "python3 -m concoursetools <command> [OPTIONS]"

        global_options: dict[str, str | None] = {
            "-h, --help": "Show this help message",
            "-v, --version": "Show the Concourse Tools version",
        }

        major_sections = {
            "Global Options": global_options,
            "Available Commands": {command_name: self.commands[command_name].description
                                   for command_name in sorted(self.commands)}
        }

        self.print_help_page(usage_string, major_sections, spacing=spacing, separation=separation)

    def print_version(self) -> None:
        """Print the version of Concourse Tools."""
        print(f"Concourse Tools v{__version__}")


class CLICommand(_CLIParser):
    """
    Represents a command in a CLI.

    :param name: The name of the command.
    :param description: An optional description of the command.
    :param inner_function: The function on which the command is based.
    :param inner_parser: Used to parse the arguments for the command.
    :param positional_arguments: A list of positional arguments.
    :param options: A list of options.
    """
    def __init__(self, name: str, description: str | None, inner_function: CLIFunction, inner_parser: ArgumentParser,
                 positional_arguments: list[PositionalArgument[Any]], options: list[Option[Any]]) -> None:
        self.name = name
        self.description = description
        self.inner_function = inner_function
        self.inner_parser = inner_parser
        self.positional_arguments = positional_arguments
        self.options = options

    def invoke(self, args: list[str]) -> None:
        """
        Invoke the CLI.

        :param args: Arguments to be parsed.
        """
        if set(HELP_OPTION.aliases) & set(args):
            return self.print_help()

        args, kwargs = self.parse_args(args)
        self.inner_function(*args, **kwargs)

    def parse_args(self, args: list[str]) -> tuple[list[Any], dict[str, Any]]:
        """
        Parse the arguments for a function.

        :param args: Arguments to be parsed.
        :returns: The args and kwargs to be passed to the inner function.
        """
        parsed_args_namespace = self.inner_parser.parse_args(args)
        kwargs = dict(parsed_args_namespace._get_kwargs())
        args = []
        for param_name, parameter in inspect.signature(self.inner_function).parameters.items():
            if parameter.kind is inspect._ParameterKind.POSITIONAL_ONLY:
                value = kwargs.pop(param_name)
                args.append(value)
        return args, kwargs

    def print_help(self, spacing: int = 2, separation: int = 1) -> None:
        """
        Print the help page for the command.

        :param spacing: The size of the indent for the keys and values, as well as the minimum spacing
                        between keys and values.
        :param separation: The number of new lines between help sections.
        """
        global_options: dict[str, str | None] = {
            "-h, --help": "Show this help message",
        }

        command_arguments: dict[str, str | None] = {parameter.name: parameter.description or "" for parameter in self.positional_arguments}
        command_options: dict[str, str | None] = {", ".join(parameter.aliases): parameter.description for parameter in self.options}

        major_sections = {
            "Global Options": global_options,
            "Command Arguments (required)": command_arguments,
            "Command Options": command_options,
        }

        self.print_help_page(major_sections, spacing=spacing, separation=separation)

    def print_help_page(self, help_sections: dict[str, dict[str, str | None]], spacing: int = 2,
                        separation: int = 1) -> None:

        self.print_help_section("Usage", {self.usage_string(): None}, spacing=spacing)

        separator = "\n" * separation
        print(separator, end="")

        max_key_width = max(self._max_key_length(d) for _, d in help_sections.items())

        for title, options in help_sections.items():
            self.print_help_section(title, options, key_width=max_key_width, spacing=spacing)
            print(separator, end="")

    def usage_string(self) -> str:
        """Return the usage string for the command."""
        usage_components = ["python3 -m concoursetools", self.name]
        for parameter in self.positional_arguments:
            usage_components.append(f"<{parameter.name}>")

        usage_components.append("[OPTIONS]")
        return " ".join(usage_components)

    @classmethod
    def from_function(cls, func: CLIFunction, allow_short: set[str] | None = None) -> CLICommand:
        """
        Create a new parser from a function.

        :param func: A function to be registered as a command. Positional-only parameters will become arguments
                     and keyword-only parameters will become options. All parameters must be one or the other.
        :param allow_short: A set of function parameters that are allowed a one-letter alias. By default,
                            the parameter ``my_parameter`` becomes ``--my-parameter``, but by including
                            ``my_parameter`` in this set, ``-m`` will also be valid on the command line.
        """
        if allow_short is None:
            allow_short = set()

        docstring = Docstring.from_object(func)

        parser = ArgumentParser(f"python3 -m concoursetools {func.__name__}", description=docstring.first_line)
        positional_arguments: list[PositionalArgument[Any]] = []
        options: list[Option[Any]] = []

        for parameter in Parameter.yield_from_function(func, allow_short):
            parameter.add_to_parser(parser)
            if isinstance(parameter, Option):
                options.append(parameter)
            elif isinstance(parameter, PositionalArgument):
                positional_arguments.append(parameter)
            else:
                raise TypeError

        return cls(func.__name__, docstring.first_line, func, parser, positional_arguments, options)


@dataclass
class Parameter(ABC, Generic[T]):
    """
    Represents a generic function/CLI parameter.

    :param name: The name of the parameter.
    :param param_type: The Python type of the parameter.
    :param description: An optional description of the parameter.
    """
    name: str
    param_type: type[T]
    description: str | None = None

    @property
    def long_alias(self) -> str:
        """
        The long alias for the parameter.

        :Example:
            >>> Option("my_option", str).long_alias
            '--my-option'
        """
        return f"--{self.name}".replace("_", "-")

    @property
    def short_alias(self) -> str:
        """
        The short alias for the parameter.

        :Example:
            >>> Option("my_option", str).short_alias
            '-m'
        """
        return f"-{self.name[0]}"

    @property
    @abstractmethod
    def aliases(self) -> tuple[str, ...]:
        """The aliases for the option."""
        ...

    @abstractmethod
    def add_to_parser(self, parser: ArgumentParser) -> None:
        """
        Add the parameter to a parser.

        :param parser: The parser in question.
        :seealso: This is done using :meth:`argparse.ArgumentParser.add_argument`.
        """
        ...

    @classmethod
    def yield_from_function(cls, func: CLIFunction, allow_short: set[str]) -> Generator[Parameter[Any], None, None]:
        """
        Yield parameters from a function.

        Parameters are parsed from the docstring using a combination of :func:`inspect.signature`
        and :meth:`concoursetools.cli.docstring.Docstring.from_object`.

        :param func: The function to parse.
        :param allow_short: A set of function parameters that are allowed a one-letter alias. By default,
                            the parameter ``my_parameter`` becomes ``--my-parameter``, but by including
                            ``my_parameter`` in this set, ``-m`` will also be valid on the command line.
        """
        docstring = Docstring.from_object(func)

        for parameter_name, parameter in inspect.signature(func).parameters.items():
            parameter_help = docstring.parameters.get(parameter_name)
            parameter_type = _ANNOTATIONS_TO_TYPES[parameter.annotation]

            if parameter.kind is inspect._ParameterKind.POSITIONAL_ONLY:
                yield PositionalArgument(parameter_name, parameter_type, parameter_help)
            elif parameter.kind is inspect._ParameterKind.KEYWORD_ONLY:
                if issubclass(parameter_type, bool):
                    yield FlagOption(parameter_name, parameter_help, parameter.default)
                else:
                    yield Option(parameter_name, parameter_type, parameter_help, parameter.default,
                                 allow_short=(parameter_name in allow_short))
            else:
                raise ValueError("Parameters must be positional or keyword only.")


@dataclass
class PositionalArgument(Parameter[T]):
    """
    Represents a positional function/CLI parameter.

    :param name: The name of the argument.
    :param param_type: The Python type of the argument.
    :param description: An optional description of the argument.
    """
    @property
    def aliases(self) -> tuple[str, ...]:
        """The aliases for the option."""
        return (self.name,)

    def add_to_parser(self, parser: ArgumentParser) -> None:
        parser.add_argument(*self.aliases, type=self.param_type, help=self.description)


@dataclass
class Option(Parameter[T]):
    """
    Represents a generic function/CLI option.

    :param name: The name of the option.
    :param param_type: The Python type of the option.
    :param description: An optional description of the option.
    :param default: The option default, if set.
    :param allow_short: Set to :data:`True` to allow a short option, i.e. ``-o`` as well as ``--option``.
    """
    default: T | None = None
    allow_short: bool = False

    @property
    def aliases(self) -> tuple[str, ...]:
        if self.allow_short:
            return (self.short_alias, self.long_alias)
        return (self.long_alias,)

    def add_to_parser(self, parser: ArgumentParser) -> None:
        parser.add_argument(*self.aliases, type=self.param_type, default=self.default, help=self.description)


class FlagOption(Option[bool]):
    """
    Represents a generic function/CLI flag.

    :param name: The name of the flag.
    :param description: An optional description of the flag.
    :param default: The option default, if set. Should be either :data:`True` or :data:`False`.
    """
    def __init__(self, name: str, description: str | None, default: bool):
        super().__init__(name, bool, description, default, allow_short=False)

    def add_to_parser(self, parser: ArgumentParser) -> None:
        parser.add_argument(*self.aliases, action="store_true", help=self.description)


HELP_OPTION = Option("help", bool, "", allow_short=True)
VERSION_OPTION = Option("version", bool, "", allow_short=True)
