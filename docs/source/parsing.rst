Parsing
=======

.. automodule:: concoursetools.parsing


JSON Parsing
------------

The following functions are responsible for parsing Concourse JSON payloads and returning Python objects.

.. autofunction:: concoursetools.parsing.parse_check_payload

.. autofunction:: concoursetools.parsing.parse_in_payload

.. autofunction:: concoursetools.parsing.parse_out_payload

.. autofunction:: concoursetools.parsing.parse_metadata


JSON Formatting
---------------

The following functions are responsible for formatting Concourse JSON payloads from Python objects.

.. autofunction:: concoursetools.parsing.format_check_output

.. autofunction:: concoursetools.parsing.format_in_out_output

.. autofunction:: concoursetools.parsing.format_metadata
