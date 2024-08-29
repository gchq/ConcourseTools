# (C) Crown Copyright GCHQ
from collections.abc import Generator
from contextlib import contextmanager, redirect_stderr, redirect_stdout
from io import StringIO
import json
import shutil
import textwrap
import unittest
import unittest.mock

from concoursetools import __version__
from concoursetools.cli.parser import _ANNOTATIONS_TO_TYPES, _CURRENT_PYTHON_VERSION, CLI, Docstring


class ParsingTests(unittest.TestCase):

    def test_all_defaults(self) -> None:
        args, kwargs = test_cli.commands["first_command"].parse_args(["abcd", "123"])
        self.assertListEqual(args, ["abcd", 123])
        self.assertDictEqual(kwargs, {
            "option_1": "value",
            "option_2": False,
        })

    def test_parsing_args(self) -> None:
        args, kwargs = test_cli.commands["first_command"].parse_args(["abcd", "123", "--option-1", "new_value", "--option-2"])
        self.assertListEqual(args, ["abcd", 123])
        self.assertDictEqual(kwargs, {
            "option_1": "new_value",
            "option_2": True,
        })

    def test_parsing_shorter_args(self) -> None:
        args, kwargs = test_cli.commands["first_command"].parse_args(["abcd", "123", "-o", "new_value", "--option-2"])
        self.assertListEqual(args, ["abcd", 123])
        self.assertDictEqual(kwargs, {
            "option_1": "new_value",
            "option_2": True,
        })

    def test_missing_positional(self) -> None:
        with self.assertCLIError():
            test_cli.commands["first_command"].parse_args([])

    def test_incorrect_keyword(self) -> None:
        with self.assertCLIError():
            test_cli.commands["first_command"].parse_args([".", "--aption"])

    @contextmanager
    def assertCLIError(self) -> Generator[None, None, None]:
        with self.assertRaises(SystemExit):
            with redirect_stderr(StringIO()):
                yield


class InvokeTests(unittest.TestCase):

    def test_defaults(self) -> None:
        new_stdout = StringIO()
        with redirect_stdout(new_stdout):
            test_cli.invoke(["first_command", "abcd", "123"])
        self.assertEqual(new_stdout.getvalue(), textwrap.dedent("""
        {
          "positional": {
            "1": "abcd",
            "2": 123
          },
          "optional": {
            "1": "value",
            "2": false
          }
        }
        """).lstrip())

    def test_args(self) -> None:
        new_stdout = StringIO()
        with redirect_stdout(new_stdout):
            test_cli.invoke(["first_command", "abcd", "123", "--option-1", "new_value", "--option-2"])
        self.assertEqual(new_stdout.getvalue(), textwrap.dedent("""
        {
          "positional": {
            "1": "abcd",
            "2": 123
          },
          "optional": {
            "1": "new_value",
            "2": true
          }
        }
        """).lstrip())


class HelpTests(unittest.TestCase):
    """
    Tests for the --help CLI option.
    """
    maxDiff = None

    def test_version(self) -> None:
        new_stdout = StringIO()
        with redirect_stdout(new_stdout):
            test_cli.invoke(["--version"])

        self.assertEqual(new_stdout.getvalue(), f"Concourse Tools v{__version__}\n")

    def test_generic_help(self) -> None:
        new_stdout = StringIO()
        with redirect_stdout(new_stdout):
            test_cli.invoke(["--help"])

        self.assertEqual(new_stdout.getvalue(), textwrap.dedent("""
        Usage:
          python3 -m concoursetools <command> [OPTIONS]

        Global Options:
          -h, --help      Show this help message
          -v, --version   Show the Concourse Tools version

        Available Commands:
          first_command   Invoke a test command.
          second_command  Invoke a second test command.

        """).lstrip())

    def test_generic_help_no_arguments(self) -> None:
        new_stdout = StringIO()
        with redirect_stdout(new_stdout):
            test_cli.invoke([])

        self.assertEqual(new_stdout.getvalue(), textwrap.dedent("""
        Usage:
          python3 -m concoursetools <command> [OPTIONS]

        Global Options:
          -h, --help      Show this help message
          -v, --version   Show the Concourse Tools version

        Available Commands:
          first_command   Invoke a test command.
          second_command  Invoke a second test command.

        """).lstrip())

    def first_command_help(self) -> None:
        with self._mock_terminal_width(120):
            width, _ = shutil.get_terminal_size()
            self.assertGreaterEqual(width, 120)

            new_stdout = StringIO()
            with redirect_stdout(new_stdout):
                test_cli.invoke(["first_command", "--help"])

        self.assertEqual(new_stdout.getvalue(), textwrap.dedent("""
        Usage:
          python3 -m concoursetools first_command <arg_1> <arg_2> [OPTIONS]

        Global Options:
          -h, --help      Show this help message

        Command Arguments (required):
          arg_1           The first positional argument.
          arg_2           The second positional argument.

        Command Options:
          -o, --option-1  The first optional argument.
          --option-2      The second optional argument.

        """).lstrip())

    def test_narrow_help_string(self) -> None:
        with self._mock_terminal_width(80):
            width, _ = shutil.get_terminal_size()
            self.assertEqual(width, 80)

            new_stdout = StringIO()
            with redirect_stdout(new_stdout):
                test_cli.invoke(["first_command", "--help"])

        self.assertEqual(new_stdout.getvalue(), textwrap.dedent("""
        Usage:
          python3 -m concoursetools first_command <arg_1> <arg_2> [OPTIONS]

        Global Options:
          -h, --help      Show this help message

        Command Arguments (required):
          arg_1           The first positional argument.
          arg_2           The second positional argument.

        Command Options:
          -o, --option-1  The first optional argument.
          --option-2      The second optional argument.

        """).lstrip())

    def test_narrower_help_string(self) -> None:
        with self._mock_terminal_width(40):
            width, _ = shutil.get_terminal_size()
            self.assertEqual(width, 40)

            new_stdout = StringIO()
            with redirect_stdout(new_stdout):
                test_cli.invoke(["first_command", "--help"])

        self.assertEqual(new_stdout.getvalue(), textwrap.dedent("""
        Usage:
          python3 -m concoursetools \\
            first_command <arg_1> <arg_2> \\
            [OPTIONS]

        Global Options:
          -h, --help      Show this help message

        Command Arguments (required):
          arg_1           The first positional
                          argument.
          arg_2           The second positional
                          argument.

        Command Options:
          -o, --option-1  The first optional
                          argument.
          --option-2      The second optional
                          argument.

        """).lstrip())

    @staticmethod
    @contextmanager
    def _mock_terminal_width(new_width: int) -> Generator[None, None, None]:
        _, current_height = shutil.get_terminal_size()
        with unittest.mock.patch("shutil.get_terminal_size", lambda: (new_width, current_height)):
            yield


class AnnotationTests(unittest.TestCase):
    """
    Tests for the _ANNOTATIONS_TO_TYPE mapping.
    """
    def test_strings(self) -> None:
        self.assertEqual(_ANNOTATIONS_TO_TYPES["str"], str)
        self.assertEqual(_ANNOTATIONS_TO_TYPES["bool"], bool)
        self.assertEqual(_ANNOTATIONS_TO_TYPES["int"], int)
        self.assertEqual(_ANNOTATIONS_TO_TYPES["float"], float)

    def test_optional_strings(self) -> None:
        self.assertEqual(_ANNOTATIONS_TO_TYPES["str | None"], str)
        self.assertEqual(_ANNOTATIONS_TO_TYPES["bool | None"], bool)
        self.assertEqual(_ANNOTATIONS_TO_TYPES["int | None"], int)
        self.assertEqual(_ANNOTATIONS_TO_TYPES["float | None"], float)

    def test_types(self) -> None:
        self.assertEqual(_ANNOTATIONS_TO_TYPES[str], str)
        self.assertEqual(_ANNOTATIONS_TO_TYPES[bool], bool)
        self.assertEqual(_ANNOTATIONS_TO_TYPES[int], int)
        self.assertEqual(_ANNOTATIONS_TO_TYPES[float], float)

    def test_optional_types(self) -> None:
        if _CURRENT_PYTHON_VERSION < (3, 10):
            self.skipTest("Union types with '|' only valid for Python >= 3.10.")
        self.assertEqual(_ANNOTATIONS_TO_TYPES[str | None], str)
        self.assertEqual(_ANNOTATIONS_TO_TYPES[bool | None], bool)
        self.assertEqual(_ANNOTATIONS_TO_TYPES[int | None], int)
        self.assertEqual(_ANNOTATIONS_TO_TYPES[float | None], float)

    def test_reversed_optional_string_fails(self) -> None:
        with self.assertRaises(KeyError):
            _ANNOTATIONS_TO_TYPES["None | str"]


class DocstringTests(unittest.TestCase):
    """
    Tests for the docstring parser.
    """
    def test_empty(self) -> None:

        def func() -> None:
            pass

        docstring = Docstring.from_object(func)
        self.assertEqual(docstring.first_line, "")
        self.assertEqual(docstring.description, "")
        self.assertDictEqual(docstring.parameters, {})

    def test_one_line(self) -> None:

        def func() -> None:
            """A simple function."""
            pass

        docstring = Docstring.from_object(func)
        self.assertEqual(docstring.first_line, "A simple function.")
        self.assertEqual(docstring.description, "")
        self.assertDictEqual(docstring.parameters, {})

    def test_with_params(self) -> None:

        def func() -> None:
            """
            A simple function.

            :param param_1: A simple parameter.
            :param param_2: A more complex parameter with a description that
                            spans multiple lines.
            """

        docstring = Docstring.from_object(func)
        self.assertEqual(docstring.first_line, "A simple function.")
        self.assertEqual(docstring.description, "")
        self.assertDictEqual(docstring.parameters, {
            "param_1": "A simple parameter.",
            "param_2": "A more complex parameter with a description that spans multiple lines.",
        })

    def test_multiline_with_params(self) -> None:

        def func() -> None:
            """
            A simple function.

            This is a more complex description that
            spans multiple lines.

            :param param_1: A simple parameter.
            :param param_2: A more complex parameter with a description that
                            spans multiple lines.
            """

        docstring = Docstring.from_object(func)
        self.assertEqual(docstring.first_line, "A simple function.")
        self.assertEqual(docstring.description, "This is a more complex description that\nspans multiple lines.")
        self.assertDictEqual(docstring.parameters, {
            "param_1": "A simple parameter.",
            "param_2": "A more complex parameter with a description that spans multiple lines.",
        })

    def test_with_only_params(self) -> None:

        def func() -> None:
            """
            :param param_1: A simple parameter.
            :param param_2: A more complex parameter with a description that
                            spans multiple lines.
            """

        docstring = Docstring.from_object(func)
        self.assertEqual(docstring.first_line, "")
        self.assertEqual(docstring.description, "")
        self.assertDictEqual(docstring.parameters, {
            "param_1": "A simple parameter.",
            "param_2": "A more complex parameter with a description that spans multiple lines.",
        })


test_cli = CLI()


@test_cli.register(allow_short={"option_1"})
def first_command(arg_1: str, arg_2: int, /, *, option_1: str = "value", option_2: bool = False) -> None:
    """
    Invoke a test command.

    :param arg_1: The first positional argument.
    :param arg_2: The second positional argument.
    :param option_1: The first optional argument.
    :param option_2: The second optional argument.
    """
    command_json = {
        "positional": {
            "1": arg_1,
            "2": arg_2,
        },
        "optional": {
            "1": option_1,
            "2": option_2
        }
    }
    print(json.dumps(command_json, indent=2))


@test_cli.register()
def second_command() -> None:
    """Invoke a second test command."""
