Dockertools
===========

.. automodule:: concoursetools.dockertools
    :members: create_script_file


Dockerfile
----------
For easier dynamic creation of Dockerfiles, the module contains a number of
:class:`~concoursetools.dockertools.Instruction` classes:

.. autoclass:: concoursetools.dockertools.Instruction
    :members:


A :class:`~concoursetools.dockertools.Comment` class is also included:

.. autoclass:: concoursetools.dockertools.Comment
    :members:


All instructions and comments are added to a A :class:`~concoursetools.dockertools.Dockerfile` instance
in *instruction groups*:

.. autoclass:: concoursetools.dockertools.Dockerfile
    :members:


Dockerfile Instructions
-----------------------

All currently relevant instructions have been implemented:

.. list-table::
    :header-rows: 1
    :align: left

    * - Instruction
      - Description
      - Classes
    * - ``ADD``
      - Add local or remote files and directories.
      -
    * - ``ARG``
      - Use build-time variables.
      -
    * - ``CMD``
      - Specify default commands.
      -
    * - ``COPY``
      - Copy files and directories.
      - :class:`~concoursetools.dockertools.CopyInstruction`
    * - ``ENTRYPOINT``
      - Specify default executable.
      - :class:`~concoursetools.dockertools.EntryPointInstruction`
    * - ``ENV``
      - Set environment variables.
      - :class:`~concoursetools.dockertools.EnvInstruction`
    * - ``EXPOSE``
      - Describe which ports your application is listening on.
      -
    * - ``FROM``
      - Check a container's health on startup.
      - :class:`~concoursetools.dockertools.FromInstruction`
    * - ``HEALTHCHECK``
      - Check a container's health on startup.
      -
    * - ``LABEL``
      - Add metadata to an image.
      -
    * - ``MAINTAINER``
      - Specify the author of an image.
      -
    * - ``ONBUILD``
      - Specify instructions for when the image is used in a build.
      -
    * - ``RUN``
      - Execute build commands.
      - :class:`~concoursetools.dockertools.RunInstruction`, :class:`~concoursetools.dockertools.MultiLineRunInstruction`
    * - ``SHELL``
      - Set the default shell of an image.
      -
    * - ``STOPSIGNAL``
      - Specify the system call signal for exiting a container.
      -
    * - ``USER``
      - Set user and group ID.
      -
    * - ``VOLUME``
      - Create volume mounts.
      -
    * - ``WORKDIR``
      - Change working directory.
      - :class:`~concoursetools.dockertools.WorkDirInstruction`


.. autoclass:: concoursetools.dockertools.CopyInstruction
.. autoclass:: concoursetools.dockertools.EntryPointInstruction
.. autoclass:: concoursetools.dockertools.EnvInstruction
.. autoclass:: concoursetools.dockertools.FromInstruction
.. autoclass:: concoursetools.dockertools.RunInstruction
.. autoclass:: concoursetools.dockertools.MultiLineRunInstruction
.. autoclass:: concoursetools.dockertools.WorkDirInstruction


Dockerfile Mounts
-----------------

The module also implements some mounts for the ``RUN`` step to facilitate secrets:

.. autoclass:: concoursetools.dockertools.Mount
    :members:

All currently relevant mount types have been implemented:

.. list-table::
    :header-rows: 1
    :align: left

    * - Mount
      - Description
      - Classes
    * - ``bind``
      - Bind-mount context directories (read-only).
      -
    * - ``cache``
      - Mount a temporary directory to cache directories for compilers and package managers.
      -
    * - ``tmpfs``
      - Mount a ``tmpfs`` in the build container.
      -
    * - ``secret``
      - Allow the build container to access secure files such as private keys without baking them into the image or build cache.
      - :class:`~concoursetools.dockertools.SecretMount`
    * - ``ssh``
      - Allow the build container to access SSH keys via SSH agents, with support for passphrases.
      -

.. autoclass:: concoursetools.dockertools.SecretMount
