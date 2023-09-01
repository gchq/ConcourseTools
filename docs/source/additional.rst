Additional Patterns
===================

.. automodule:: concoursetools.additional

.. autoclass:: concoursetools.additional.OutOnlyConcourseResource
    :members: publish_new_version

.. autoclass:: concoursetools.additional.InOnlyConcourseResource
    :members: download_data

.. autoclass:: concoursetools.additional.TriggerOnChangeConcourseResource
    :members: fetch_latest_version

.. autoclass:: concoursetools.additional.MultiVersionConcourseResource
    :members: fetch_latest_sub_versions, download_version
    :show-inheritance:

.. autoclass:: concoursetools.additional.SelfOrganisingConcourseResource
    :members: fetch_all_versions


Combining Resource Types
------------------------

Occasionally you may wish to implement multiple resource types with the same set of dependencies. Although it is often cleaner to treat these separately and :ref:`build separate Docker images <Deploying the Resource Type>`, there are times where it is easier to build a single image containing all of your resource types, and to select one of them via the resource config. To do this, you can use the :func:`~concoursetools.additional.combine_resource_types` function:

.. autofunction:: concoursetools.additional.combine_resource_types
