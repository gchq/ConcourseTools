Version
=======

.. automodule:: concoursetools.version

Version Parent Class
--------------------

.. autoclass:: concoursetools.version.Version
    :members:


Typed Version Class
-------------------

.. autoclass:: concoursetools.version.TypedVersion
    :members: flatten, un_flatten

Supported Types
_______________

Concourse Tools has out-of-the-box support for a few common types:

* :class:`~datetime.datetime`: The datetime object is mapped to an integer timestamp.
* :class:`bool`: The boolean is mapped to the strings ``"True"`` or ``"False"``.
* :class:`~enum.Enum`: Enums are mapped to their *names*, so ``MyEnum.ONE`` maps to ``ONE``.
* :class:`~pathlib.Path`: Paths are mapped to their string representations.


Version Comparisons
-------------------

It is often beneficial to directly compare version within your code.

Hashing
_______

By default, every version is hashable, and this :func:`hash` is determined by the version class and the output of :meth:`~concoursetools.version.Version.to_flat_dict`. Key/value pairs are sorted and then hashed as a :class:`tuple`, which is combined with the hash of the class.

Equality
________

By default, two versions are equal if they have the same :func:`hash`. However, you may wish to overload this. For example, consider the following version class:

.. code:: python3

    class GitBranch(Version):

        def __init__(self, branch_name: str):
            self.branch_name = branch_name

Under the default behaviour, ``GitBranch("main")`` and ``GitBranch("origin/main")`` will be not be considered equal, but this might not be ideal. The fastest way to fix this is to overload :meth:`~object.__eq__` like so:

.. code:: python3

    class GitBranch(Version):

        def __init__(self, branch_name: str):
            self.branch_name = branch_name

        def __eq__(self, other):
            return self.branch_name.split("/")[-1] == other.branch_name.split("/")[-1]


Ordering
________

Sometimes you need to order versions to simplify your scripts (returning the latest version, etc.), but by default versions are **not** comparable in this way. This can be fixed by also inheriting from :class:`SortableVersionMixin`, which expects you to implement :meth:`~object.__lt__`. We want ``version_a <= version_b`` if and only if ``version_a`` is **no older** than ``version_b``.

.. autoclass:: concoursetools.version.SortableVersionMixin
    :members:


Multi Versions
--------------

.. autoclass:: concoursetools.additional.MultiVersion
    :members:
