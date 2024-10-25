Quickstart
==========

Creating a Concourse resource type with Concourse Tools couldn't be simpler.
To begin, install **Concourse Tools** from source or from PyPI (see the footer for links).

.. code:: shell

    $ pip install concoursetools

Start by familiarising yourself with the Concourse resource "rules" in the
:concourse:`documentation <implementing-resource-types>`. To recreate that example, start by creating a new
``concourse.py`` file in your repository. The first step is to create a :class:`~concoursetools.version.Version` subclass:


.. code:: python

    from dataclasses import dataclass
    from concoursetools import TypedVersion


    @dataclass()
    class GitVersion(TypedVersion):
        ref: str


Next, create a subclass of :class:`~concoursetools.resource.ConcourseResource`:

.. code:: python

    from concoursetools import ConcourseResource


    class GitResource(ConcourseResource[GitVersion]):

        def __init__(self, uri: str, branch: str, private_key: str) -> None:
            super().__init__(GitVersion)
            self.uri = uri
            self.branch = branch
            self.private_key = private_key


Here, the parameters in the ``__init__`` method will be taken from the ``source`` configuration for the resource.
Now, implement the three methods required to define the behaviour of the resource:


.. code:: python

    from pathlib import Path
    from typing import Any
    from concoursetools import BuildMetadata


    class GitResource(ConcourseResource[GitVersion]):
        ...

        def fetch_new_versions(self, previous_version: GitVersion | None) -> list[GitVersion]:
            ...

        def download_version(self, version: GitVersion, destination_dir: pathlib.Path,
                            build_metadata: BuildMetadata, **kwargs: Any) -> tuple[GitVersion, dict[str, str]]:
            ...

        def publish_new_version(self, sources_dir: pathlib.Path, build_metadata: BuildMetadata,
                                **kwargs: Any) -> tuple[GitVersion, dict[str, str]]:
            ...


The keyword arguments in :meth:`~concoursetools.resource.ConcourseResource.download_version`
and :meth:`~concoursetools.resource.ConcourseResource.publish_new_version` correspond to ``params`` in the ``get`` step,
and ``get_params`` in the ``put`` step respectively.

Once you are happy with the resource, freeze your requirements into a ``requirements.txt`` file,
then generate the ``Dockerfile`` using the Concourse Tools CLI:

.. code:: shell

    $ python3 -m concoursetools dockerfile .


Finally, upload the Docker image to a registry, and use it in your pipelines!


.. tip::
    Check out the :ref:`Examples` section for different ways to leverage Concourse Tools for your use case.
