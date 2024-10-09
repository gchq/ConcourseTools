# (C) Crown Copyright GCHQ
"""
Concourse Tools contains a number of simple functions for mapping
between Python and the Concourse resource type paradigm.
"""
from __future__ import annotations

import json
from typing import Any, cast

from concoursetools.typing import Metadata, MetadataPair, Params, ResourceConfig, VersionConfig


def parse_check_payload(raw_json: str) -> tuple[ResourceConfig, VersionConfig | None]:
    """
    Parse raw input JSON for a :concourse:`check payload <implementing-resource-types.resource-check>`.

    :param raw_json: A JSON string of the following form:

    .. code:: json

        {
            "source": {
                "uri": "git://some-uri",
                "branch": "develop",
                "private_key": "..."
            },
            "version": { "ref": "61cbef" }
        }

    :returns: The source and version configuration (if it exists).

    .. note::
        If the version has not been passed, then :data:`None` will be returned, and **not** an empty :class:`dict`.
    """
    payload: dict[str, dict[str, object] | None] = json.loads(raw_json)
    source_config = _extract_source_config_from_payload(payload)

    try:
        version_config = _extract_version_config_from_payload(payload)
    except KeyError:
        version_config = None

    return source_config, version_config


def parse_in_payload(raw_json: str) -> tuple[ResourceConfig, VersionConfig, Params]:
    """
    Parse raw input JSON for an :concourse:`in payload <implementing-resource-types.resource-in>`.

    :param raw_json: A JSON string of the following form:

    .. code:: json

        {
            "source": {
                "uri": "git://some-uri",
                "branch": "develop",
                "private_key": "..."
            },
            "version": { "ref": "61cbef" },
            "params": { "skip_download": true }
        }

    :returns: The source and version configuration, and parameters passed to the get step.
    """
    payload: dict[str, dict[str, object] | None] = json.loads(raw_json)
    source_config = _extract_source_config_from_payload(payload)
    params_config = _extract_param_config_from_payload(payload)

    try:
        version_config = _extract_version_config_from_payload(payload)
    except KeyError as error:
        raise RuntimeError("Could not extract version from payload") from error

    return source_config, version_config, params_config


def parse_out_payload(raw_json: str) -> tuple[ResourceConfig, Params]:
    """
    Parse raw input JSON for an :concourse:`out payload <implementing-resource-types.resource-out>`.

    :param raw_json: A JSON string of the following form:

    .. code:: json

        {
            "params": {
                "branch": "develop",
                "repo": "some-repo"
            },
            "source": {
                "uri": "git@...",
                "private_key": "..."
            }
        }

    :returns: The source configuration, and parameters passed to the put step.
    """
    payload: dict[str, dict[str, object] | None] = json.loads(raw_json)
    source_config = _extract_source_config_from_payload(payload)
    params_config = _extract_param_config_from_payload(payload)

    return source_config, params_config


def parse_metadata(metadata_pairs: list[MetadataPair]) -> Metadata:
    """
    Convert key-value pairs toa key-value mapping.

    :param metadata_pairs: A list of key-value pairs for processing in Concourse.
    :returns: A key-value mapping representing metadata.
    """
    return {pair["name"]: pair["value"] for pair in metadata_pairs}


def format_check_output(version_configs: list[VersionConfig], **json_kwargs: Any) -> str:
    """
    Format :concourse:`check output <implementing-resource-types.resource-check>` as a JSON string.

    :param version_configs: A list of version configurations.
    :param json_kwargs: Additional keyword arguments to pass to :func:`json.dumps`.
    :returns: A formatted JSON string to pass to Concourse, in the following form:

    .. code:: json

        [
            { "ref": "61cbef" },
            { "ref": "d74e01" },
            { "ref": "7154fe" }
        ]
    """
    safe_version_configs = [{str(key): str(value) for key, value in version_config.items()} for version_config in version_configs]
    return json.dumps(safe_version_configs, **json_kwargs)


def format_in_out_output(version_config: VersionConfig, metadata: Metadata, **json_kwargs: Any) -> str:
    """
    Format :concourse:`in output <implementing-resource-types.resource-in>` or
    :concourse:`out output <implementing-resource-types.resource-out>` as a JSON string.

    :param version_config: A version configuration.
    :param metadata: A key-value mapping of metadata.
    :param json_kwargs: Additional keyword arguments to pass to :func:`json.dumps`.
    :returns: A formatted JSON string to pass to Concourse, in the following form:

    .. code:: json

        {
            "version": { "ref": "61cbef" },
            "metadata": [
                { "name": "commit", "value": "61cbef" },
                { "name": "author", "value": "Hulk Hogan" }
            ]
        }
    """
    safe_version_config = {str(key): str(value) for key, value in version_config.items()}
    safe_metadata = format_metadata(metadata)
    output = {
        "version": safe_version_config,
        "metadata": safe_metadata,
    }
    return json.dumps(output, **json_kwargs)


def format_metadata(metadata: Metadata) -> list[MetadataPair]:
    """
    Convert a key-value mapping to key-value pairs.

    :param metadata: A key-value mapping representing metadata. Keys and values should both be strings.
    :returns: A list of key-value pairs for processing in Concourse.
    """
    return [{"name": str(name), "value": str(value)} for name, value in metadata.items()]


def format_check_input(resource_config: ResourceConfig, version_config: VersionConfig | None = None, **json_kwargs: Any) -> str:
    """
    Format :concourse:`check input <implementing-resource-types.resource-check>` as a JSON string.

    :param resource_config: A resource configuration.
    :param version_config: A version configuration, or :data:`None` if no version currently exists.
    :param json_kwargs: Additional keyword arguments to pass to :func:`json.dumps`.
    :returns: A formatted JSON string as Concourse will pass to a Check:

    .. code:: json

        {
            "source": {
                "uri": "git://some-uri",
                "branch": "develop",
                "private_key": "..."
            },
            "version": { "ref": "61cbef" }
        }
    """
    payload = {"source": resource_config}
    if version_config is not None:
        payload["version"] = version_config
    return json.dumps(payload, **json_kwargs)


def format_in_input(resource_config: ResourceConfig, version_config: VersionConfig, params: Params | None = None, **json_kwargs: Any) -> str:
    """
    Format :concourse:`in input <implementing-resource-types.resource-in>` as a JSON string.

    :param resource_config: A resource configuration.
    :param version_config: A version configuration.
    :param params: Optional parameters to be passed.
    :param json_kwargs: Additional keyword arguments to pass to :func:`json.dumps`.
    :returns: A formatted JSON string as Concourse will pass to an In:

    .. code:: json

        {
            "source": {
                "uri": "git://some-uri",
                "branch": "develop",
                "private_key": "..."
            },
            "version": { "ref": "61cbef" },
            "params": { "skip_download": true }
        }
    """
    payload = {
        "source": resource_config,
        "version": version_config,
    }
    if params is not None:
        payload["params"] = params
    return json.dumps(payload, **json_kwargs)


def format_out_input(resource_config: ResourceConfig, params: Params | None = None, **json_kwargs: Any) -> str:
    """
    Format :concourse:`out input <implementing-resource-types.resource-out>` as a JSON string.

    :param resource_config: A resource configuration.
    :param params: Optional parameters to be passed.
    :param json_kwargs: Additional keyword arguments to pass to :func:`json.dumps`.
    :returns: A formatted JSON string as Concourse will pass to an Out:

    .. code:: json

        {
            "params": {
                "branch": "develop",
                "repo": "some-repo"
            },
            "source": {
                "uri": "git@...",
                "private_key": "..."
            }
        }
    """
    payload = {"source": resource_config}
    if params is not None:
        payload["params"] = params
    return json.dumps(payload, **json_kwargs)


def _extract_source_config_from_payload(payload: dict[str, dict[str, Any] | None]) -> dict[str, Any]:
    try:
        unsafe_source_config = payload["source"]
    except KeyError as error:
        raise RuntimeError("Could not extract source from payload") from error

    try:
        unsafe_source_config = cast(dict[str, Any], unsafe_source_config)
        source_config = {str(key): value for key, value in unsafe_source_config.items()}
    except AttributeError:
        if unsafe_source_config is not None:
            raise
        source_config = {}

    return source_config


def _extract_version_config_from_payload(payload: dict[str, dict[str, Any] | None]) -> dict[str, Any]:
    unsafe_version_config = payload["version"]
    unsafe_version_config = cast(dict[str, Any], unsafe_version_config)
    version_config = {str(key): str(value) for key, value in unsafe_version_config.items()}
    return version_config


def _extract_param_config_from_payload(payload: dict[str, dict[str, Any] | None]) -> dict[str, Any]:
    unsafe_params_config = payload.get("params", {})
    unsafe_params_config = cast(dict[str, Any], unsafe_params_config)
    params_config = {str(key): value for key, value in unsafe_params_config.items()}
    return params_config
