Printing/Debugging
==================

A Concourse resource is supposed to print output (such as versions and metadata) to ``stdout``, and all debugging messages to ``stderr``. The :class:`~concoursetools.resource.ConcourseResource` class automatically redirects ``stdout`` to ``stderr`` when running its methods, meaning that all printed output from you (and from your dependencies) automatically ends up in ``stderr``.

Colour
------

.. automodule:: concoursetools.colour
    :members:
    :exclude-members: Colour

Available Colours
_________________

All ``colour`` arguments are :wikipedia:`ANSI colour escape codes <ANSI_escape_code#Colors>`, but a number of common codes are available as attributes of the :class:`~concoursetools.colour.Colour` class:

.. autoclass:: concoursetools.colour.Colour
    :members:
    :undoc-members:
