# (C) Crown Copyright GCHQ
"""
Configuration file for the Sphinx documentation builder.

This file only contains a selection of the most common options.
For a full list see the documentation: https://www.sphinx-doc.org/en/master/usage/configuration.html.
"""
# -- Path setup --------------------------------------------------------------

from collections.abc import Callable
from pathlib import Path
import sys
from typing import Any

import sphinx.config
from sphinx_autodoc_typehints import format_annotation

CONF_FILE_PATH = Path(__file__).absolute()
SOURCE_FOLDER_PATH = CONF_FILE_PATH.parent
DOCS_FOLDER_PATH = SOURCE_FOLDER_PATH.parent
REPO_FOLDER_PATH = DOCS_FOLDER_PATH.parent

sys.path.extend([str(DOCS_FOLDER_PATH), str(SOURCE_FOLDER_PATH), str(REPO_FOLDER_PATH)])


import concoursetools
import concoursetools.additional
import concoursetools.cli.parser
import concoursetools.importing
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
    "extensions.cli",
    "extensions.concourse",
    "extensions.linecount",
    "extensions.wikipedia",
    "extensions.xkcd",
]

toc_object_entries_show_parents = "hide"  # don't show prefix in secondary TOC

always_document_param_types = True
autodoc_member_order = "bysource"

autodoc_custom_types = {
    concoursetools.cli.parser.CLIFunctionT: format_annotation(Callable[..., None], sphinx.config.Config()),
    concoursetools.importing.T: ":class:`object`",
    concoursetools.typing.VersionT: ":class:`~concoursetools.version.Version`",
    concoursetools.typing.SortableVersionT: ":class:`~concoursetools.version.Version`",
}

suppress_warnings = ["config.cache"]  # https://github.com/sphinx-doc/sphinx/issues/12300#issuecomment-2062238457


def typehints_formatter(annotation: Any, config: sphinx.config.Config) -> str | None:
    """Properly replace custom type aliases."""
    return autodoc_custom_types.get(annotation)


nitpicky = True
nitpick_ignore = [
    ("py:class", "concoursetools.additional._PseudoConcourseResource"),
    ("py:class", "concoursetools.typing.SortableVersionT"),
]

linkcheck_report_timeouts_as_broken = False  # silences a warning: https://github.com/sphinx-doc/sphinx/issues/11868
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
    "source_repository": "https://github.com/gchq/ConcourseTools/",
    "source_branch": "main",
    "source_directory": "docs/source/",
    "footer_icons": [
        {
            "name": "GitHub",
            "url": "https://github.com/gchq/ConcourseTools/",
            "class": "fa-brands fa-github fa-2x",
        },
        {
            "name": "PyPI",
            "url": "https://pypi.org/project/concoursetools/",
            "class": "fa-brands fa-python fa-2x",
        }
    ],
}
