GitHub Branches
===============

.. caution::
    This example is for reference only. It is not extensively tested, and it not intended to be a fully-fledged Concourse resource for production pipelines. Copy and paste at your own risk.

On occasion, you may wish your resource to emit versions when something has changed, and not have a history of this to rely on. For example, imagine that we want to run a pipeline on a number of different branches of a GitHub repository. Our resource could emit a number of versions like this:

.. code:: json

    {
      "branch": "feature/new-module",
      "commit": "abcdef..."
    }

But what happens when a check yields two versions from different branches? We could figure out the "latest" version by sorting by commit date, but if we are tracking multiple branches then we don't want to ignore a commit on one just because a more recent commit has been made on another. Previous in Concourse this was "fixed" by passing ``version: every`` to the resource, but this means that if multiple commits are pushed to a branch at once, then each commit will emit a build, which may not be what we want.

What we really want is to iterate over all branches in our repository, and spin up a branch-specific pipeline for each one using the :concourse:`set-pipeline-step`. This is easy to do, but we need to make sure that new pipelines are added when new branches appear, and that old pipelines are deleted when their branches are removed. We specifically require a resource which will trigger a pipeline whenever something has changed. The generic resource for this pattern is the :class:`~concoursetools.additional.TriggerOnChangeConcourseResource`, but because the "state" is made up of several "sub versions", it makes sense to instead utilise the :class:`~concoursetools.additional.MultiVersionConcourseResource`, which takes care of much of the boiler plate for us, and also allow us to automatically download these subversions as JSON so that we may iterate over them.

Branch Version
--------------

For this example, each "version" will contain an encoded JSON string with all of the subversions. We only care about whether or not that version (and hence the state) has changed, and not whether these versions were linear.  To start, we define the subversion schema:

.. literalinclude:: ../../../examples/github_branches.py
    :pyobject: BranchVersion

We inherit from :class:`~concoursetools.version.TypedVersion` to allow us to use the :func:`~dataclasses.dataclass` decorator and save us some lines of code. We have to specify ``unsafe_hash=True`` in order to ensure that the version instance will be *hashable*, otherwise we won't be able to use it with our resource. We also need to specify ``order=True`` to allow our subversions to be sorted, as this is required to make sure the same set of subversions yield identical versions. We could have made use of the :class:`~concoursetools.version.SortableVersionMixin`, but given that the :func:`~dataclasses.dataclass` decorator does this for us it isn't necessary here.

Branch Resource
---------------

We start by inheriting from :class:`~concoursetools.additional.MultiVersionConcourseResource`. A standard :class:`~concoursetools.resource.ConcourseResource` will take a version class, but this time we need to pass a *subversion class* instead, as well as a key:

.. literalinclude:: ../../../examples/github_branches.py
    :pyobject: Resource.__init__
    :end-at: super().__init__
    :dedent:

The resource will then construct a :class:`~concoursetools.version.Version` class which wraps the subversion class, and stores the list of subversions as a JSON-encoded string. The key, ``"branches"``, is used as the key in this version. The final version will look like this:

.. code:: python3

    {"branches": "[{\"name\": \"issue/95\"}, {\"name\": \"master\"}, {\"name\": \"release/6.7.x\"}, {\"name\": \"version\"}, {\"name\": \"version-lts\"}]"}

We then store a compiled regex and the API route within the class. There is no need to store each parameter separately, as we can just construct the API route in one line:

.. literalinclude:: ../../../examples/github_branches.py
    :pyobject: Resource.__init__
    :dedent:

The source of this resource would then look something like this:

.. code:: yaml

    source:
      owner: concourse
      repo: github-release-resource
      regex: release/.*

We only need to implement the :meth:`~concoursetools.additional.MultiVersionConcourseResource.fetch_latest_sub_versions` method; the results of this will be collected and converted into a final version by the parent class:

.. literalinclude:: ../../../examples/github_branches.py
    :pyobject: Resource.fetch_latest_sub_versions
    :dedent:

The logic required here is incredibly minimal, and we only need to return each available subversion. The returned set will then be sorted by the resource when converting it to its final version, which is why we needed the subversion to be sortable and hashable.

When the branches change (either with new ones added or existing ones removed) a new version will be emitted and the pipeline will be triggered. Users can then iterate over them in their pipeline using a combination of the :concourse:`across-step` and the :concourse:`set-pipeline-step`:

.. code:: yaml

    - get: repo-branches
    - load_var: branches
      file: branches/branches.json
    - across:
      - var: branch-info
        values: ((.:branches))
      set-pipeline: branch-pipeline
      file: ...
      vars:
        branch: ((.:branch-info.name))

GitHub Branches Conclusion
--------------------------

The final module only requires **43 lines** (including docstrings) and looks like this:

.. literalinclude:: ../../../examples/github_branches.py
    :linenos:
