# (C) Crown Copyright GCHQ
"""
Minor Sphinx extension for creating Concourse documentation links, based on https://sphinx-toolbox.readthedocs.io/en/stable/extensions/wikipedia.html.

Calling :concourse:`jobs` will create a link to the Concourse documentation. Rules for parsing links and text can be
found in the docstring examples of the ``parse_link_and_title`` function.

Set ``concourse_base_url`` in ``conf.py`` to change the URL used. It must contain "{target}" to be populated.
"""
from __future__ import annotations

from docutils import nodes
from docutils.nodes import system_message
from docutils.parsers.rst.states import Inliner
from sphinx.application import Sphinx
from sphinx.util.nodes import split_explicit_title

__all__ = ("make_concourse_link", "setup")

DEFAULT_BASE_URL = "https://concourse-ci.org/docs/{target}"


def make_concourse_link(name: str, rawtext: str, text: str, lineno: int, inliner: Inliner, options: dict[str, object] = {},
                        content: list[str] = []) -> tuple[list[nodes.reference], list[system_message]]:
    """
    Add a link to the given article on Concourse CI.

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
    text = nodes.unescape(text)
    target, title = parse_link_and_title(text)

    base_url: str = inliner.document.settings.env.config.concourse_base_url
    ref = base_url.format(target=target)

    node = nodes.reference(rawtext, title, refuri=str(ref), **options)
    return [node], []


def parse_link_and_title(text: str) -> tuple[str, str]:
    """
    Parse the link and title from text.

    :Example:
        >>> parse_link_and_title("steps")
        ('steps/', 'steps')
        >>> parse_link_and_title("steps.set_pipeline")
        ('steps/set-pipeline/', 'set_pipeline')
        >>> parse_link_and_title("steps.set_pipeline#instance_vars")
        ('steps/set-pipeline/#instance_vars', 'instance_vars')
        >>> parse_link_and_title("step <steps>")
        ('steps/', 'step')
        >>> parse_link_and_title("setting pipeline <steps.set_pipeline>")
        ('steps/set-pipeline/', 'setting pipeline')
        >>> parse_link_and_title("pipeline vars <steps.set_pipeline#instance_vars>")
        ('steps/set-pipeline/#instance_vars', 'pipeline vars')
    """
    _, title, target = split_explicit_title(text)

    new_title = title.split(".")[-1].split("#")[-1].replace("-", " ")

    try:
        page, anchor = target.split("#")
    except ValueError:
        page = target
        anchor = ""

    new_page = page.replace("_", "-").replace(".", "/")
    new_target = f"{new_page}/"
    new_target = f"{new_page}/#{anchor}" if anchor else f"{new_page}/"

    return new_target, new_title


def setup(app: Sphinx) -> dict[str, object]:
    """
    Attach the extension to the application.

    :param app: The Sphinx application.
    """
    app.add_role("concourse", make_concourse_link)
    app.add_config_value("concourse_base_url", DEFAULT_BASE_URL, "env", [str])

    return {"parallel_read_safe": True}
