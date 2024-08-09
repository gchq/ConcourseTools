# (C) Crown Copyright GCHQ
"""
Minor Sphinx extension for counting the number of lines in a file.

:linecount:`../relative/path/to/file.txt` will be replaced with the number of lines in `file.txt`.

Paths should be relative to the directory of the current file, not the source directory.
This is the same  path passed to literalinclude.
"""
from __future__ import annotations

from pathlib import Path

from docutils import nodes
from docutils.nodes import system_message
from docutils.parsers.rst.states import Inliner
from sphinx.application import Sphinx

__all__ = ("count_lines", "setup")


def count_lines(name: str, rawtext: str, text: str, lineno: int, inliner: Inliner, options: dict[str, object] = {},
                content: list[str] = []) -> tuple[list[nodes.Node], list[system_message]]:
    """
    Add a text node containing the number of lines.

    :param name: The local name of the interpreted role, the role name actually used in the document.
    :param rawtext: A string containing the entire interpreted text input, including the role and markup.
    :param text: The interpreted text content.
    :param lineno: The line number where the interpreted text begins.
    :param inliner: The :class:`docutils.parsers.rst.states.Inliner` object that called :func:`~.source_role`.
                    It contains the several attributes useful for error reporting and document tree access.
    :param options: A dictionary of directive options for customization (from the ``role`` directive),
                    to be interpreted by the function. Used for additional attributes for the generated elements
                    and other functionality.
    :param content: A list of strings, the directive content for customization (from the ``role`` directive).
                    To be interpreted by the function.

    :return: A list containing the created node, and a list containing any messages generated during the function.
    """
    path = Path(nodes.unescape(text))  # type: ignore[attr-defined]
    page_path = Path(Path(inliner.document.settings._source))
    resolved_path = (page_path.parent / path).resolve()
    with open(resolved_path) as rf:
        line_count = sum(1 for _ in rf)

    node = nodes.Text(str(line_count))
    return [node], []


def setup(app: Sphinx) -> dict[str, object]:
    """
    Attach the extension to the application.

    :param app: The Sphinx application.
    """
    app.add_role("linecount", count_lines)

    return {"parallel_read_safe": True}
