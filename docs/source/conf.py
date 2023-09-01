# (C) Crown Copyright GCHQ
"""
Configuration file for the Sphinx documentation builder.

This file only contains a selection of the most common options.
For a full list see the documentation: https://www.sphinx-doc.org/en/master/usage/configuration.html.
"""
# -- Path setup --------------------------------------------------------------

import pathlib
import sys
from typing import Optional, cast

from bs4 import BeautifulSoup
from bs4.element import Tag
from sphinx.application import Sphinx
import sphinx.config

CONF_FILE_PATH = pathlib.Path(__file__).absolute()
SOURCE_FOLDER_PATH = CONF_FILE_PATH.parent
DOCS_FOLDER_PATH = SOURCE_FOLDER_PATH.parent
REPO_FOLDER_PATH = DOCS_FOLDER_PATH.parent

sys.path.extend([str(DOCS_FOLDER_PATH), str(SOURCE_FOLDER_PATH), str(REPO_FOLDER_PATH)])


import concoursetools
import concoursetools.additional
import concoursetools.resource
import concoursetools.typing
import concoursetools.version

# -- Project information -----------------------------------------------------

project = "Concourse Tools"
copyright = "UK Crown"
version = "v" + concoursetools.__version__


# -- General configuration ---------------------------------------------------

extensions = [
    "sphinx.ext.autodoc",
    "sphinx.ext.autosectionlabel",
    "sphinx.ext.intersphinx",
    "sphinx_autodoc_typehints",
    "sphinx.ext.viewcode",
    "extensions.concourse",
    "extensions.wikipedia",
    "extensions.xkcd",
]

always_document_param_types = True
autodoc_member_order = "bysource"

autodoc_custom_types = {
    concoursetools.typing.MultiVersionT: ":class:`~concoursetools.additional.MultiVersion`",
    concoursetools.typing.VersionT: ":class:`~concoursetools.version.Version`",
    concoursetools.typing.SortableVersionT: ":class:`~concoursetools.version.Version`",
}


def typehints_formatter(annotation, config: sphinx.config.Config) -> Optional[str]:
    """Properly replace custom type aliases."""
    return autodoc_custom_types.get(annotation)


nitpicky = True
nitpick_ignore = [
    ("py:class", "concoursetools.additional._PseudoConcourseResource"),
    ("py:class", "concoursetools.typing.SortableVersionT"),
]

linkcheck_anchors_ignore_for_url = [
    "https://github.com/.*",
]

intersphinx_mapping = {
    "python3": ("https://docs.python.org/3", None),
    "requests": ("https://requests.readthedocs.io/en/latest/", None),
}

html_theme = "furo"
html_favicon = "_static/favicon.png"

html_static_path = ["_static"]

html_css_files = [
    "style.css",
    "https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/fontawesome.min.css",
    "https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/solid.min.css",
    "https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/brands.min.css",
]

html_theme_options = {
    "light_logo": "logo.png",
    "dark_logo": "logo-dark.png",
    "sidebar_hide_name": True,
    "footer_icons": [
        {
            "name": "GitHub",
            "url": "https://github.com/gchq/ConcourseTools",
            "class": "fa-brands fa-github fa-2x",
        },
        {
            "name": "PyPI",
            "url": "https://pypi.org/project/concoursetools/",
            "class": "fa-brands fa-python fa-2x",
        }
    ],
}


def reduce_method_names(app: Sphinx, exception: Optional[Exception]) -> None:
    """Remove class prefixes from method names in table of contents."""
    built_files_dir = pathlib.Path(app.outdir)
    for html_file in built_files_dir.glob("*.html"):
        soup = BeautifulSoup(html_file.read_text(), features="html.parser")
        toc = soup.find("div", {"class": "toc-tree"}) or soup.find("div", {"class": "toctree-wrapper"})
        if toc is None:
            continue
        toc = cast(Tag, toc)
        for span in toc.find_all("span", {"class": "pre"}):
            span = cast(Tag, span)
            *_, new_text = span.text.split(".")
            span.string = new_text
        html_file.write_text(str(soup))


def setup(app: Sphinx) -> None:
    app.connect("build-finished", reduce_method_names)
