# (C) Crown Copyright GCHQ
"""
Functions for creating the Dockerfile or asset files.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
import inspect
import os
from pathlib import Path
import sys
import textwrap
from types import MethodType
from typing import Any, Literal, TypeVar

from concoursetools import ConcourseResource

T = TypeVar("T")
ScriptName = Literal["check", "in", "out"]
MethodName = Literal["check_main", "in_main", "out_main"]

DEFAULT_EXECUTABLE = "/usr/bin/env python3"
DEFAULT_PYTHON_VERSION = f"{sys.version_info.major}.{sys.version_info.minor}"


def create_script_file(path: Path, resource_class: type[ConcourseResource[Any]], method_name: MethodName,
                       executable: str = DEFAULT_EXECUTABLE, permissions: int = 0o755,
                       encoding: str | None = None) -> None:
    """
    Create a script file at a given path.

    :param path: The path at which the file will be created.
    :param resource_class: The :class:`~concoursetools.resource.ConcourseResource` class to be exported.
    :param method_name: The name of the method to be invoked.
    :param executable: The executable to use for the script (at the top).
    :param permissions: The (Linux) permissions the file should have. Defaults to ``rwxr-xr-x``.
    :param encoding: The encoding of the file as passed to :meth:`~pathlib.Path.write_text`.
                     Setting to :data:`None` (default) will use the user's default encoding.
    """
    method: MethodType = getattr(resource_class, method_name)
    docstring = inspect.getdoc(method) or ""
    docstring_header, *_ = docstring.split("\n")

    contents = textwrap.dedent(f"""
    #!{executable}
    \"\"\"
    {docstring_header}
    \"\"\"
    from {resource_class.__module__} import {resource_class.__name__}


    if __name__ == "__main__":
        {resource_class.__name__}.{method_name}()
    """).lstrip()

    path.write_text(contents, encoding=encoding)
    path.chmod(permissions)


class Instruction(ABC):
    """
    Represents an instruction in a Dockerfile.
    """
    def __str__(self) -> str:
        return self.to_string()

    @abstractmethod
    def to_string(self) -> str:
        """Return the string representation of the item."""
        ...


class Comment(Instruction):
    """
    Represents a comment in a Dockerfile.

    :comment: The comment to be added.

    :Example:
        >>> print(Comment("This is a comment"))
        # This is a comment
    """
    def __init__(self, comment: str) -> None:
        self.comment = comment

    def to_string(self) -> str:
        return f"# {self.comment}"


class CopyInstruction(Instruction):
    """
    Represents a ``COPY`` instruction.

    :param source: The file/folder to be copied.
    :param dest: The destination on the image of the file/folder. If :data:`None`, the destination will be the name
                 of the source file/folder, and will be placed in the working directory on the image.

    :Example:
        >>> print(CopyInstruction("folder/file.txt"))
        COPY folder/file.txt file.txt
        >>> print(CopyInstruction("folder/file.txt", "folder/new_file.txt"))
        COPY folder/file.txt folder/new_file.txt
    """
    def __init__(self, source: str, dest: str | None = None) -> None:
        if dest is None:
            *_, dest = source.split(os.sep)

        self.source = source
        self.dest = dest

    def to_string(self) -> str:
        return f"COPY {self.source} {self.dest}"


class EntryPointInstruction(Instruction):
    """
    Represents an ``ENTRYPOINT`` instruction.

    .. note::
        Docker recommends the "exec" form of this instruction over the "shell" form, and so the former is used here.

    :param commands: The commands to be run.

    :Example:
        >>> print(EntryPointInstruction(["python3", "-m", "http.server"]))
        ENTRYPOINT ["python3", "-m", "http.server"]
    """
    def __init__(self, commands: list[str]) -> None:
        self.commands = commands

    def to_string(self) -> str:
        command_string = ", ".join(f"\"{command}\"" for command in self.commands)
        return f"ENTRYPOINT [{command_string}]"


class EnvInstruction(Instruction):
    """
    Represents an ``ENV`` instruction.

    :param variables: A mapping of environment variables to be set.

    :Example:
        >>> print(EnvInstruction({"MY_NAME": "John Doe"}))
        ENV MY_NAME="John Doe"
        >>> print(EnvInstruction({"MY_NAME": "John Doe", "MY_AGE": "42"}))
        ENV MY_NAME="John Doe" MY_AGE="42"
    """
    def __init__(self, variables: dict[str, str]) -> None:
        self.variables = variables

    def to_string(self) -> str:
        variable_string = " ".join(f"{key}=\"{value}\"" for key, value in self.variables.items())
        return f"ENV {variable_string}"


class FromInstruction(Instruction):
    """
    Represents a ``FROM`` instruction.

    :param image: The base image to be used.
    :param tag: An optional image tag.
    :param digest: An optional digest of the image.
    :param platform: Pass to specify the platform to be used, i.e. ``"windows/amd64"``.

    :Example:
        >>> print(FromInstruction("python"))
        FROM python
        >>> print(FromInstruction("python", tag="3.11-slim"))
        FROM python:3.11-slim
        >>> print(FromInstruction("python", digest="sha256:380094..."))
        FROM python@sha256:380094...
        >>> print(FromInstruction("python", tag="3.11-slim", platform="linux/386"))
        FROM --platform=linux/386 python:3.11-slim
    """
    def __init__(self, image: str, tag: str | None = None, digest: str | None = None,
                 platform: str | None = None) -> None:
        if tag and digest:
            raise ValueError("Cannot pass BOTH tag and digest.")
        self.image = image
        self.tag = tag
        self.digest = digest
        self.platform = platform

    def to_string(self) -> str:
        if self.tag:
            ref = f"{self.image}:{self.tag}"
        elif self.digest:
            ref = f"{self.image}@{self.digest}"
        else:
            ref = self.image

        if self.platform:
            return f"FROM --platform={self.platform} {ref}"
        else:
            return f"FROM {ref}"


class RunInstruction(Instruction):
    """
    Represents a ``RUN`` instruction.

    .. note::
        The ``shell`` form of this command is more common than the ``exec`` form, so the former is used.

    :param commands: A list of commands to be run.

    :Example:
        >>> print(RunInstruction(["pip install --upgrade pip"]))
        RUN pip install --upgrade pip
        >>> print(RunInstruction(["pip install --upgrade pip", "pip install -r requirements.txt"]))
        RUN pip install --upgrade pip && pip install -r requirements.txt
    """
    def __init__(self, commands: list[str]) -> None:
        self.commands = commands

    def to_string(self) -> str:
        command_string = " && ".join(self.commands)
        return f"RUN {command_string}"


class WorkDirInstruction(Instruction):
    """
    Represents a ``WORKDIR`` instruction.

    :param work_dir: The directory to set as the working directory on the image.
    """
    def __init__(self, work_dir: str) -> None:
        self.work_dir = work_dir

    def to_string(self) -> str:
        return f"WORKDIR {self.work_dir}"


class Mount(ABC):
    """
    Represents a mount for the run command.
    """
    def __str__(self) -> str:
        return self.to_string()

    def to_string(self) -> str:
        """Return a string representation of the mount."""
        info_string = ",".join(f"{key}={value}" for key, value in self.to_dict().items())
        return f"--mount={info_string}"

    @abstractmethod
    def to_dict(self) -> dict[str, str]:
        """Return a key/value mapping corresponding to the Dockerfile keys for this mount."""
        ...


class SecretMount(Mount):
    """
    Represents a mounted secret value.

    :param secret_id: The ID of the secret.
    :param target: The location at which the secret will be mounted.
    :param required: If :data:`True`, the instruction errors out when the secret is unavailable.
    :param mode: The file mode for secret file in octal.
    :param user_id: The user ID for secret file.
    :param group_id: The group ID for secret file.

    :Example:
        >>> print(SecretMount(secret_id="aws", target="/root/.aws/credentials"))
        --mount=type=secret,id=aws,target=/root/.aws/credentials
    """
    def __init__(self, secret_id: str | None = None, target: str | None = None, required: bool | None = None,
                 mode: int | None = None, user_id: int | None = None, group_id: int | None = None) -> None:
        if not (secret_id or target):
            raise ValueError("Either a secret ID or target must be passed.")

        self.secret_id = secret_id
        self.target = target
        self.required = required
        self.mode = mode
        self.user_id = user_id
        self.group_id = group_id

    def to_dict(self) -> dict[str, str]:
        info: dict[str, str] = {"type": "secret"}

        if self.secret_id is not None:
            info["id"] = self.secret_id

        if self.target is not None:
            info["target"] = self.target

        if self.mode is not None:
            info["mode"] = f"{self.mode:0>4o}"

        if self.user_id is not None:
            info["uid"] = str(self.user_id)

        if self.group_id is not None:
            info["gid"] = str(self.group_id)

        if self.required is not None:
            info["required"] = "true" if self.required else "false"

        return info


class MultiLineRunInstruction(Instruction):
    r"""
    Represents a ``RUN`` instruction which will be split across multiple lines.

    :param commands: A list of commands to be run.
    :param mounts: A list of mounts to be used.

    :Example:
        >>> print(MultiLineRunInstruction(
        ...     ["pip install --upgrade pip", "pip install -r requirements.txt"]
        ... ))
        RUN \
            pip install --upgrade pip && \
            pip install -r requirements.txt
        >>> print(MultiLineRunInstruction(
        ...     ["pip install --upgrade pip", "pip install -r requirements.txt"],
        ...     [SecretMount(secret_id="aws", target="/root/.aws/credentials")]
        ... ))
        RUN \
            --mount=type=secret,id=aws,target=/root/.aws/credentials \
            pip install --upgrade pip && \
            pip install -r requirements.txt
    """
    def __init__(self, commands: list[str], mounts: list[Mount] | None = None) -> None:
        self.commands = commands
        self.mounts = mounts or []

    def to_string(self) -> str:
        lines = ["RUN \\"]
        for mount in self.mounts:
            lines.append(f"    {mount.to_string()} \\")
        for command in self.commands[:-1]:
            lines.append(f"    {command} && \\")
        lines.append(f"    {self.commands[-1]}")
        return "\n".join(lines)


class Dockerfile:
    """
    Represents the contents of a Dockerfile.

    :param instruction_groups: A list of lists of instructions or comments. Separation between groups is larger than
                               between instructions within the group to imply sections to the Dockerfile.
    """
    def __init__(self, instruction_groups: list[list[Instruction | Comment]] | None = None) -> None:
        self.instruction_groups = instruction_groups or []

    def new_instruction_group(self, *instructions: Instruction | Comment) -> None:
        """
        Add instructions to a new instruction group within the Dockerfile.

        :param instructions: Instructions or comments to add to the new group.
        """
        self.instruction_groups.append(list(instructions))

    def write_to_file(self, file_path: Path, encoding: str | None = None) -> None:
        """
        Write the contents of the Dockerfile to a path.

        :param file_path: The location to which to write the contents.
        :param encoding: The encoding of the file. Defaults to the system default.
        """
        file_path.write_text(self.to_string(), encoding=encoding)

    def to_string(self) -> str:
        """Return the contents of the Dockerfile."""
        content_lines = []
        for instruction_group in self.instruction_groups:
            for instruction in instruction_group:
                content_lines.append(instruction.to_string())
            content_lines.append("")

        return "\n".join(content_lines)
