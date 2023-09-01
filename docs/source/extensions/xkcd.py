# (C) Crown Copyright GCHQ
"""
Minor Sphinx extension for embedding xkcd comics, based on https://sphinx-toolbox.readthedocs.io/en/stable/extensions/wikipedia.html.

You can embed a particular comic with the following directive:

.. xkcd:: <num>

In addition:

:wikipedia:`path/to/page.html` will create a link to that page on the xkcd website.

Set ``xkcd_endpoint`` in ``conf.py`` to change the URL used.
"""
from typing import Any, Dict, List, Tuple

from docutils import nodes
from docutils.parsers.rst import directives
from docutils.parsers.rst.roles import set_classes
from docutils.parsers.rst.states import Inliner
import requests
from sphinx.application import Sphinx
from sphinx.environment import BuildEnvironment
from sphinx.util import logging
from sphinx.util.docutils import SphinxDirective
from sphinx.util.nodes import split_explicit_title

DEFAULT_XKCD = "https://xkcd.com"


class XkcdDirective(SphinxDirective):
    """
    Directive for xkcd comics.
    """
    required_arguments = 1  # The comic number
    option_spec = {
        "height": directives.length_or_unitless,
        "width": directives.length_or_percentage_or_unitless,
        "scale": directives.percentage,
        "class": directives.class_option,
        "caption": directives.unchanged,
    }

    @property
    def config(self) -> BuildEnvironment:
        """Return the config environment."""
        return self.state.document.settings.env.config  # type: ignore[no-any-return]

    def run(self) -> List[nodes.Node]:
        """
        Process the content of the shield directive.
        """
        comic_number, = self.arguments
        comic_info = self.get_comic_info(int(comic_number), self.config["xkcd_endpoint"])

        caption = self.options.pop("caption", "Relevant xkcd")

        set_classes(self.options)
        image_node = nodes.image(self.block_text, uri=directives.uri(comic_info["img"]),
                                 alt=comic_info["alt"], **self.options)
        self.add_name(image_node)

        reference_node = nodes.reference("", "", refuri=comic_info["link"])
        reference_node += image_node

        caption_node = nodes.caption("", caption)

        figure_node = nodes.figure()
        figure_node += reference_node
        figure_node += caption_node
        return [figure_node]

    def get_comic_info(self, comic_number: int, endpoint: str = DEFAULT_XKCD) -> Dict[str, Any]:
        comic_link = f"{endpoint}/{comic_number}/"
        try:
            response = requests.get(f"{endpoint}/{comic_number}/info.0.json")
            response.raise_for_status()
        except requests.ConnectionError:
            logger = logging.getLogger(__name__)
            logger.warning("Could not connect to xkcd endpoint")
            response_json: Dict[str, Any] = {
                "img": comic_link,
                "alt": comic_link,
            }
        except requests.HTTPError:
            latest_response = requests.get(f"{endpoint}/info.0.json")
            latest_json: Dict[str, Any] = latest_response.json()
            most_recent_comic = latest_json["num"]
            if most_recent_comic < comic_number:
                raise ValueError(f"You asked for xkcd #{comic_number}, but the most recent available comic is #{most_recent_comic}")
            else:
                raise
        else:
            response_json = response.json()
        response_json["link"] = comic_link
        return response_json


def make_xkcd_link(name: str, rawtext: str, text: str, lineno: int, inliner: Inliner,
                   options: Dict[str, Any] = {}, content: List[str] = []) -> Tuple[List[nodes.reference], List[nodes.system_message]]:
    """
    Add a link to a page on the xkcd website.

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

    endpoint: str = inliner.document.settings.env.config.xkcd_endpoint  # type: ignore
    ref = f"{endpoint}/{target}"

    node = nodes.reference(rawtext, title, refuri=str(ref), **options)
    return [node], []


def setup(app: Sphinx) -> Dict[str, Any]:
    """
    Attach the extension to the application.

    :param app: The Sphinx application.
    """
    app.add_directive("xkcd", XkcdDirective)
    app.add_role("xkcd", make_xkcd_link)
    app.add_config_value("xkcd_endpoint", DEFAULT_XKCD, "env", [str])
    return {"parallel_read_safe": True}
