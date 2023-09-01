Main Scripts
============
When scripts are eventually generated for your resource class, each step corresponds to a function call which encapsulates all logic. All of the following functions accept no arguments, instead extracting parameters directly from the command line, ``stdin``, and environment variables. They will print to ``stdout`` and ``stderr``, and do not return anything.

Although each method can *technically* be overloaded, this is **not** recommended as all of the resource logic is contained in the standard methods, and this will just add complications.

.. automethod:: concoursetools.resource.ConcourseResource.check_main

.. automethod:: concoursetools.resource.ConcourseResource.in_main

.. automethod:: concoursetools.resource.ConcourseResource.out_main
