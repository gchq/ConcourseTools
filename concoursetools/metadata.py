# (C) Crown Copyright GCHQ
"""
Build metadata represents the environment of the build.

The :meth:`~concoursetools.resource.ConcourseResource.download_version` and
:meth:`~concoursetools.resource.ConcourseResource.publish_new_version` methods are each passed a
``build_metadata`` parameter, which is an instance of :class:`BuildMetadata` populated from environment variables.

.. note::
    Build metadata is deliberately not passed to :meth:`~concoursetools.resource.ConcourseResource.fetch_new_versions`,
    as none of this metadata is passed to the check environment by Concourse, to avoid antipatterns.

See the Concourse :concourse:`implementing-resource-types.resource-metadata` documentation for more information.
"""
from __future__ import annotations

import json
import os
from string import Template as StringTemplate
from typing import Any
from urllib.parse import quote


class BuildMetadata:  # pylint: disable=invalid-name
    """
    A class containing metadata about the running build.

    :param BUILD_ID: The internal identifier for the build. Right now this is numeric, but it may become a UUID
                         in the future. Treat it as an absolute reference to the build.
    :param BUILD_TEAM_NAME: The team that the build belongs to.
    :param ATC_EXTERNAL_URL: The public URL for your ATC; useful for debugging.
    :param BUILD_NAME: The build number within the build's job.
    :param BUILD_JOB_NAME: The name of the build's job.
    :param BUILD_PIPELINE_NAME: The name of the pipeline that the build's job lives in.
    :param BUILD_PIPELINE_INSTANCE_VARS: The instance vars of the :concourse:`instanced pipeline <instanced-pipelines>`
                                         that the build's job lives in, serialized as JSON.

    .. note::
        A few variables are often present in the build environment, but are **not** documented by Concourse:

        * ``BUILD_JOB_ID``
        * ``BUILD_TEAM_ID``
        * ``BUILD_PIPELINE_ID``

        These can still be accessed via :data:`os.environ`, but they are not supported by Concourse Tools.
    """
    def __init__(self, BUILD_ID: str, BUILD_TEAM_NAME: str, ATC_EXTERNAL_URL: str, BUILD_NAME: str | None = None,
                 BUILD_JOB_NAME: str | None = None, BUILD_PIPELINE_NAME: str | None = None,
                 BUILD_PIPELINE_INSTANCE_VARS: str | None = None):
        self.BUILD_ID = BUILD_ID
        self.BUILD_TEAM_NAME = BUILD_TEAM_NAME

        self.BUILD_NAME = BUILD_NAME
        self.BUILD_JOB_NAME = BUILD_JOB_NAME
        self.BUILD_PIPELINE_NAME = BUILD_PIPELINE_NAME
        self.BUILD_PIPELINE_INSTANCE_VARS = BUILD_PIPELINE_INSTANCE_VARS

        self.ATC_EXTERNAL_URL = ATC_EXTERNAL_URL

    @property
    def BUILD_CREATED_BY(self) -> str:
        """
        The username that created the build.

        :raises PermissionError:  If this information has not been enabled.

        .. warning::
            By default this information is **not** available. To enable it, you need to set
            :concourse:`resources.schema.resource.expose_build_created_by` in your resource schema.
        """
        try:
            return os.environ["BUILD_CREATED_BY"]
        except KeyError as error:
            raise PermissionError("The 'BUILD_CREATED_BY' variable has not been made available. This must be enabled "
                                  "with the 'expose_build_created_by' variable within the resource schema: "
                                  "https://concourse-ci.org/resources.html#schema.resource.expose_build_created_by") from error

    @property
    def is_one_off_build(self) -> bool:
        """
        Return :data:`True` if this build is one-off, and :data:`False` otherwise.

        A build is a "one-off" is it is triggered via the Concourse CLI
        :concourse:`execute command <tasks.running-tasks>`.
        It is determined by the absence of all of the following attributes:

        * ``BUILD_JOB_NAME``
        * ``BUILD_PIPELINE_NAME``
        * ``BUILD_PIPELINE_INSTANCE_VARS``

        .. caution::
            The documentation insists that ``$BUILD_NAME`` will also not be set in the
            environment during a one-off build, but experimentation has shown this to be **false**.
        """
        return all(attr is None for attr in (self.BUILD_JOB_NAME, self.BUILD_PIPELINE_NAME, self.BUILD_PIPELINE_INSTANCE_VARS))

    @property
    def is_instanced_pipeline(self) -> bool:
        """Return :data:`True` if this is an :concourse:`instanced pipeline <instanced-pipelines>`."""
        return self.BUILD_PIPELINE_INSTANCE_VARS is not None

    def instance_vars(self) -> dict[str, object]:
        """
        Return the instance vars set on this pipeline as a mapping.

        When working with an :concourse:`instanced pipeline <instanced-pipelines>`, it is much more convenient to
        work with the instance vars as a mapping instead of a JSON string.

        .. note::
            If this is **not** an instanced pipeline, this method just returns
            an empty :class:`dict`.

        :Example:

            If a instanced pipeline has been created from within another pipeline
            (using the :concourse:`set-pipeline-step`), such as this:

            .. code:: yaml

              - set_pipeline: my-bots
                file: examples/pipelines/pipeline-vars.yml
                instance_vars:
                  first: the-third
                  hello: R2D2
                  branches:
                    from: develop
                    to: main

            then this method will return the following mapping:

            .. code:: python3

                {
                    "first": "the-third",
                    "hello": "R2D2",
                    "branches": {
                        "from" "develop",
                        "to": "main"
                    }
                }
        """
        instance_vars: dict[str, object] = json.loads(self.BUILD_PIPELINE_INSTANCE_VARS or "{}")
        return instance_vars

    def build_url(self) -> str:
        """
        Calculate the url to the build.

        This method will return a full URL to the build within the web UI, accounting for any
        instanced pipelines. It is the **most robust** way to get a link to the build within Concourse,
        and should be preferred where possible.
        """
        if self.is_one_off_build:
            build_path = f"builds/{self.BUILD_ID}"
        else:
            build_path = f"teams/{self.BUILD_TEAM_NAME}/pipelines/{self.BUILD_PIPELINE_NAME}/jobs/{self.BUILD_JOB_NAME}/builds/{self.BUILD_NAME}"

        if self.is_instanced_pipeline:
            flattened_instance_vars = _flatten_dict(self.instance_vars())
            query_string = "?" + "&".join(f"vars.{key}={quote(json.dumps(value))}" for key, value in flattened_instance_vars.items())
        else:
            query_string = ""

        return f"{self.ATC_EXTERNAL_URL}/{quote(build_path)}{query_string}"

    def format_string(self, string: str, additional_values: dict[str, str] | None = None,
                      ignore_missing: bool = False) -> str:
        """
        Format a string with metadata using standard bash ``$`` notation.

        Only a handful of "safe" values will be interpolated, not arbitrary attributes on the instance.
        These are the :concourse:`original environment variables <implementing-resource-types.resource-metadata>`,
        including :attr:`BUILD_CREATED_BY` if it exists. object missing environment variable (such as in the case of a
        one-off build) will be empty. A ``$BUILD_URL`` variable is also added for ease.

        .. danger::
            By passing additional values you are allowing an arbitrary user to view these with the correct choice
            of variable. You should take **great care** not to pass any sensitive values.

        :param string: The string to be interpolated.
        :param additional_values: Additional values which can be used for interpolation.
                                  The keys of the mapping should not include the ``$`` character.
        :param ignore_missing: By default, if the variable is not available then a :class:`KeyError` will be raised.
                               Setting this to :data:`True` will ignore missing variables.
        :returns: The interpolated string.
        :seealso: Interpolation is done using an instance of :class:`string.Template` by calling either
                  :meth:`~string.Template.substitute` when ``ignore_missing`` is :data:`False`, and
                  :meth:`~string.Template.safe_substitute` otherwise.

        :Example:
            >>> from concoursetools.mocking import TestBuildMetadata
            >>> metadata = TestBuildMetadata()
            >>> metadata.format_string("The build id is $BUILD_ID.")
            'The build id is 12345678.'
        """
        template = StringTemplate(string)
        possible_values: dict[str, str] = {
            "BUILD_ID": self.BUILD_ID,
            "BUILD_TEAM_NAME": self.BUILD_TEAM_NAME,
            "BUILD_NAME": self.BUILD_NAME or "",
            "BUILD_JOB_NAME": self.BUILD_JOB_NAME or "",
            "BUILD_PIPELINE_NAME": self.BUILD_PIPELINE_NAME or "",
            "BUILD_PIPELINE_INSTANCE_VARS": self.BUILD_PIPELINE_INSTANCE_VARS or "",
            "ATC_EXTERNAL_URL": self.ATC_EXTERNAL_URL,
            "BUILD_URL": self.build_url(),
        }
        if additional_values is not None:
            possible_values.update(additional_values)

        try:
            possible_values["$BUILD_CREATED_BY"] = self.BUILD_CREATED_BY
        except PermissionError:
            pass

        return template.safe_substitute(possible_values) if ignore_missing else template.substitute(possible_values)

    @classmethod
    def from_env(cls) -> "BuildMetadata":
        """Return an instance populated from the environment."""
        return cls(
            BUILD_ID=os.environ["BUILD_ID"],
            BUILD_TEAM_NAME=os.environ["BUILD_TEAM_NAME"],
            ATC_EXTERNAL_URL=os.environ["ATC_EXTERNAL_URL"],
            BUILD_NAME=os.environ.get("BUILD_NAME"),
            BUILD_JOB_NAME=os.environ.get("BUILD_JOB_NAME"),
            BUILD_PIPELINE_NAME=os.environ.get("BUILD_PIPELINE_NAME"),
            BUILD_PIPELINE_INSTANCE_VARS=os.environ.get("BUILD_PIPELINE_INSTANCE_VARS"),
        )


def _flatten_dict(d: dict[str, Any]) -> dict[str, Any]:
    """
    Flatten a nested dictionary into a single-level dictionary.

    :Example:
        >>> d = {
        ...     "key_1": "value_1",
        ...     "key_2": {
        ...         "1": "value_2_1",
        ...         "2": "value_2_2",
        ...     }
        ... }
        >>> _flatten_dict(d)
        {'key_1': 'value_1', 'key_2.1': 'value_2_1', 'key_2.2': 'value_2_2'}
    """
    flattened_dict: dict[str, object] = {}
    for key, value in d.items():
        if isinstance(value, dict):
            sub_flattened_dict = _flatten_dict(value)
            for sub_key, sub_value in sub_flattened_dict.items():
                flattened_dict[f"{key}.{sub_key}"] = sub_value
        else:
            flattened_dict[key] = value
    return flattened_dict
