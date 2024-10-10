Quickstart
==========

Creating a Concourse resource type with Concourse Tools couldn't be simpler:

1. Install **Concourse Tools** from source or from PyPI (see the footer for links).
2. Create subclasses of :class:`~concoursetools.version.Version` and :class:`~concoursetools.resource.ConcourseResource`, taking care to implement any required functions.
3. Create a :ref:`Dockerfile <Dockerfile Structure>` containing your requirements and calling your resource.
4. Upload the Docker image to a registry, and use it in your pipelines!

.. tip::
    Check out the :ref:`Examples` section for different ways to leverage Concourse Tools for your use case.
