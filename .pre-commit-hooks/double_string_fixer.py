"""
A copy of https://github.com/pre-commit/pre-commit-hooks/tree/main#double-quote-string-fixer,
except it replaces single-quoted strings with double-quoted strings.

Copyright (c) 2014 pre-commit dev team: Anthony Sottile, Ken Struys

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in
all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
THE SOFTWARE.
"""
from __future__ import annotations

import argparse
import io
import re
import sys
import tokenize
from typing import Sequence

if sys.version_info >= (3, 12):  # pragma: >=3.12 cover
    FSTRING_START = tokenize.FSTRING_START
    FSTRING_END = tokenize.FSTRING_END
else:  # pragma: <3.12 cover
    FSTRING_START = FSTRING_END = -1

START_QUOTE_RE = re.compile("^[a-zA-Z]*'")


def handle_match(token_text: str) -> str:
    if '"""' in token_text or "'''" in token_text:
        return token_text

    match = START_QUOTE_RE.match(token_text)
    if match is not None:
        meat = token_text[match.end():-1]
        if '"' in meat or "'" in meat:
            return token_text
        else:
            return match.group().replace("'", '"') + meat + '"'
    else:
        return token_text


def get_line_offsets_by_line_no(src: str) -> list[int]:
    # Padded so we can index with line number
    offsets = [-1, 0]
    for line in src.splitlines(True):
        offsets.append(offsets[-1] + len(line))
    return offsets


def fix_strings(filename: str) -> int:
    with open(filename, encoding="UTF-8", newline="") as f:
        contents = f.read()
    line_offsets = get_line_offsets_by_line_no(contents)

    # Basically a mutable string
    splitcontents = list(contents)

    fstring_depth = 0

    # Iterate in reverse so the offsets are always correct
    tokens_l = list(tokenize.generate_tokens(io.StringIO(contents).readline))
    tokens = reversed(tokens_l)
    for token_type, token_text, (srow, scol), (erow, ecol), _ in tokens:
        if token_type == FSTRING_START:  # pragma: >=3.12 cover
            fstring_depth += 1
        elif token_type == FSTRING_END:  # pragma: >=3.12 cover
            fstring_depth -= 1
        elif fstring_depth == 0 and token_type == tokenize.STRING:
            new_text = handle_match(token_text)
            splitcontents[
                line_offsets[srow] + scol:
                line_offsets[erow] + ecol
            ] = new_text

    new_contents = "".join(splitcontents)
    if contents != new_contents:
        with open(filename, "w", encoding="UTF-8", newline="") as f:
            f.write(new_contents)
        return 1
    else:
        return 0


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("filenames", nargs="*", help="Filenames to fix")
    args = parser.parse_args(argv)

    retv = 0

    for filename in args.filenames:
        return_value = fix_strings(filename)
        if return_value != 0:
            print(f"Fixing strings in {filename}")
        retv |= return_value

    return retv


if __name__ == "__main__":
    raise SystemExit(main())
