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

The ``concourse.py`` module contains your :class:`~concoursetools.version.Version` and :class:`~concoursetools.resource.ConcourseResource` subclasses. It can be called whatever you like, but ``concourse.py`` is the most clear, and is the default for the CLI.

.. note::

    It is possible to split your code into multiple modules, or even packages. This is sometimes useful if you have written a lot of code, or if it naturally splits. However, make sure that this code is also put in the correct place in your :ref:`Docker image <Dockerfile>`.


Requirements
------------

The ``requirements.txt`` file should contain a complete list of requirements within your virtual environment (version pinned) sufficient to reproduce with

.. code:: shell

    $ pip install -r requirements.txt --no-deps

If this is not possible, then rewrite your requirements file. If you have any dependencies which are not public, then you will have to make some adjustments to your :ref:`Dockerfile <Including Certs in your Docker Build>`.


Assets
------

The contents of each of the files in ``assets`` follow the same pattern. For example, here is the contents of ``assets/check``:

.. code:: python3

    #!/usr/bin/env python3
    """
    Check for new versions of the resource.
    """
    from concourse import MyResource


    if __name__ == "__main__":
        MyResource.check_main()

It is these files which get called by Concourse as part of the resource. Note that none of the asset files have any extensions, but specific their executable at the top of the file. ``MyResource`` should correspond to your :class:`~concoursetools.resource.ConcourseResource` subclass, and ``resource`` to the :ref:`module in which you have placed it <Resource module>`. Replace :meth:`~concoursetools.resource.ConcourseResource.check_main` with :meth:`~concoursetools.resource.ConcourseResource.in_main` and :meth:`~concoursetools.resource.ConcourseResource.out_main` for ``assets/in`` and ``assets/out`` respectively.

.. important::

    Every file in assets need to be executable. This can be done with

    .. code:: shell

        $ chmod +x assets/*

.. tip::

    Because this pattern is suitable for almost every resource type, you can automate the creation of the ``assets``
    folder with the :ref:`cli.assets` CLI command.

Dockerfile
----------

The Dockerfile should look something like:

.. code:: Dockerfile

    FROM python:3.9

    COPY requirements.txt requirements.txt

    RUN python3 -m pip install --upgrade pip && \
        pip install -r requirements.txt --no-deps

    WORKDIR /opt/resource/
    COPY concourse.py ./concourse.py
    RUN python3 -m concoursetools assets . -r concourse.py

    ENTRYPOINT ["python3"]

You should adjust the base image according to your requirements. If you **cannot** use the CLI to create your :ref:`assets <Assets>` folder, then you should manually copy your asset files across to ``/opt/resource``.

.. tip::

    You can automate the creation of this file with the :ref:`cli.dockerfile` CLI command.


Including Certs in your Docker Build
____________________________________

If any of your requirements are private (Concourse Tools is not a public project, and so you are probably putting a git clone path in your :ref:`Requirements` file), then you should build your Docker image in `two stages <https://docs.docker.com/build/building/multi-stage/>`_, keeping your keys out of the final image which gets pushed to your Docker registry:

.. code:: Dockerfile

    FROM python:3.9 as builder

    RUN apk update --no-progress && apk add openssh-client && apk add --no-cache --no-progress git

    ARG ssh_known_hosts
    ARG ssh_private_key

    RUN mkdir -p /root/.ssh && chmod 0700 /root/.ssh
    RUN echo "$ssh_known_hosts" > /root/.ssh/known_hosts && chmod 600 /root/.ssh/known_hosts
    RUN echo "$ssh_private_key" > /root/.ssh/id_rsa && chmod 600 /root/.ssh/id_rsa

    COPY requirements.txt requirements.txt

    RUN python3 -m venv /opt/venv
    # Activate venv
    ENV PATH="/opt/venv/bin:$PATH"

    RUN python3 -m pip install --upgrade pip && \
        pip install -r requirements.txt --no-deps


    FROM python:3.9-slim as runner
    COPY --from=builder /opt/venv /opt/venv
    # Activate venv
    ENV PATH="/opt/venv/bin:$PATH"

    WORKDIR /opt/resource/
    COPY concourse.py ./concourse.py
    RUN python3 -m concoursetools assets . -r concourse.py

    ENTRYPOINT ["python3"]

You can then pass the contents of your SSH private key and ``known_hosts`` file to the builder image, but **not** the final image:

.. code:: shell

    $ docker build --build-arg ssh_private_key="$(cat ~/.ssh/id_rsa)" --build-arg ssh_known_hosts="$(cat ~/.ssh/known_hosts)" . -t <repo>:<tag>

.. note::

    The reason we don't just mount ``.ssh`` or similar is to make this pattern as reusable as possible, since you may need to pass arbitrary certs.

The Python :mod:`venv` module is necessary to easily copy the installed requirements to the new image.

.. tip::

    You can easily generate this skeleton with the :ref:`cli.dockerfile` CLI command:

    .. code:: shell

        $ python3 -m concoursetools dockerfile . --include-rsa

Dockertools Reference
---------------------

.. automodule:: concoursetools.dockertools
    :members:
