Mocking
=======

.. automodule:: concoursetools.mocking


Environment Variables
---------------------

.. autofunction:: concoursetools.mocking.mock_environ

.. autofunction:: concoursetools.mocking.create_env_vars

.. autoclass:: concoursetools.mocking.TestBuildMetadata

Input / Output
--------------

.. autofunction:: concoursetools.mocking.mock_argv

.. autofunction:: concoursetools.mocking.mock_stdin

.. autoclass:: concoursetools.mocking.StringIOWrapper
    :members:


Directory State
---------------
Often you need to mock certain files when testing your resource, which are usually accessible in the resource folders. Rather than set this up manually, you can pass a directory state to :class:`~concoursetools.mocking.TemporaryDirectoryState` to make this easier.

.. autoclass:: concoursetools.mocking.TemporaryDirectoryState
    :members:
