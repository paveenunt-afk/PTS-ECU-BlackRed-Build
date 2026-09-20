from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
import os
import struct
import tempfile


class BinError(Exception):
    pass


class BinBoundsError(BinError):
    pass


@dataclass(frozen=True)
class ChangedRange:
    start: int
    end: int


class BinImage:
    def __init__(self, data: bytes, source_path: Path | None = None):
        self._original = bytes(data)
        self._working = bytearray(data)
        self._saved_snapshot = bytes(data)
        self.source_path = Path(source_path) if source_path else None

    @classmethod
    def from_bytes(cls, data: bytes) -> "BinImage":
        return cls(data)

    @classmethod
    def from_file(cls, path: str | Path) -> "BinImage":
        p = Path(path)
        with p.open("rb") as fh:
            return cls(fh.read(), p)

    @property
    def original_bytes(self) -> bytes:
        return self._original

    @property
    def dirty(self) -> bool:
        return self._working != self._saved_snapshot

    @property
    def size(self) -> int:
        return len(self._working)

    def __len__(self) -> int:
        return self.size

    def to_bytes(self) -> bytes:
        return bytes(self._working)

    def _check(self, address: int, size: int) -> None:
        if address < 0 or size < 0 or address + size > self.size:
            raise BinBoundsError(
                f"Address range 0x{address:X}..0x{address + size - 1:X} exceeds image size 0x{self.size:X}"
            )

    def _read(self, address: int, fmt: str) -> int:
        size = struct.calcsize(fmt)
        self._check(address, size)
        return int(struct.unpack_from(fmt, self._working, address)[0])

    def _write(self, address: int, fmt: str, value: int) -> None:
        size = struct.calcsize(fmt)
        self._check(address, size)
        try:
            struct.pack_into(fmt, self._working, address, int(value))
        except struct.error as exc:
            raise BinError(str(exc)) from exc

    def read_u8(self, address: int) -> int:
        return self._read(address, "B")

    def read_u16_be(self, address: int) -> int:
        return self._read(address, ">H")

    def read_u16_le(self, address: int) -> int:
        return self._read(address, "<H")

    def write_u8(self, address: int, value: int) -> None:
        self._write(address, "B", value)

    def write_u16_be(self, address: int, value: int) -> None:
        self._write(address, ">H", value)

    def write_u16_le(self, address: int, value: int) -> None:
        self._write(address, "<H", value)

    def read_codec(self, address: int, codec: str) -> int:
        table = {"B": self.read_u8, ">H": self.read_u16_be, "<H": self.read_u16_le}
        try:
            return table[codec](address)
        except KeyError as exc:
            raise BinError(f"Unsupported codec: {codec}") from exc

    def write_codec(self, address: int, codec: str, value: int) -> None:
        table = {"B": self.write_u8, ">H": self.write_u16_be, "<H": self.write_u16_le}
        try:
            table[codec](address, value)
        except KeyError as exc:
            raise BinError(f"Unsupported codec: {codec}") from exc

    def changed_ranges(self) -> list[ChangedRange]:
        ranges: list[ChangedRange] = []
        start: int | None = None
        for i, (a, b) in enumerate(zip(self._original, self._working)):
            if a != b and start is None:
                start = i
            elif a == b and start is not None:
                ranges.append(ChangedRange(start, i - 1))
                start = None
        if start is not None:
            ranges.append(ChangedRange(start, self.size - 1))
        return ranges

    def save(self, path: str | Path | None = None, *, backup_existing: bool = False) -> Path:
        target = Path(path) if path is not None else self.source_path
        if target is None:
            raise BinError("No output path supplied")
        target.parent.mkdir(parents=True, exist_ok=True)
        if backup_existing and target.exists():
            stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            target.with_suffix(target.suffix + f".{stamp}.bak").write_bytes(target.read_bytes())
        fd, tmp_name = tempfile.mkstemp(prefix=target.name + ".", suffix=".tmp", dir=str(target.parent))
        try:
            with os.fdopen(fd, "wb") as fh:
                fh.write(self._working)
                fh.flush()
                os.fsync(fh.fileno())
            os.replace(tmp_name, target)
            self._saved_snapshot = bytes(self._working)
            self.source_path = target
        finally:
            if os.path.exists(tmp_name):
                os.unlink(tmp_name)
        return target
