# (C) Crown Copyright GCHQ
"""
Minor Sphinx extension for creating Concourse documentation links, based on https://sphinx-toolbox.readthedocs.io/en/stable/extensions/wikipedia.html.

:concourse:`jobs` will create a link to /jobs.html with the text "jobs".
:concourse:`jobs.thing.thing2` will create a link to /jobs.html#thing1.thing2 with the text "thing2".
:concourse:`jobs-a-b-c` will create a link to /jobs-a-b-c.html with the text "jobs a b c".
:concourse:`job <jobs>` will create a link to /jobs.html with the text "job".
:concourse:`job <jobs.thing1.thing2>` will create a link to /jobs.html#thing1.thing2 with the text "job".

Set ``concourse_base_url`` in ``conf.py`` to change the URL used. It must contain "{target}" to be populated.
"""
from __future__ import annotations

from typing import Any
from urllib.parse import quote

from docutils import nodes
from docutils.nodes import system_message
from docutils.parsers.rst.states import Inliner
from sphinx.application import Sphinx
from sphinx.util.nodes import split_explicit_title

__all__ = ("make_concourse_link", "setup")

DEFAULT_BASE_URL = "https://concourse-ci.org/{target}"


def make_concourse_link(name: str, rawtext: str, text: str, lineno: int, inliner: Inliner, options: dict[str, Any] = {},
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
    _, title, target = split_explicit_title(text)

    title = title.split(".")[-1].replace("-", " ")

    page, *anchors = quote(target.replace(" ", "_"), safe="").split(".", maxsplit=1)
    if anchors:
        anchor = ".".join(anchors)
        new_target = f"{page}.html#{anchor}"
    else:
        new_target = f"{page}.html"

    base_url: str = inliner.document.settings.env.config.concourse_base_url  # type: ignore
    ref = base_url.format(target=new_target)

    node = nodes.reference(rawtext, title, refuri=str(ref), **options)
    return [node], []


def setup(app: Sphinx) -> dict[str, Any]:
    """
    Attach the extension to the application.

    :param app: The Sphinx application.
    """
    app.add_role("concourse", make_concourse_link)
    app.add_config_value("concourse_base_url", DEFAULT_BASE_URL, "env", [str])

    return {"parallel_read_safe": True}
