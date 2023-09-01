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
import json
import os
from typing import Any, Dict, Optional
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

        These can still be accessed via :obj:`os.environ`, but they are not supported by Concourse Tools.
    """
    def __init__(self, BUILD_ID: str, BUILD_TEAM_NAME: str, ATC_EXTERNAL_URL: str, BUILD_NAME: Optional[str] = None,
                 BUILD_JOB_NAME: Optional[str] = None, BUILD_PIPELINE_NAME: Optional[str] = None,
                 BUILD_PIPELINE_INSTANCE_VARS: Optional[str] = None):
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
        Return :obj:`True` if this build is one-off, and :obj:`False` otherwise.

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
        """Return :obj:`True` if this is an :concourse:`instanced pipeline <instanced-pipelines>`."""
        return self.BUILD_PIPELINE_INSTANCE_VARS is not None

    def instance_vars(self) -> Dict[str, Any]:
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
        instance_vars: Dict[str, Any] = json.loads(self.BUILD_PIPELINE_INSTANCE_VARS or "{}")
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


def _flatten_dict(d: Dict[str, Any]) -> Dict[str, Any]:
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
        {"key_1": "value_1", "key_2.1": "value_2_1", "key_2.2", "value_2_2"}
    """
    flattened_dict: Dict[str, Any] = {}
    for key, value in d.items():
        if isinstance(value, dict):
            sub_flattened_dict = _flatten_dict(value)
            for sub_key, sub_value in sub_flattened_dict.items():
                flattened_dict[f"{key}.{sub_key}"] = sub_value
        else:
            flattened_dict[key] = value
    return flattened_dict
