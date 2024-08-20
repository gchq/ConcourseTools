Bitbucket Build Status
======================

.. caution::
    This example is for reference only. It is not extensively tested, and it not intended to be a fully-fledged Concourse resource for production pipelines. Copy and paste at your own risk.

This example will (mostly) recreate the excellent `SHyx0rmZ/bitbucket-build-status-resource <https://github.com/SHyx0rmZ/bitbucket-build-status-resource/tree/v1.6.0>`_ - specifically version 1.6.0. This is an ideal candidate to show how boiler plate code can be massively reduced to a single module concerning itself with nothing but the internal logic of your resource type.

We only care about updating the resource, and so the :class:`~concoursetools.additional.OutOnlyConcourseResource` seems like the best route.

Build Status Version
--------------------
A `quick glance through the original code <https://github.com/SHyx0rmZ/bitbucket-build-status-resource/blob/v1.6.0/scripts/out#L154>`_ shows that the version contains only the build status. Since the build status must be one of three specific values, the correct thing to do is to define an :class:`~enum.Enum`:

.. literalinclude:: ../../../examples/build_status.py
    :pyobject: BuildStatus

The benefit of using an enum (other than it being arguably the "correct" thing to do) is that we don't need to keep checking membership, and we can rely on the enum to raise an error upon user error. We also only need to worry about updating the enum in a single place when we need to.

Next we define the version. To make things easier, we can forget about converting the enum to a string and simply rely on :class:`~concoursetools.version.TypedVersion` to do it for us:

.. literalinclude:: ../../../examples/build_status.py
    :pyobject: Version


Build Status Resource
---------------------
Next we need to think about the resource. The hardest thing about this example is that there are a number of required parameters, which are actually only required in one of two circumstances. This unfortunately means that we can't rely on Concourse Tools to automatically catch missing parameters.

The original solves this problem through the use of `driver subclasses <https://github.com/SHyx0rmZ/bitbucket-build-status-resource/blob/v1.6.0/scripts/bitbucket/bitbucket.py#L19>`_, but since the number of conditionals remain *pretty much* the same we will avoid that for now, and it can always be refactored later. We can however deal with the variables in sensible groups, and rely on the right errors being thrown if the user gives the wrong parameters.

.. note::
    The original contains a number of deprecated parameters which **have not** been included in this example. These could be maintained quite easily.

When we collect all resource parameters and place them in a class it can seem quite daunting:

.. literalinclude:: ../../../examples/build_status.py
    :pyobject: Resource
    :end-at: super


Bitbucket Authentication
________________________
The first parameter group are the authentication parameters: ``username``, ``password``, ``client_id`` and ``client_secret``. We'll ignore that the latter two don't make sense for Bitbucket Server, and let the request fail if a user decides to try. The most Pythonic thing to do is to save an ``auth`` attribute to be used instead of the individual values, which will clutter the instance otherwise. We want a function to filter them out. If the user has passed ``username`` and ``password``, we want to use :class:`~requests.auth.HTTPBasicAuth`:

.. literalinclude:: ../../../examples/build_status.py
    :pyobject: create_auth
    :end-at: auth: AuthBase = HTTPBasicAuth

If the user instead passes ``client_id`` and ``client_secret``, we instead need to use OAuth to fetch a bearer token. Neither of these are available natively in :mod:`requests`, and so we need to implement our own. The original resource `has the following <https://github.com/SHyx0rmZ/bitbucket-build-status-resource/blob/v1.6.0/scripts/bitbucket/bitbucket.py#L39>`_:

.. literalinclude:: ../../../examples/build_status.py
    :pyobject: BitbucketOAuth
    :end-at: return request

We can then copy the `original code for requesting the access token <https://github.com/SHyx0rmZ/bitbucket-build-status-resource/blob/v1.6.0/scripts/bitbucket/bitbucket.py#L86>`_ into an alternative constructor for ease:

.. literalinclude:: ../../../examples/build_status.py
    :pyobject: BitbucketOAuth

That way the ``create_auth`` function becomes quite simple:

.. literalinclude:: ../../../examples/build_status.py
    :pyobject: create_auth


Bitbucket Drivers
_________________
We still need to differentiate between each type of driver, in order to know which parameters to complain about. It may be considered overkill, but I would choose to define another :class:`~enum.Enum`:

.. literalinclude:: ../../../examples/build_status.py
    :pyobject: Driver

Again, this is slightly more resilient to change than checking a string all the time. Of course, the ``driver`` parameter to the resource has to be a string, so a lookup is required:

.. literalinclude:: ../../../examples/build_status.py
    :pyobject: Resource
    :start-at: try:
    :end-at: Driver must be
    :dedent:

Now we can just check against the enum throughout our code. The initialiser now looks like this:

.. literalinclude:: ../../../examples/build_status.py
    :pyobject: Resource
    :end-at: Must set repository


Updating the Resource
---------------------
We can now write the code to update the resource, which involves implementing :meth:`~concoursetools.additional.OutOnlyConcourseResource.publish_new_version`. The method takes the usual parameters, and then the additional arguments offered by the original:

.. note::
    The original configures a few variables via files instead of direct parameters. This is likely due to it being implemented before the :concourse:`load-var-step` was a thing. This implementation replaces them with direct variables.

.. literalinclude:: ../../../examples/build_status.py
    :pyobject: Resource.publish_new_version
    :end-before: self.debug
    :dedent:

First up is debugging. The original allows the user to pass ``debug`` to the resource and have additional information be shown in the console. This required an `additional function <https://github.com/SHyx0rmZ/bitbucket-build-status-resource/blob/v1.6.0/scripts/concourse/concourse.py>`_ to remember, but not so with Concourse tools: we can just print!

.. code:: python3

    if self._debug:
        print("--DEBUG MODE--")

This will then show up in the console when debugging has been activated. We could go one further and simplify our code with a ``debug`` function, which will also allow :ref:`coloured output <Colour>` to be printed:

.. literalinclude:: ../../../examples/build_status.py
    :pyobject: Resource.debug
    :dedent:

Remember creating that Build Status enum? We should make use of it here:

.. literalinclude:: ../../../examples/build_status.py
    :pyobject: Resource.publish_new_version
    :start-at: try
    :end-at: {possible_values}
    :dedent:

Next we need to fetch the commit hash (if it hasn't already been set). This is more or less a direct lift from the `original code <https://github.com/SHyx0rmZ/bitbucket-build-status-resource/blob/v1.6.0/scripts/out#L49>`_, except we can make use of the fact that ``sources_dir`` is both already available to us (no shenanigans with :data:`sys.argv`), but is also a :class:`~pathlib.Path` instance, which makes the code a bit shorter:

.. literalinclude:: ../../../examples/build_status.py
    :pyobject: Resource.publish_new_version
    :start-at: if commit_hash is None
    :end-at: subprocess.check_output
    :dedent:

.. tip::
    If I were coding this from scratch, I would make use of the `GitPython <https://gitpython.readthedocs.io/en/stable/>`_ package (and the `Mercurial <https://pypi.org/project/mercurial/>`_ one if it were `actually stable <https://wiki.mercurial-scm.org/MercurialApi>`_) as part of the benefit of using Concourse Tools is having immediate access to the entire Python ecosystem, but I admit that it might seem a touch excessive given the simple command we need to run.

Next we need to figure out the default parameters for the build status. This is where Concourse Tools truly shines, as we require access to the :ref:`Build Metadata`. The :meth:`~concoursetools.additional.OutOnlyConcourseResource.publish_new_version` method is passed a :class:`~concoursetools.metadata.BuildMetadata` instance which contains attributes for everything that Concourse makes available to the resource, as well as some helpful convenience functions for dealing with one-off builds and instanced pipelines. In particular, it includes a :meth:`~concoursetools.metadata.BuildMetadata.build_url` method for calculating an exact URL for the build (instanced pipelines and all), which means that `this original code <https://github.com/SHyx0rmZ/bitbucket-build-status-resource/blob/v1.6.0/scripts/out#L74>`_ is condensed down from 39 lines to just one:

.. literalinclude:: ../../../examples/build_status.py
    :pyobject: Resource.publish_new_version
    :start-at: build_url =
    :end-at: build_url =
    :dedent:

The other defaults follow in a similar fashion:

.. literalinclude:: ../../../examples/build_status.py
    :pyobject: Resource.publish_new_version
    :start-at: key =
    :end-at: name = f"{build
    :dedent:

Next, we determine the URL to which to :func:`~requests.post` our request:

.. literalinclude:: ../../../examples/build_status.py
    :pyobject: Resource.publish_new_version
    :start-at: if self.driver
    :end-at: /statuses/build
    :dedent:

.. tip::
    .. versionadded:: 0.8.0

        The :meth:`~concoursetools.metadata.BuildMetadata.format_string` method can be used to substitute build metadata
        into the status description in order to allow users to reference the build:

        .. literalinclude:: ../../../examples/build_status.py
            :pyobject: Resource.publish_new_version
            :start-at: build_metadata.format_string
            :end-at: build_metadata.format_string
            :dedent:

Finally we submit the request and return the new version:

.. literalinclude:: ../../../examples/build_status.py
    :pyobject: Resource.publish_new_version
    :start-at: data =
    :dedent:

.. note::
    The original doesn't return any metadata, but this example does in order to illustrate how it works.


Conclusion
----------
The original repository scripts cover 12 Python files and a total of 433 lines. With Concourse tools, this same code is covered in :linecount:`../../../examples/build_status.py` lines, and a single Python file:

.. literalinclude:: ../../../examples/build_status.py
    :linenos:
