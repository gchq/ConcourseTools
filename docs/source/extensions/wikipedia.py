# (C) Crown Copyright GCHQ
"""
Minor Sphinx extension for creating Wikipedia links, based on https://sphinx-toolbox.readthedocs.io/en/stable/extensions/wikipedia.html.

:wikipedia:`Cats` will create a link to /wiki/Cats with the text "Cats".
:wikipedia:`cat <Cats>` will create a link to /wiki/Cats with the text "cat".

Set ``wikipedia_base_url`` in ``conf.py`` to change the URL used. It must contain "{target}" to be populated.
It can also contain "{lang}" to allow the language code (e.g. "de") to be injected with the ``wikipedia_lang`` variable.
"""

from __future__ import annotations

import re
from urllib.parse import quote

from docutils import nodes
from docutils.nodes import system_message
from docutils.parsers.rst.states import Inliner
from sphinx.application import Sphinx
from sphinx.util.nodes import split_explicit_title

__all__ = ("make_wikipedia_link", "setup")

DEFAULT_BASE_URL = "https://{lang}.wikipedia.org/wiki/{target}"
RE_WIKI_LANG = re.compile(":(.*?):(.*)")


def make_wikipedia_link(
    name: str,
    rawtext: str,
    text: str,
    lineno: int,
    inliner: Inliner,
    options: dict[str, object] = {},
    content: list[str] = [],
) -> tuple[list[nodes.reference], list[system_message]]:
    """
    Add a link to the given article on :wikipedia:`Wikipedia`.

    :param name: The local name of the interpreted role, the role name actually used in the document.
    :param rawtext: A string containing the entire interpreted text input, including the role and markup.
    :param text: The interpreted text content.
    :param lineno: The line number where the interpreted text begins.
    :param inliner: The :class:`docutils.parsers.rst.states.Inliner` object that called ``source_role``.
                    It contains the several attributes useful for error reporting and document tree access.
    :param options: A dictionary of directive options for customization (from the ``role`` directive),
                    to be interpreted by the function. Used for additional attributes for the generated elements
                    and other functionality.
    :param content: A list of strings, the directive content for customization (from the ``role`` directive).
                    To be interpreted by the function.

    :return: A list containing the created node, and a list containing any messages generated during the function.
    """
    text = nodes.unescape(text)  # type: ignore[attr-defined]
    has_explicit, title, target = split_explicit_title(text)

    if match := RE_WIKI_LANG.match(target):
        lang, target = match.groups()
        if not has_explicit:
            title = target
    else:  # default language
        lang = inliner.document.settings.env.config.wikipedia_lang

    base_url: str = inliner.document.settings.env.config.wikipedia_base_url
    ref = base_url.format(lang=lang, target=quote(target.replace(" ", "_"), safe="#"))

    node = nodes.reference(rawtext, title, refuri=str(ref), **options)
    return [node], []


def setup(app: Sphinx) -> dict[str, object]:
    """
    Attach the extension to the application.

    :param app: The Sphinx application.
    """
    app.add_role("wikipedia", make_wikipedia_link)
    app.add_config_value("wikipedia_base_url", DEFAULT_BASE_URL, "env", [str])
    app.add_config_value("wikipedia_lang", "en", "env", [str])

    return {"parallel_read_safe": True}
