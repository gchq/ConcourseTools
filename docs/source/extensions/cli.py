# (C) Crown Copyright GCHQ
"""
Sphinx extension for documenting the custom CLI.
"""
from __future__ import annotations

from typing import Literal

from docutils import nodes
from docutils.parsers.rst import directives
from sphinx.application import Sphinx
from sphinx.ext.autodoc import import_object
from sphinx.util.docutils import SphinxDirective

from concoursetools.cli.parser import CLI


def _align_directive(argument: str) -> str:
    return directives.choice(argument, ("left", "center", "right"))


class CLIDirective(SphinxDirective):
    """
    Directive for listing CLI commands in a table.
    """
    required_arguments = 1  # The import path of the CLI
    option_spec = {
        "align": _align_directive,
    }

    def run(self) -> list[nodes.Node]:
        """
        Process the content of the shield directive.
        """
        align: Literal["left", "center", "right"] | None = self.options.get("align")

        headers = [nodes.entry("", nodes.paragraph("", header)) for header in ["Command", "Description"]]

        import_string, = self.arguments
        cli = self.import_cli(import_string)

        rows: list[list[nodes.entry]] = []

        for command_name, command in cli.commands.items():
            rows.append([
                nodes.entry("", nodes.paragraph("", "", nodes.reference("", "", nodes.literal("", command_name), refid=f"cli.{command_name}"))),
                nodes.entry("", nodes.paragraph("", command.description or "")),
            ])

        table = self.create_table(headers, rows, align=align)

        nodes_to_return: list[nodes.Node] = [table]

        for command_name, command in cli.commands.items():
            command_section = nodes.section(ids=[f"cli.{command_name}"])
            title = nodes.title(f"cli.{command_name}", "", nodes.literal("", command_name))
            command_section.append(title)

            if command.description is not None:
                command_section.append(nodes.paragraph("", command.description))

            usage_block = nodes.literal_block("", f"$ {command.usage_string()}")
            command_section.append(usage_block)

            for positional in command.positional_arguments:
                alias_paragraph = nodes.paragraph("", "", nodes.literal("", positional.name))
                description_paragraph = nodes.paragraph("", positional.description or "")
                description_paragraph.set_class("cli-option-description")
                command_section.extend([alias_paragraph, description_paragraph])

            for option in command.options:
                alias_nodes: list[nodes.Node] = []
                for alias in option.aliases:
                    alias_nodes.append(nodes.literal("", alias))
                    alias_nodes.append(nodes.Text(", "))
                alias_paragraph = nodes.paragraph("", "", *alias_nodes[:-1])
                description_paragraph = nodes.paragraph("", option.description or "")
                description_paragraph.set_class("cli-option-description")
                command_section.extend([alias_paragraph, description_paragraph])

            nodes_to_return.append(command_section)

        return nodes_to_return

    def create_table(self, headers: list[nodes.entry], rows: list[list[nodes.entry]],
                     align: Literal["left", "center", "right"] | None = None) -> nodes.table:
        table = nodes.table()
        if align is not None:
            table["align"] = align

        table_group = nodes.tgroup(cols=len(headers))
        table_group.extend([nodes.colspec()] * len(headers))

        table.append(table_group)

        header = nodes.thead()
        header_row = nodes.row()
        header_row.extend(headers)
        header.append(header_row)
        table_group.append(header)

        body = nodes.tbody()
        for row in rows:
            body_row = nodes.row()
            body_row.extend(row)
            body.append(body_row)

        table_group.append(body)
        return table

    def import_cli(self, import_string: str) -> CLI:
        *module_components, import_object_name = import_string.split(".")
        import_path = ".".join(module_components)

        import_result = import_object(import_path, [import_object_name])
        cli: CLI = import_result[-1]
        return cli


def setup(app: Sphinx) -> dict[str, object]:
    """
    Attach the extension to the application.

    :param app: The Sphinx application.
    """
    app.add_directive("cli", CLIDirective)
    return {"parallel_read_safe": True}
