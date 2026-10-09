#!/usr/bin/env python3
"""Read and write classic Warcraft III war3map.wtg files.

The WTG binary format does not store an ECA's argument count.  A matching
set of World Editor definitions (action.txt, event.txt, condition.txt and
call.txt) is therefore required to parse and write ECA data safely.
"""

from __future__ import annotations

import argparse
import json
import re
import struct
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, Mapping, Sequence


TYPE_EVENT = 0
TYPE_CONDITION = 1
TYPE_ACTION = 2
TYPE_CALL = 3
TYPE_NAMES = {
    TYPE_EVENT: "event",
    TYPE_CONDITION: "condition",
    TYPE_ACTION: "action",
    TYPE_CALL: "call",
}

DEFINITION_FILES = {
    TYPE_EVENT: "event.txt",
    TYPE_CONDITION: "condition.txt",
    TYPE_ACTION: "action.txt",
    TYPE_CALL: "call.txt",
}


class WtgError(Exception):
    """Base exception for WTG parsing and writing errors."""


class WtgParseError(WtgError):
    """Raised when a WTG stream is malformed or lacks a definition."""


class WtgWriteError(WtgError):
    """Raised when a model cannot be serialized safely."""


@dataclass(frozen=True)
class EcaDefinition:
    """Editor metadata needed to locate an ECA's serialized arguments."""

    eca_type: int
    name: str
    arg_types: tuple[str, ...] = ()

    @property
    def stored_arg_types(self) -> tuple[str, ...]:
        return tuple(t for t in self.arg_types if t.lower() != "nothing")

    @property
    def arg_count(self) -> int:
        return len(self.stored_arg_types)


class DefinitionSet:
    """Definitions indexed by (ECA type, editor function name)."""

    def __init__(self, definitions: Iterable[EcaDefinition] = ()) -> None:
        self._items: dict[tuple[int, str], EcaDefinition] = {}
        for definition in definitions:
            self.add(definition)

    def add(self, definition: EcaDefinition) -> None:
        if definition.eca_type not in TYPE_NAMES:
            raise ValueError(f"invalid ECA type: {definition.eca_type}")
        self._items[(definition.eca_type, definition.name)] = definition

    def get(self, eca_type: int, name: str) -> EcaDefinition:
        definition = self._items.get((eca_type, name))
        if definition is not None:
            return definition
        normalized = name.strip()
        if normalized != name:
            definition = self._items.get((eca_type, normalized))
            if definition is not None:
                return definition
        # Older KKWE/YDWE builds serialize action entries as call nodes, and
        # use a padded call wrapper for custom expressions in argument slots.
        if eca_type == TYPE_CALL and not normalized:
            return EcaDefinition(TYPE_CALL, name, ("value",))
        candidates = [item for (kind, item_name), item in self._items.items() if item_name in {name, normalized}]
        if len(candidates) == 1:
            return candidates[0]
        action = self._items.get((TYPE_ACTION, name)) or self._items.get((TYPE_ACTION, normalized))
        if action is not None:
            return action
        kind = TYPE_NAMES.get(eca_type, str(eca_type))
        raise WtgParseError(
            f"missing {kind} definition for ECA {name!r}; "
            "load the matching World Editor definition files"
        )

    @classmethod
    def from_root(cls, root: str | Path) -> "DefinitionSet":
        """Load the four definition files below a share/mpq or UI root."""

        root_path = Path(root)
        definitions: list[EcaDefinition] = []
        for eca_type, filename in DEFINITION_FILES.items():
            paths = _find_definition_files(root_path, filename)
            if not paths:
                raise FileNotFoundError(
                    f"could not find {filename!r} below {root_path}"
                )
            for path in paths:
                definitions.extend(_parse_definition_file(path, eca_type))
        return cls(definitions)

    @classmethod
    def from_counts(
        cls, counts: Mapping[tuple[int, str], int]
    ) -> "DefinitionSet":
        """Build a small definition set for tests or custom extensions."""

        return cls(
            EcaDefinition(eca_type, name, ("value",) * count)
            for (eca_type, name), count in counts.items()
        )


def _find_definition_file(root: Path, filename: str) -> Path | None:
    paths = _find_definition_files(root, filename)
    return paths[0] if paths else None


def _find_definition_files(root: Path, filename: str) -> list[Path]:
    if root.is_file():
        return [root] if root.name.casefold() == filename.casefold() else []
    direct_candidates = (
        root / filename,
        root / "ydwe" / filename,
        root / "common" / filename,
    )
    found = {candidate.resolve() for candidate in direct_candidates if candidate.is_file()}
    found.update(candidate.resolve() for candidate in root.rglob(filename) if candidate.is_file())
    return sorted(found, key=lambda path: str(path).casefold())


_SECTION_RE = re.compile(r'^\[(?:"([^"]+)"|([^\]]+))\]\s*$')
_ARG_RE = re.compile(r"^type\s*=\s*(.*?)\s*$")


def _parse_definition_file(path: Path, eca_type: int) -> list[EcaDefinition]:
    result: list[EcaDefinition] = []
    current_name: str | None = None
    current_args: list[str] = []
    pending_arg = False

    def flush() -> None:
        if current_name is not None:
            result.append(
                EcaDefinition(eca_type, current_name, tuple(current_args))
            )

    text = path.read_text(encoding="utf-8-sig")
    for raw_line in text.splitlines():
        line = raw_line.strip()
        match = _SECTION_RE.match(line)
        if match:
            flush()
            current_name = match.group(1) or match.group(2)
            current_args = []
            pending_arg = False
            continue
        if current_name is None:
            continue
        if line == "[[.args]]":
            current_args.append("nothing")
            pending_arg = True
            continue
        if pending_arg:
            arg_match = _ARG_RE.match(line)
            if arg_match:
                current_args[-1] = arg_match.group(1)
                pending_arg = False
    flush()
    return result


@dataclass
class WtgArgument:
    type: int
    value: str
    call: "WtgEca | None" = None
    call_tail: int = 0
    index: "WtgArgument | None" = None

    def to_dict(self) -> dict:
        result: dict = {"type": self.type, "value": self.value}
        if self.call is not None:
            result["call"] = self.call.to_dict()
            result["call_tail"] = self.call_tail
        if self.index is not None:
            result["index"] = self.index.to_dict()
        return result


@dataclass
class WtgEca:
    type: int
    name: str
    enabled: int = 1
    args: list[WtgArgument] = field(default_factory=list)
    children: list["WtgEca"] = field(default_factory=list)
    child_id: int | None = None

    def to_dict(self) -> dict:
        result: dict = {
            "type": self.type,
            "type_name": TYPE_NAMES.get(self.type, str(self.type)),
            "name": self.name,
            "enabled": self.enabled,
            "args": [arg.to_dict() for arg in self.args],
            "children": [child.to_dict() for child in self.children],
        }
        if self.child_id is not None:
            result["child_id"] = self.child_id
        return result


@dataclass
class WtgCategory:
    id: int
    name: str
    comment: int = 0

    def to_dict(self) -> dict:
        return {"id": self.id, "name": self.name, "comment": self.comment}


@dataclass
class WtgVariable:
    name: str
    type: str
    unknown: int = 1
    is_array: int = 0
    array_size: int = 1
    is_default: int = 0
    value: str = ""

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "type": self.type,
            "unknown": self.unknown,
            "is_array": self.is_array,
            "array_size": self.array_size,
            "is_default": self.is_default,
            "value": self.value,
        }


@dataclass
class WtgTrigger:
    name: str
    description: str = ""
    type: int = 0
    enabled: int = 1
    custom_code: int = 0
    initially_on: int = 0
    run_on_init: int = 0
    category: int = 0
    ecas: list[WtgEca] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "description": self.description,
            "type": self.type,
            "enabled": self.enabled,
            "custom_code": self.custom_code,
            "initially_on": self.initially_on,
            "run_on_init": self.run_on_init,
            "category": self.category,
            "eca_count": len(self.ecas),
            "ecas": [eca.to_dict() for eca in self.ecas],
        }


@dataclass
class WtgFile:
    version: int
    categories: list[WtgCategory]
    variables: list[WtgVariable]
    triggers: list[WtgTrigger]
    unknown: int = 2
    encoding: str = "utf-8"

    def to_dict(self) -> dict:
        return {
            "signature": "WTG!",
            "version": self.version,
            "encoding": self.encoding,
            "category_count": len(self.categories),
            "variable_count": len(self.variables),
            "trigger_count": len(self.triggers),
            "categories": [item.to_dict() for item in self.categories],
            "variables": [item.to_dict() for item in self.variables],
            "triggers": [item.to_dict() for item in self.triggers],
        }

    def find_trigger(self, name: str) -> WtgTrigger:
        for trigger in self.triggers:
            if trigger.name == name:
                return trigger
        raise KeyError(name)

    def find_variable(self, name: str) -> WtgVariable:
        for variable in self.variables:
            if variable.name == name:
                return variable
        raise KeyError(name)


class _Reader:
    def __init__(self, data: bytes, encoding: str) -> None:
        self.data = data
        self.encoding = encoding
        self.offset = 0

    def _require(self, size: int) -> None:
        if self.offset + size > len(self.data):
            raise WtgParseError(
                f"unexpected end of file at offset {self.offset}; need {size} bytes"
            )

    def i32(self) -> int:
        self._require(4)
        value = struct.unpack_from("<i", self.data, self.offset)[0]
        self.offset += 4
        return value

    def u32(self) -> int:
        self._require(4)
        value = struct.unpack_from("<I", self.data, self.offset)[0]
        self.offset += 4
        return value

    def c4(self) -> bytes:
        self._require(4)
        value = self.data[self.offset : self.offset + 4]
        self.offset += 4
        return value

    def z(self) -> str:
        end = self.data.find(b"\0", self.offset)
        if end < 0:
            raise WtgParseError(f"unterminated string at offset {self.offset}")
        raw = self.data[self.offset : end]
        self.offset = end + 1
        try:
            return raw.decode(self.encoding)
        except UnicodeDecodeError as exc:
            raise WtgParseError(
                f"cannot decode string at offset {end - len(raw)} as {self.encoding}"
            ) from exc


class _Writer:
    def __init__(self, encoding: str) -> None:
        self.encoding = encoding
        self.data = bytearray()

    def i32(self, value: int) -> None:
        self.data += struct.pack("<i", int(value))

    def u32(self, value: int) -> None:
        self.data += struct.pack("<I", int(value))

    def c4(self, value: bytes) -> None:
        if len(value) != 4:
            raise WtgWriteError(f"expected 4-byte signature, got {value!r}")
        self.data += value

    def z(self, value: str) -> None:
        if "\0" in value:
            raise WtgWriteError("WTG strings cannot contain NUL characters")
        try:
            self.data += value.encode(self.encoding)
        except UnicodeEncodeError as exc:
            raise WtgWriteError(
                f"cannot encode string {value!r} as {self.encoding}"
            ) from exc
        self.data.append(0)


def _read_argument(reader: _Reader, definitions: DefinitionSet) -> WtgArgument:
    arg_type = reader.i32()
    value = reader.z()
    insert_call = reader.i32()
    if insert_call == 1:
        call = _read_eca(reader, definitions, is_child=False, is_argument=True)
        call_tail = reader.i32()
        return WtgArgument(arg_type, value, call=call, call_tail=call_tail)
    if insert_call != 0:
        raise WtgParseError(
            f"invalid argument call flag {insert_call} at offset {reader.offset - 4}"
        )
    insert_index = reader.i32()
    if insert_index == 1:
        return WtgArgument(arg_type, value, index=_read_argument(reader, definitions))
    if insert_index != 0:
        raise WtgParseError(
            f"invalid argument index flag {insert_index} at offset {reader.offset - 4}"
        )
    return WtgArgument(arg_type, value)


def _read_eca(
    reader: _Reader,
    definitions: DefinitionSet,
    *,
    is_child: bool,
    is_argument: bool = False,
) -> WtgEca:
    eca_type = reader.i32()
    child_id = reader.i32() if is_child else None
    name_offset = reader.offset
    name = reader.z()
    enabled = reader.i32()
    try:
        definition = definitions.get(eca_type, name)
    except WtgParseError as exc:
        raise WtgParseError(f"at offset {name_offset}: {exc}") from exc
    args = [
        _read_argument(reader, definitions)
        for _ in range(definition.arg_count)
    ]
    child_count = reader.i32()
    if child_count < 0:
        raise WtgParseError(f"negative child ECA count for {name!r}")
    children = [
        _read_eca(reader, definitions, is_child=True)
        for _ in range(child_count)
    ]
    return WtgEca(
        type=eca_type,
        name=name,
        enabled=enabled,
        args=args,
        children=children,
        child_id=child_id,
    )


def read_wtg(
    path: str | Path,
    definitions: DefinitionSet,
    *,
    encoding: str = "utf-8",
) -> WtgFile:
    """Read a classic WTG v7 file using editor ECA definitions."""

    data = Path(path).read_bytes()
    reader = _Reader(data, encoding)
    if reader.c4() != b"WTG!":
        raise WtgParseError("missing WTG! signature")
    version = reader.i32()
    if version != 7:
        raise WtgParseError(
            f"unsupported WTG header {version}; this writer targets classic v7"
        )

    category_count = reader.i32()
    if category_count < 0:
        raise WtgParseError("negative category count")
    categories = [
        WtgCategory(reader.i32(), reader.z(), reader.i32())
        for _ in range(category_count)
    ]

    unknown = reader.i32()
    variable_count = reader.i32()
    if variable_count < 0:
        raise WtgParseError("negative variable count")
    variables = [
        WtgVariable(
            name=reader.z(),
            type=reader.z(),
            unknown=reader.i32(),
            is_array=reader.i32(),
            array_size=reader.i32(),
            is_default=reader.i32(),
            value=reader.z(),
        )
        for _ in range(variable_count)
    ]

    trigger_count = reader.i32()
    if trigger_count < 0:
        raise WtgParseError("negative trigger count")
    triggers: list[WtgTrigger] = []
    for _ in range(trigger_count):
        trigger = WtgTrigger(
            name=reader.z(),
            description=reader.z(),
            type=reader.i32(),
            enabled=reader.i32(),
            custom_code=reader.i32(),
            initially_on=reader.i32(),
            run_on_init=reader.i32(),
            category=reader.i32(),
        )
        eca_count = reader.i32()
        if eca_count < 0:
            raise WtgParseError(f"negative ECA count for trigger {trigger.name!r}")
        trigger.ecas = [
            _read_eca(reader, definitions, is_child=False)
            for _ in range(eca_count)
        ]
        triggers.append(trigger)

    if reader.offset != len(data):
        raise WtgParseError(
            f"trailing data after final trigger: {len(data) - reader.offset} bytes"
        )
    return WtgFile(
        version=version,
        categories=categories,
        variables=variables,
        triggers=triggers,
        unknown=unknown,
        encoding=encoding,
    )


def _write_argument(writer: _Writer, argument: WtgArgument, definitions: DefinitionSet) -> None:
    writer.i32(argument.type)
    writer.z(argument.value)
    if argument.call is not None and argument.index is not None:
        raise WtgWriteError("an argument cannot contain both call and index")
    if argument.call is not None:
        writer.i32(1)
        _write_eca(writer, argument.call, definitions, is_child=False)
        writer.i32(argument.call_tail)
        return
    writer.i32(0)
    if argument.index is not None:
        writer.i32(1)
        _write_argument(writer, argument.index, definitions)
    else:
        writer.i32(0)


def _write_eca(
    writer: _Writer,
    eca: WtgEca,
    definitions: DefinitionSet,
    *,
    is_child: bool,
) -> None:
    if eca.type not in TYPE_NAMES:
        raise WtgWriteError(f"invalid ECA type {eca.type} for {eca.name!r}")
    writer.i32(eca.type)
    if is_child:
        if eca.child_id is None:
            raise WtgWriteError(f"child ECA {eca.name!r} has no child_id")
        writer.i32(eca.child_id)
    writer.z(eca.name)
    writer.i32(eca.enabled)
    definition = definitions.get(eca.type, eca.name)
    if len(eca.args) != definition.arg_count:
        raise WtgWriteError(
            f"ECA {eca.name!r} expects {definition.arg_count} args, "
            f"got {len(eca.args)}"
        )
    for argument in eca.args:
        _write_argument(writer, argument, definitions)
    writer.i32(len(eca.children))
    for child in eca.children:
        _write_eca(writer, child, definitions, is_child=True)


def write_wtg(
    path: str | Path,
    wtg: WtgFile,
    definitions: DefinitionSet,
    *,
    encoding: str | None = None,
) -> None:
    """Write a WtgFile as classic WTG v7."""

    if wtg.version != 7:
        raise WtgWriteError(f"unsupported WTG version for writing: {wtg.version}")
    writer = _Writer(encoding or wtg.encoding)
    writer.c4(b"WTG!")
    writer.i32(7)
    writer.i32(len(wtg.categories))
    for category in wtg.categories:
        writer.i32(category.id)
        writer.z(category.name)
        writer.i32(category.comment)
    writer.i32(wtg.unknown)
    writer.i32(len(wtg.variables))
    for variable in wtg.variables:
        writer.z(variable.name)
        writer.z(variable.type)
        writer.i32(variable.unknown)
        writer.i32(variable.is_array)
        writer.i32(variable.array_size)
        writer.i32(variable.is_default)
        writer.z(variable.value)
    writer.i32(len(wtg.triggers))
    for trigger in wtg.triggers:
        writer.z(trigger.name)
        writer.z(trigger.description)
        writer.i32(trigger.type)
        writer.i32(trigger.enabled)
        writer.i32(trigger.custom_code)
        writer.i32(trigger.initially_on)
        writer.i32(trigger.run_on_init)
        writer.i32(trigger.category)
        writer.i32(len(trigger.ecas))
        for eca in trigger.ecas:
            _write_eca(writer, eca, definitions, is_child=False)
    Path(path).write_bytes(writer.data)


def _summary(wtg: WtgFile) -> dict:
    return {
        "signature": "WTG!",
        "version": wtg.version,
        "category_count": len(wtg.categories),
        "variable_count": len(wtg.variables),
        "trigger_count": len(wtg.triggers),
        "categories": [category.name for category in wtg.categories],
        "variables": [variable.name for variable in wtg.variables],
        "triggers": [
            {"name": trigger.name, "eca_count": len(trigger.ecas)}
            for trigger in wtg.triggers
        ],
    }


def _parse_assignment(value: str) -> tuple[str, str]:
    if "=" not in value:
        raise argparse.ArgumentTypeError("expected NAME=VALUE")
    name, new_value = value.split("=", 1)
    if not name:
        raise argparse.ArgumentTypeError("variable name cannot be empty")
    return name, new_value


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path, help="input war3map.wtg")
    parser.add_argument(
        "--ui-root",
        type=Path,
        required=True,
        help="directory containing YDWE/KKWE definition txt files",
    )
    parser.add_argument("--json-out", type=Path, help="write the decoded model as JSON")
    parser.add_argument("--write-out", type=Path, help="write a WTG file to this path")
    parser.add_argument(
        "--set-variable",
        action="append",
        type=_parse_assignment,
        default=[],
        metavar="NAME=VALUE",
        help="change a variable before --write-out; may be repeated",
    )
    args = parser.parse_args(argv)
    try:
        definitions = DefinitionSet.from_root(args.ui_root)
        wtg = read_wtg(args.input, definitions)
        for name, value in args.set_variable:
            wtg.find_variable(name).value = value
            wtg.find_variable(name).is_default = 1
        if args.json_out:
            args.json_out.write_text(
                json.dumps(wtg.to_dict(), ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
        if args.write_out:
            if args.write_out.resolve() == args.input.resolve():
                raise WtgWriteError("refusing to overwrite the input WTG")
            write_wtg(args.write_out, wtg, definitions)
        print(json.dumps(_summary(wtg), ensure_ascii=False, indent=2))
        return 0
    except (OSError, WtgError, KeyError) as exc:
        print(f"wtg_parser: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
