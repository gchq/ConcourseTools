AWS Secrets
===========

.. caution::
    This example is for reference only. It is not extensively tested, and it not intended to be a fully-fledged Concourse resource for production pipelines. Copy and paste at your own risk.

This example will showcase the :class:`~concoursetools.additional.TriggerOnChangeConcourseResource`, and how to build a resource to emit versions whenever something has changed, rather than when a new linear version becomes available. In this example, the resource will watch an secret in `AWS SecretsManager <https://docs.aws.amazon.com/secretsmanager/latest/userguide/intro.html>`_, and yield a new version whenever the value of that secret has changed. It will also allow the user to optionally download the secret value, and also to update the secret via a string or a file. The functionality will depend heavily on `boto3 <https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/secretsmanager.html>`_ in order to reduce the amount of code needed to function.


Secrets Version
---------------

Every secret in SecretsManager has a number of `versions <https://docs.aws.amazon.com/secretsmanager/latest/userguide/whats-in-a-secret.html#term_version>`_ representing changes to the secret value. This is all the version needs to contain:

.. literalinclude:: ../../../examples/secrets.py
    :pyobject: SecretVersion

Here, we only inherit from :class:`~concoursetools.version.TypedVersion` to save some lines of code.


Secrets Resource
----------------

We start by inheriting from :class:`~concoursetools.additional.TriggerOnChangeConcourseResource` and passing in the version class. The resource should take an ARN string of the secret (AWS recommends this over the secret name). We also define the AWS SecretsManager client in the ``__init__`` method for ease. To get the AWS region, we need only parse the ARN string to avoid asking for duplicate values from the user:

.. literalinclude:: ../../../examples/secrets.py
    :pyobject: Resource.__init__
    :dedent:

With this resource type, we don't overload from :meth:`~concoursetools.resource.ConcourseResource.fetch_new_versions`, as it would force us to define the behaviour of the trigger. Instead, we let the resource implement this for us, and overload :meth:`~concoursetools.additional.TriggerOnChangeConcourseResource.fetch_latest_version`. If the version we fetch is the same, then no new versions are emitted. If the version is different, then that new version is sent which which will trigger the pipeline:

.. literalinclude:: ../../../examples/secrets.py
    :pyobject: Resource.fetch_latest_version
    :dedent:

We use `list_secret_version_ids <https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/secretsmanager/client/list_secret_version_ids.html>`_ with ``IncludeDeprecated=False`` to ensure that we only get versions which are either current or pending. We then iterate over the versions and find the one marked with ``AWSCURRENT``. If we don't find it then we raise an error to alert the user.

Next, we overload :meth:`~concoursetools.resource.ConcourseResource.download_version` to allow us to download the metadata (and optionally the value) of the new secret:

.. literalinclude:: ../../../examples/secrets.py
    :pyobject: Resource.download_version
    :dedent:

The behaviour of the resource is as follows:

1. The metadata of the secret is fetched from AWS using `describe_secret <https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/secretsmanager/client/describe_secret.html>`_. The response metadata is removed, but could potentially be output as :ref:`Step Metadata`.
2. The metadata is saved to a file. By default this is named ``metadata.json``, but the user can customise this with the parameters of the :concourse:`get-step`.
3. If the user has requested the secret value also (which is **not** the default behaviour), then this is fetched using `get_secret_value <https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/secretsmanager/client/get_secret_value.html>`_ to be saved to a file, which defaults to ``value`` but is again customisable by the user.
4. If the response contains a string, then this is written directly to the file using :meth:`~Path.write_text`, but if it contains a binary then it is instead written using :meth:`~Path.write_bytes`.

The :mod:`json` module is imported as ``json_package`` to avoid a name collision with a future argument. The metadata of the secret contains some :class:`~datetime.datetime` objects, and so a custom :class:`~json.JSONEncoder` is required:

.. literalinclude:: ../../../examples/secrets.py
    :pyobject: DatetimeSafeJSONEncoder

Finally, we overload :meth:`~concoursetools.resource.ConcourseResource.publish_new_version` to allow the user to update the secret. We *could* make this rotate the secret, but for the purposes of this example we will allow the user to specify a new value exactly:

.. literalinclude:: ../../../examples/secrets.py
    :pyobject: Resource.publish_new_version
    :dedent:

The behaviour is as follows:

1. If the user has specified the secret value as JSON, then encode that as a string as pass it forward.
2. If the secret is specified as a string, then attempt to set the secret value with `put_secret_value <https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/secretsmanager/client/put_secret_value.html>`_.
3. If the secret is specified as a file path, then use :meth:`~Path.read_bytes` to get the contents of the file (more resilient than reading the text) and set the ``SecretBinary`` instead.
4. If none of these have been set, then raise an error.
5. Pull out the new ID from the response to establish the new version to return, and also pass the ``VersionStages`` as metadata to be output to the console.


AWS Secrets Conclusion
----------------------

We have added a lot of functionality for this resource in only :linecount:`../../../examples/secrets.py` lines of code. The final module looks like this:

.. literalinclude:: ../../../examples/secrets.py
    :linenos:
