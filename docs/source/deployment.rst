Deploying the Resource Type
===========================

To properly "deploy" the resource type, your repo should look something like this:

.. code:: none

    .
    |-- Dockerfile
    |-- README.md
    |-- assets
    |   |-- check
    |   |-- in
    |   |-- out
    |-- requirements.txt
    |-- concourse.py
    |-- tests.py


Resource Module
---------------

The ``concourse.py`` module contains your :class:`~concoursetools.version.Version` and
:class:`~concoursetools.resource.ConcourseResource` subclasses. It can be called whatever you like, but ``concourse.py``
is the most clear, and is the default for the CLI.

.. note::

    It is possible to split your code into multiple modules, or even packages. This is sometimes useful if you have
    written a lot of code, or if it naturally splits. However, make sure that this code is also put in the correct place
    in your :ref:`Docker image <Dockerfile Structure>`.


Requirements
------------

The ``requirements.txt`` file should contain a complete list of requirements within your virtual environment (version
pinned) sufficient to reproduce with

.. code:: shell

    $ pip install -r requirements.txt --no-deps

If this is not possible, then rewrite your requirements file. If you have any dependencies which are not public, then
you will have to make some adjustments to your :ref:`Dockerfile <Including Certs in your Docker Build>`.


Assets
------

The contents of each of the files in ``assets`` follow the same pattern. For example, here is the contents of
``assets/check``:

.. code:: python3

    #!/usr/bin/env python3
    """
    Check for new versions of the resource.
    """
    from concourse import MyResource


    if __name__ == "__main__":
        MyResource.check_main()

It is these files which get called by Concourse as part of the resource. Note that none of the asset files have any
extensions, but specific their executable at the top of the file. ``MyResource`` should correspond to your
:class:`~concoursetools.resource.ConcourseResource` subclass, and ``resource`` to the :ref:`module in which you have
placed it <Resource module>`. Replace :meth:`~concoursetools.resource.ConcourseResource.check_main` with
:meth:`~concoursetools.resource.ConcourseResource.in_main` and
:meth:`~concoursetools.resource.ConcourseResource.out_main` for ``assets/in`` and ``assets/out`` respectively.

.. important::

    Every file in assets need to be executable. This can be done with

    .. code:: shell

        $ chmod +x assets/*

.. tip::

    Because this pattern is suitable for almost every resource type, you can automate the creation of the ``assets``
    folder with the :ref:`cli.assets` CLI command.


Dockerfile Structure
--------------------

The Dockerfile should look something like:

.. code-block:: Dockerfile
    :linenos:

    FROM python:3.12

    RUN python3 -m venv /opt/venv
    # Activate venv
    ENV PATH="/opt/venv/bin:$PATH"

    COPY requirements.txt requirements.txt

    RUN \
        python3 -m pip install --upgrade pip && \
        pip install -r requirements.txt --no-deps

    WORKDIR /opt/resource/
    COPY concourse.py ./concourse.py
    RUN python3 -m concoursetools . -r concourse.py

    ENTRYPOINT ["python3"]

.. tip::

    You can automate the creation of this file with the :ref:`cli.dockerfile` CLI command.


Base Image
__________

.. code-block:: Dockerfile
    :linenos:

    FROM python:3.12

You should adjust the base image according to your requirements. Concourse Tools will default to ``python:<version>``,
where ``<version>`` corresponds to the current major/minor version you are running. However, you may wish to specify
a different base image, such as ``python:3.*-slim`` or ``python:3.*-alpine``.


Virtual Environment
___________________

.. code-block:: Dockerfile
    :linenos:
    :lineno-start: 3

    RUN python3 -m venv /opt/venv
    # Activate venv
    ENV PATH="/opt/venv/bin:$PATH"

There is much debate as to whether or not it is worth creating a virtual environment within a Docker container.
Concourse Tools chooses to create one by default in order to maximise the similarity between code running on the image
and code running locally.


Installing Requirements
_______________________

.. code-block:: Dockerfile
    :linenos:
    :lineno-start: 7

    COPY requirements.txt requirements.txt

    RUN \
        python3 -m pip install --upgrade pip && \
        pip install -r requirements.txt --no-deps

By default, Concourse Tools will copy over the ``requirements.txt`` file to use for the resource dependencies.
The installation process is a single command involving two parts:

1. Updating ``pip`` to ensure the latest available version at build time,
2. Installing the static requirements file *without implicit dependencies*.

If these were two separate commands then Docker would cache the first one and ``pip`` would never be upgraded.

.. note::
    By passing ``--no-deps`` we ensure that the ``requirements.txt`` file is fully complete, and we are not missing
    any implicit dependencies.


Including Certs in your Docker Build
____________________________________

.. versionadded:: 0.8
    In previous versions the advice was to use multi-stage builds for this. Although that practice is equally
    secure, it makes sense to use `Docker secrets <https://docs.docker.com/build/building/secrets/>`_ instead.

If any of your requirements are private then you will need to make your private keys available to the image during the
build process, **without** storing them within the image itself. This can be done by making the following change to the
``RUN`` command from previous section:

.. code-block:: Dockerfile
    :linenos:
    :lineno-start: 7

    COPY requirements.txt requirements.txt

    RUN \
        --mount=type=secret,id=private_key,target=/root/.ssh/id_rsa,mode=0600,required=true \
        --mount=type=secret,id=known_hosts,target=/root/.ssh/known_hosts,mode=0644 \
        python3 -m pip install --upgrade pip && \
        pip install -r requirements.txt --no-deps

The secrets must then be passed at build time:

.. code:: shell

    $ docker build \
        --secret id=private_key,src=~/.ssh/id_rsa \
        --secret id=known_hosts,src=~/.ssh/known_hosts \
        .

The files are then mounted securely using the `correct permissions
<https://superuser.com/questions/215504/permissions-on-private-key-in-ssh-folder>`_.

.. tip::

    You can easily generate this skeleton with the :ref:`cli.dockerfile` CLI command:

    .. code:: shell

        $ python3 -m concoursetools docker . --include-rsa


Creating Asset Files
____________________

.. code-block:: Dockerfile
    :linenos:
    :lineno-start: 13

    WORKDIR /opt/resource/
    COPY concourse.py ./concourse.py
    RUN python3 -m concoursetools . -r concourse.py

Concourse requires that your asset files are placed in ``/opt/resource`` on the container, which is done here using
the Concourse Tools CLI to reduce the required code.

.. warning::
    If you **cannot** use the CLI to create your :ref:`assets <Assets>` folder, then you should manually copy your asset
    files across to ``/opt/resource``.

If your resource requires additional modules to work, then you need to ensure they are also copied across **before**
the CLI is invoked:

.. code-block:: Dockerfile
    :linenos:
    :lineno-start: 13

    WORKDIR /opt/resource/
    COPY concourse.py ./concourse.py
    COPY extra.py ./extra.py
    RUN python3 -m concoursetools . -r concourse.py


Entry Point
___________

.. code-block:: Dockerfile
    :linenos:
    :lineno-start: 17

    ENTRYPOINT ["python3"]

Finally, we specify an ``ENTRYPOINT`` for the container. This has little bearing on the resource itself as Concourse
will specify the scripts it wishes to invoke via the shebang in the scripts. It isn't even used when hijacking the
container (the default is bash). However, it is best practice to set something, and this should make it easiest to
debug locally.


Dockertools Reference
---------------------

.. automodule:: concoursetools.dockertools
    :members:
