# (C) Crown Copyright GCHQ
import re
import textwrap
from typing import cast
from unittest import TestCase

from concoursetools.parsing import format_check_output, format_in_out_output, parse_check_payload, parse_in_payload, parse_out_payload
from concoursetools.typing import VersionConfig


class CheckParsingTests(TestCase):
    """
    Tests that Concourse JSON is being properly parsed.
    """
    def test_check_step_with_version(self) -> None:
        config = textwrap.dedent("""
        {
            "source": {
                "uri": "git://some-uri",
                "branch": "develop",
                "private_key": "...",
                "merges": true
            },
            "version": { "ref": "61cbef" }
        }
        """).strip()
        resource, version = parse_check_payload(config)

        self.assertDictEqual(resource, {
            "uri": "git://some-uri",
            "branch": "develop",
            "private_key": "...",
            "merges": True,
        })

        self.assertIsNotNone(version)
        version = cast(VersionConfig, version)
        self.assertDictEqual(version, {"ref": "61cbef"})

    def test_check_step_no_version(self) -> None:
        config = textwrap.dedent("""
        {
            "source": {
                "uri": "git://some-uri",
                "branch": "develop",
                "private_key": "..."
            }
        }
        """).strip()
        resource, version = parse_check_payload(config)

        self.assertDictEqual(resource, {
            "uri": "git://some-uri",
            "branch": "develop",
            "private_key": "...",
        })

        self.assertIsNone(version)

    def test_check_step_missing_source(self) -> None:
        config = textwrap.dedent("""
        {
            "version": { "ref": "61cbef" }
        }
        """).strip()
        with self.assertRaises(RuntimeError):
            parse_check_payload(config)

    def test_check_step_broken_version(self) -> None:
        config = textwrap.dedent("""
        {
            "source": {
                "uri": "git://some-uri",
                "branch": "develop",
                "private_key": "..."
            },
            "version": {
                "ref": "61cbef",
                "is_merge": true
            }
        }
        """).strip()
        resource, version = parse_check_payload(config)

        self.assertDictEqual(resource, {
            "uri": "git://some-uri",
            "branch": "develop",
            "private_key": "...",
        })

        self.assertIsNotNone(version)
        version = cast(VersionConfig, version)

        self.assertDictEqual(version, {
            "ref": "61cbef",
            "is_merge": "True",
        })


class InParsingTests(TestCase):
    """
    Tests that Concourse JSON is being properly parsed.
    """
    def test_in_step_with_params(self) -> None:
        config = textwrap.dedent("""
        {
            "source": {
                "uri": "git://some-uri",
                "branch": "develop",
                "private_key": "...",
                "merges": true
            },
            "version": { "ref": "61cbef" },
            "params": { "shallow": true }
        }
        """).strip()
        resource, version, params = parse_in_payload(config)

        self.assertDictEqual(resource, {
            "uri": "git://some-uri",
            "branch": "develop",
            "private_key": "...",
            "merges": True,
        })

        self.assertDictEqual(version, {"ref": "61cbef"})
        self.assertDictEqual(params, {"shallow": True})

    def test_in_step_no_params(self) -> None:
        config = textwrap.dedent("""
        {
            "source": {
                "uri": "git://some-uri",
                "branch": "develop",
                "private_key": "..."
            },
            "version": { "ref": "61cbef" }
        }
        """).strip()
        resource, version, params = parse_in_payload(config)

        self.assertDictEqual(resource, {
            "uri": "git://some-uri",
            "branch": "develop",
            "private_key": "...",
        })

        self.assertDictEqual(version, {"ref": "61cbef"})
        self.assertDictEqual(params, {})

    def test_in_step_missing_source(self) -> None:
        config = textwrap.dedent("""
        {
            "version": { "ref": "61cbef" }
        }
        """).strip()
        with self.assertRaises(RuntimeError):
            parse_in_payload(config)

    def test_in_step_missing_version(self) -> None:
        config = textwrap.dedent("""
        {
            "source": {
                "uri": "git://some-uri",
                "branch": "develop",
                "private_key": "..."
            }
        }
        """).strip()
        with self.assertRaises(RuntimeError):
            parse_in_payload(config)


class OutParsingTests(TestCase):
    """
    Tests that Concourse JSON is being properly parsed.
    """
    def test_out_step_with_params(self) -> None:
        config = textwrap.dedent("""
        {
            "source": {
                "uri": "git://some-uri",
                "branch": "develop",
                "private_key": "...",
                "merges": true
            },
            "params": {
                "repo": "repo",
                "force": false
            }
        }
        """).strip()
        resource, params = parse_out_payload(config)

        self.assertDictEqual(resource, {
            "uri": "git://some-uri",
            "branch": "develop",
            "private_key": "...",
            "merges": True,
        })

        self.assertDictEqual(params, {
            "repo": "repo",
            "force": False,
        })

    def test_out_step_no_params(self) -> None:
        config = textwrap.dedent("""
        {
            "source": {
                "uri": "git://some-uri",
                "branch": "develop",
                "private_key": "..."
            }
        }
        """).strip()
        resource, params = parse_out_payload(config)

        self.assertDictEqual(resource, {
            "uri": "git://some-uri",
            "branch": "develop",
            "private_key": "...",
        })

        self.assertDictEqual(params, {})

    def test_out_step_missing_source(self) -> None:
        config = textwrap.dedent("""
        {
            "params": {
                "repo": "repo",
                "force": false
            }
        }
        """).strip()
        with self.assertRaises(RuntimeError):
            parse_out_payload(config)


class FormatTests(TestCase):
    """
    Tests for the formatting of strings to pass to Concourse.
    """
    def test_check_format(self) -> None:
        versions = [
            {"ref": "61cbef"},
            {"ref": "d74e01"},
            {"ref": "7154fe"},
        ]
        expected_output = re.sub(r"\s", "", """
        [
            { "ref": "61cbef" },
            { "ref": "d74e01" },
            { "ref": "7154fe" }
        ]
        """)
        self.assertEqual(expected_output, format_check_output(versions, separators=(",", ":")))

    def test_check_format_not_strings(self) -> None:
        versions = [
            {"ref": 100},
            {"ref": True},
            {"ref": None},
        ]
        expected_output = re.sub(r"\s", "", """
        [
            { "ref": "100" },
            { "ref": "True" },
            { "ref": "None" }
        ]
        """)
        self.assertEqual(expected_output, format_check_output(versions, separators=(",", ":")))  # type: ignore[arg-type]

    def test_in_out_format(self) -> None:
        version = {"ref": "61cebf"}
        metadata = {
            "commit": "61cebf",
            "author": "HulkHogan",
        }
        expected_output = re.sub(r"\s", "", """
        {
            "version": { "ref": "61cebf" },
            "metadata": [
                { "name": "commit", "value": "61cebf" },
                { "name": "author", "value": "HulkHogan" }
            ]
        }
        """)
        self.assertEqual(expected_output, format_in_out_output(version, metadata, separators=(",", ":")))

    def test_in_out_format_not_strings(self) -> None:
        version = {"ref": True}
        metadata = {
            "commit": 100,
            "author": "HulkHogan",
        }
        expected_output = re.sub(r"\s", "", """
        {
            "version": { "ref": "True" },
            "metadata": [
                { "name": "commit", "value": "100" },
                { "name": "author", "value": "HulkHogan" }
            ]
        }
        """)
        self.assertEqual(expected_output, format_in_out_output(version, metadata, separators=(",", ":")))  # type: ignore[arg-type]
