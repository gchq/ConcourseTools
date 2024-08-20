xkcd Comics
===========

.. caution::
    This example is for reference only. It is not extensively tested, and it not intended to be a fully-fledged Concourse resource for production pipelines. Copy and paste at your own risk.

This example will showcase the :class:`~concoursetools.additional.SelfOrganisingConcourseResource`, and how to use it to save lines of code and avoid implementing logic to determine which versions are newer than the last. In this particular example we will build a resource type to trigger on new :xkcd:`xkcd comics <>`.

.. xkcd:: 1319


xkcd Version
------------

Each xkcd comic is associated with an integer, and so these form a natural choice for the version. We'll inherit from :class:`~concoursetools.version.TypedVersion` to minimise the code we need, and make sure our versions are hashable with ``unsafe_hash=True`` as is required by the resource. Finally, we'll also implement the :func:`~operator.__lt__` method to make sure our comparisons use the comic ID as an orderable integer.

.. literalinclude:: ../../../examples/xkcd.py
    :pyobject: ComicVersion


xkcd Resource
-------------

We start by inheriting from the :class:`~concoursetools.additional.SelfOrganisingConcourseResource`. We pass in our version, and also include an optional configuration parameter for the xkcd link. Although this is unlikely to matter to 99% of users, it is good practice to allow this ot be configured in case a user is hosting their own version of the comics (or if the URL changes), and it will avoid them needing to reimplement your work.

.. literalinclude:: ../../../examples/xkcd.py
    :pyobject: XKCDResource.__init__
    :dedent:

Next we need to overload :meth:`~concoursetools.additional.SelfOrganisingConcourseResource.fetch_all_versions`. Given that our versions are comparable, the resource will only return versions considered "greater than" the previous versions (if it exists, normal rules apply if it hasn't been passed), and will even order them for us, removing our need to worry about that ourselves.

Although we could technically scrape the xkcd website to check for new versions, it is much more polite to make use of the available :wikipedia:`RSS` feed or, in this case, the :wikipedia:`Atom <Atom_(web_standard)>` feed, which can be found :xkcd:`here <atom.xml>`. Although there are existing libraries designed to parse Atom feeds, it doesn't take too much effort to pull out the comic IDs, which is all we really need for this to work:

.. literalinclude:: ../../../examples/xkcd.py
    :pyobject: yield_comic_links

.. literalinclude:: ../../../examples/xkcd.py
    :pyobject: yield_comic_ids

When given the contents of the feed as a string, the ``yield_comic_ids`` will give us all of the integers corresponding to the newer comics. All we need to do is fetch the data from the source, and return our list of versions:

.. literalinclude:: ../../../examples/xkcd.py
    :pyobject: XKCDResource.fetch_all_versions
    :dedent:

The next step is to implement actually "getting" the version. Technically it is possible that between checking the versions and fetching one, it is no longer available in the feed. However, :wikipedia:`Randall <Randall Munroe>` has been kind enough to implement a :xkcd:`JSON API <json.html>`, and so we can just use that.

.. note::
    Since this API yields a link to the current comic, it would be possible to implement this example as a :class:`~concoursetools.additional.TriggerOnChangeConcourseResource`, but we've :ref:`already got an example for that one <AWS Secrets>`.

We'll fetch this information and pull out some of the useful information such as the title and upload date. We'll also generate the URL, and set this aside as :ref:`Step Metadata`:

.. literalinclude:: ../../../examples/xkcd.py
    :pyobject: XKCDResource.download_version
    :dedent:
    :end-before: info_path =

Next we write the metadata to a file, in case the user wishes to use it themselves:

.. literalinclude:: ../../../examples/xkcd.py
    :pyobject: XKCDResource.download_version
    :dedent:
    :start-at: info_path =
    :end-before: if image

We optionally (but defaulting to :data:`True`) download the image:

.. literalinclude:: ../../../examples/xkcd.py
    :pyobject: XKCDResource.download_version
    :dedent:
    :start-at: if image
    :end-before: if link

And finally we do something similar with the comic link, and the alt text:

.. literalinclude:: ../../../examples/xkcd.py
    :pyobject: XKCDResource.download_version
    :dedent:
    :start-at: if link

We don't intend for the resource to publish new comics (unless :wikipedia:`Randall <Randall Munroe>` displays some interest), but the :meth:`~concoursetools.resource.ConcourseResource.publish_new_version` method is an :func:`~abc.abstractmethod`, and so we need to explicitly overload it to ensure that the resource can be used at all. We do this by explicitly raising a :class:`NotImplementedError`:

.. literalinclude:: ../../../examples/xkcd.py
    :pyobject: XKCDResource.publish_new_version
    :dedent:

xkcd Conclusion
---------------

The final resource only requires :linecount:`../../../examples/xkcd.py` lines of code, and looks like this:

.. literalinclude:: ../../../examples/xkcd.py
    :linenos:
