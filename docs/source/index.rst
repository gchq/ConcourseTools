Concourse Tools (|version|)
===========================

.. admonition:: Description

   A Python package for easily implementing Concourse :concourse:`resource types <implementing-resource-types>`, created by GCHQ.



Bugs and Contributions
----------------------
Contributions, fixes, suggestions and bug reports are all welcome: please see the `guidance <https://github.com/gchq/ConcourseTools/blob/main/CONTRIBUTING.md>`_.


Examples
--------

Examples are available which showcase the variety of resources made possible with Concourse Tools:

.. list-table::
    :header-rows: 1
    :align: left

    * - Resource
      - Examples
    * - :class:`~concoursetools.resource.ConcourseResource`
      - :ref:`AWS SageMaker Pipeline`
    * - :class:`~concoursetools.additional.OutOnlyConcourseResource`
      - :ref:`Bitbucket Build Status`
    * - :class:`~concoursetools.additional.SelfOrganisingConcourseResource`
      - :ref:`XKCD Comics`
    * - :class:`~concoursetools.additional.TriggerOnChangeConcourseResource`
      - :ref:`AWS Secrets`
    * - :class:`~concoursetools.additional.InOnlyConcourseResource`
      - :ref:`S3 Presigned URL`
    * - :class:`~concoursetools.additional.MultiVersionConcourseResource`
      - :ref:`GitHub Branches`

Contents
--------

.. toctree::
    :maxdepth: 2

    quickstart
    api_reference
    cli_reference
    debugging
    testing
    deployment
    internals

.. toctree::
    :caption: Examples
    :hidden:

    examples/pipeline
    examples/build_status
    examples/xkcd
    examples/secrets
    examples/s3
    examples/branches

Indices and Tables
------------------

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`
