Testing the Resource
=====================

.. automodule:: concoursetools.testing


Using Test Wrappers
-------------------

Multiple test wrappers are available:

.. list-table::
    :header-rows: 1
    :align: left

    * - Test Class
      - Input / Output
      - Executed As
    * - :class:`~concoursetools.testing.SimpleTestResourceWrapper`
      - Python
      - Resource class
    * - :class:`~concoursetools.testing.JSONTestResourceWrapper`
      - JSON
      - Main scripts
    * - :class:`~concoursetools.testing.ConversionTestResourceWrapper`
      - Python
      - Main scripts
    * - :class:`~concoursetools.testing.FileTestResourceWrapper`
      - JSON
      - External scripts
    * - :class:`~concoursetools.testing.FileConversionTestResourceWrapper`
      - Python
      - External scripts

Base Wrapper
------------

All of the above inherit from :class:`~concoursetools.testing.TestResourceWrapper`:

.. autoclass:: concoursetools.testing.TestResourceWrapper
    :members:

.. toctree::
    mocking
    wrappers
