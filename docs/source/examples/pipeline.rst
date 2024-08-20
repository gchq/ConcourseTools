AWS SageMaker Pipeline
======================

.. caution::
    This example is for reference only. It is not extensively tested, and it not intended to be a fully-fledged Concourse resource for production pipelines. Copy and paste at your own risk.

In this example we will explore how to create a custom Concourse Resource using the Concourse Tools library. In this particular example we will consider a resource to interact with an `AWS SageMaker pipeline <https://docs.aws.amazon.com/sagemaker/latest/dg/pipelines-sdk.html>`_, which needs to keep track of `executions <https://docs.aws.amazon.com/sagemaker/latest/dg/run-pipeline.html>`_ of the pipeline, and to also be able to trigger new executions. In particular, we want the following behaviour:

* :concourse:`get-step`: Fetch the latest execution and download the metadata.
* :concourse:`put-step`: Start a new pipeline execution.

The functionality of the resource will depend heavily on `boto3 <https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/sagemaker.html>`_ in order to reduce the amount of code needed to function.


Execution Version
-----------------

When selecting the version for a custom resource, it is important to ensure that they will satisfy the following conditions:

1. Versions should be linearly ordered.
2. Versions should be unique within the context of the resource.
3. Versions should contain the minimum amount of information required to be unique within the resource.

It is possible to break some of these assumptions, but to do so requires great care. For example, the `built-in git resource <https://github.com/concourse/git-resource>`_ uses a git commit to map to a version, but these are only unique within the context of a specific branch. Therefore, the resource requires a branch to be specified, otherwise the versions would not be linear. Although it would be possible to also include commit-specific information (such as author and timestamp) within the version, this is unnecessary.

Previously, some custom Concourse resources (such as the `Bitbucket pull request resource <https://github.com/laurentverbruggen/concourse-bitbucket-pullrequest-resource>`_) attempt to use non-linear versions to be able to track both commits *and* pull request IDs, but this requires the user to set ``version: every`` on their resource in order to properly pick up *every* change, which can have some unintended consequences (such as multiple commits pushed to a branch at once being considered multiple versions). The correct way to deal with this now is to make use of :concourse:`instanced-pipelines` to correspond to each pull request, and to keep versions as linear. For more information on this pattern, see the :ref:`Github Branches` example.

In this example, each execution has a corresponding `ARN <https://docs.aws.amazon.com/IAM/latest/UserGuide/reference-arns.html>`_, which uniquely defines it within the context of a pipeline (in fact, it uniquely defines it within an AWS account). Therefore, our version should contain this ARN as a string. This can be done by inheriting from the :class:`~concoursetools.version.Version` class, but it is generally easier (and requires less code) to instead make use of :mod:`dataclasses` and to inherit from :class:`~concoursetools.version.TypedVersion`:


.. literalinclude:: ../../../examples/pipeline.py
    :pyobject: ExecutionVersion

Passing around an instance of a class instead of a JSON object or even just a string is much easier, and allows us to make use of type hinting and other linter features. It also allows us to more finely specify how :ref:`version equality and comparisons <Version Comparisons>` work, and also to define how to map the attributes of the version to and from the JSON object that Concourse will use.

Pipeline Resource
-----------------

The first thing to do is to establish what the :concourse:`resources.schema.resource.source` of the resource will be, and what we require of the user to properly configure it. For Concourse Tools, a resource is a subclass of the :class:`~concoursetools.resource.ConcourseResource` class, and the arguments in the ``__init__`` method correspond to the source. In this example, we require one configuration option, and an additional *optional* option:

* ``pipeline``: This will be the `ARN <https://docs.aws.amazon.com/IAM/latest/UserGuide/reference-arns.html>`_ of the pipeline itself. We can parse this for the pipeline name we use for the `boto3 <https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/sagemaker.html>`_ calls, as well as the region we need for constructing the client. It should be a string.
* ``statuses``: A pipeline execution can have one of five statuses at any time: ``Executing``, ``Stopping``, ``Stopped``, ``Failed`` and ``Succeeded``. By default, we don't want to trigger a version for executions which are still going, but we want the user to have this choice. Therefore, we pass a default value of a list containing the statuses which trigger a version, and allow the user to pass their own.

These options correspond to the following ``__init__`` method:

.. literalinclude:: ../../../examples/pipeline.py
    :pyobject: PipelineResource.__init__
    :dedent:

A few things are happening here:

1. We inherited from :class:`~concoursetools.resource.ConcourseResource`, and we are required to pass in our :class:`~concoursetools.version.Version` subclass so that the resource can properly parse the versions as JSON.
2. We split the ARN into subgroups to fetch the region and pipeline name. Using tuple unpacking gives us an extra opportunity to catch when a user has passed a name instead of an ARN.
3. We create the client here to avoid storing the region in the class. It also helps in testing to allow us to avoid recreating it each time.
4. We set the pipeline name and statuses as instance attributes. Note that we don't bother storing the pipeline ARN.

Checking for Executions
________________________

The first behaviour we will implement is the :concourse:`check <implementing-resource-types.resource-check>`, when the external resource is queried for new executions. There are a few cases that we need to handle:

1. If no previous version is passed (i.e., the parameter is :data:`None`), then we know that this is the first request and we need to return the *latest valid version*.
2. If no versions are available *at all* then an empty list should be returned.
3. If there are new executions which have finished since the previous version, then they need to be returned in "oldest-to-newest" order, including the previous version "if it's still valid".
4. If there have been no more executions since the previous version then the response should *only* include the previous version.
5. If the previous version is no longer in the set of versions (i.e., something has gone wrong or the external resource has somehow changed) then the latest version should be returned. In practice this rarely happens, but should be planned for.

We start by defining a private method on the resource to yield "potential versions" from the external source. This is just to allow us to check equality with the previous version directly, which is cleaner than worrying about a potential :class:`AttributeError` if the previous version is :data:`None`. It also allows us to handle the way in which AWS batches up its response when calling `list_pipeline_executions <https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/sagemaker/client/list_pipeline_executions.html>`_. All we need be concerned with is that this method will yield instances of ``ExecutionVersion`` in newest-to-oldest order until the server runs out.

.. literalinclude:: ../../../examples/pipeline.py
    :pyobject: PipelineResource._yield_potential_execution_versions
    :dedent:

We can then handle the actual behaviour, which is done by overloading :meth:`~concoursetools.resource.ConcourseResource.fetch_new_versions` like so:

.. literalinclude:: ../../../examples/pipeline.py
    :pyobject: PipelineResource.fetch_new_versions
    :dedent:

We start by defining an iterator on the output of ``_yield_potential_execution_versions``. We then handle the case where the previous version has not been passed. We try to pull the first version from the iterator. If this fails (it will raise a :class:`StopIteration` error) then there are no available versions (case 2) and we return a list. If this succeeds, then we return this first (and newest) version (case 1). If a previous version *has* been passed, we begin to iterate through the versions, checking for equality with the previous version. If we reach the version then we return this list *in reverse order* (see the reversal at the end), which is case 3 or 4. If we do *not* reach the version (note the ``else`` clause in the ``for`` loop) then we know that the external source has changed, and we return the latest version (case 5).

Downloading Executions
______________________

The next functionality to consider is the downloading of a version in a :concourse:`get-step`. This is implemented within Concourse Tools by overloading :meth:`~concoursetools.resource.ConcourseResource.download_version`. The behaviour we want for this step is:

* Download the metadata of the execution (as described in `describe_pipeline_execution <https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/sagemaker/client/describe_pipeline_execution.html>`_) to a JSON file.
* *Optionally* (but by default) download the definition of the pipeline to a different JSON file. This is done by calling `describe_pipeline_definition_for_execution <https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/sagemaker/client/describe_pipeline_definition_for_execution.html>`_.
* Return information about the pipeline as metadata to be displayed in the UI.

The code for doing this is as follows:

.. literalinclude:: ../../../examples/pipeline.py
    :pyobject: PipelineResource.download_version
    :dedent:

We start by describing the execution, removing the ``ResponseMetadata`` (no reason to download this) and  writing it to a file. We allow the user to configure the name of this file by making it an optional parameter of the function. Because the execution information contains :class:`~datetime.datetime` instances, we need a custom encoder:

.. literalinclude:: ../../../examples/pipeline.py
    :pyobject: DatetimeSafeJSONEncoder

Next, we check if the user wishes to download the pipeline, and then write the definition to file. Again, each of these are configurable and the defaults are handled with default parameters. Finally, we create the metadata. It is a lot easier to deal with a Python :class:`dict` than JSON in bash, and we can take advantage of the numerous ways to update and mutate the dictionary. Here, we specifically filter out any pieces of metadata with a value of :data:`None` to reduce the amount of code we need to write. Finally, both the original version and the metadata are returned.

Publishing New Executions
_________________________

FInally, we consider the functionality of the :concourse:`put-step`, and creating new versions. To do this in Concourse Tools, we overload the :meth:`~concoursetools.resource.ConcourseResource.publish_new_version` method. The code will rely on a call to `start_pipeline_execution <https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/sagemaker/client/start_pipeline_execution.html>`_.

.. literalinclude:: ../../../examples/pipeline.py
    :pyobject: PipelineResource.publish_new_version
    :dedent:

We start with the execution description. We include an optional parameter to allow the user to specify this in their :concourse:`get params <get-step.schema.get.params>`, but if they don't then we create a default description based on the :class:`~concoursetools.metadata.BuildMetadata`. In instance of this class is passed to the :meth:`~concoursetools.resource.ConcourseResource.download_version` and :meth:`~concoursetools.resource.ConcourseResource.publish_new_version` methods, and wraps the build environment to more easily make use of environment variables which are made available to resources, as well as some useful methods for computing the :meth:`~concoursetools.metadata.BuildMetadata.build_url` and working with the :meth:`~concoursetools.metadata.BuildMetadata.instance_vars`. In particular here we've made use of the ``BUILD_ID`` and ``BUILD_PIPELINE_NAME`` attributes.  We also allow the user to pass in parameters for the execution. These are passed in as a mapping, but need to be converted to a list to fit with the function call. We also add them to the metadata for the user's benefit. Finally, we return the new version and the metadata.

.. note::
    The response from the `start_pipeline_execution <https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/sagemaker/client/start_pipeline_execution.html>`_ function contains only the ARN of the new execution, and is a big reason why the version doesn't contain the start time of the execution. To fill that in, we would need to make a second request to the server to fetch the information about the execution before creating and returning the version, which is not ideal.

Pipeline Conclusion
-------------------

The final resource only requires :linecount:`../../../examples/pipeline.py` lines of code, and looks like this:

.. literalinclude:: ../../../examples/pipeline.py
    :linenos:
