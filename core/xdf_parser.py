from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import re
import xml.etree.ElementTree as ET


class XdfParseError(ValueError):
    pass


@dataclass
class AxisDefinition:
    mode: str = "static"  # static | linked
    values: list[float] = field(default_factory=list)
    count: int = 0
    address: int | None = None
    codec: str = "B"
    math: str = "X"
    units: str = ""
    name: str = ""


@dataclass
class TableDefinition:
    name: str
    address: int
    rows: int
    columns: int
    codec: str = "B"
    display_math: str = "X"
    inverse_math: str | None = None
    row_axis: AxisDefinition = field(default_factory=AxisDefinition)
    column_axis: AxisDefinition = field(default_factory=AxisDefinition)
    units: str = ""
    description: str = ""
    category: str = ""
    minimum: float | None = None
    maximum: float | None = None
    unique_id: str | None = None

    @property
    def element_size(self) -> int:
        return 1 if self.codec == "B" else 2


@dataclass
class XdfDocument:
    tables: list[TableDefinition] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    source_path: Path | None = None


def _tag(el: ET.Element) -> str:
    return el.tag.rsplit("}", 1)[-1].upper()


def _children(el: ET.Element, name: str) -> list[ET.Element]:
    wanted = name.upper()
    return [c for c in list(el) if _tag(c) == wanted]


def _child(el: ET.Element, *names: str) -> ET.Element | None:
    wanted = {n.upper() for n in names}
    for c in list(el):
        if _tag(c) in wanted:
            return c
    return None


def _text(el: ET.Element, *names: str, default: str = "") -> str:
    child = _child(el, *names)
    if child is not None and child.text:
        return child.text.strip()
    for name in names:
        for key, value in el.attrib.items():
            if key.lower() == name.lower():
                return str(value).strip()
    return default


def _attr(el: ET.Element | None, *names: str, default: str | None = None) -> str | None:
    if el is None:
        return default
    for name in names:
        for key, value in el.attrib.items():
            if key.lower() == name.lower():
                return str(value)
    return default


def _parse_int(value: str | int | None, default: int = 0) -> int:
    if value is None or value == "":
        return default
    if isinstance(value, int):
        return value
    text = str(value).strip()
    try:
        return int(text, 0)
    except ValueError:
        # Some XDFs use raw hexadecimal without 0x prefix.
        if re.fullmatch(r"[0-9A-Fa-f]+", text):
            return int(text, 16)
        raise XdfParseError(f"Invalid integer value: {value}")


def _parse_float(value: str | None) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except ValueError as exc:
        raise XdfParseError(f"Invalid numeric value: {value}") from exc


def _codec_from_embedded(el: ET.Element | None) -> str:
    if el is None:
        return "B"
    bits = _parse_int(_attr(el, "mmedelementsizebits", "elementsizebits", "bits", default="8"), 8)
    order = (_attr(el, "byteorder", "endian", default="big") or "big").lower()
    if bits <= 8:
        return "B"
    if bits <= 16:
        return "<H" if order in {"little", "le", "lsb", "0"} else ">H"
    raise XdfParseError(f"Unsupported element size: {bits} bits")


def _math_expression(parent: ET.Element) -> tuple[str, str | None]:
    math_el = _child(parent, "MATH", "math")
    if math_el is None:
        expression = _attr(parent, "equation", "math", default="X") or "X"
        inverse = _attr(parent, "inverse", "inversemath")
        return expression, inverse
    expression = _attr(math_el, "equation", "formula", default=None)
    if not expression:
        expression = (math_el.text or "X").strip() or "X"
    inverse_el = _child(math_el, "INVERSE", "INVERSEMATH")
    inverse = None
    if inverse_el is not None:
        inverse = _attr(inverse_el, "equation", "formula", default=None) or (inverse_el.text or "").strip() or None
    if inverse is None:
        inverse = _attr(math_el, "inverse", "inversemath")
    return expression, inverse


def _parse_axis(axis_el: ET.Element | None, default_count: int = 1) -> AxisDefinition:
    if axis_el is None:
        return AxisDefinition(mode="static", values=[float(i) for i in range(default_count)], count=default_count)
    axis_id = (_attr(axis_el, "id", "name", default="") or "").lower()
    count = _parse_int(_text(axis_el, "indexcount", "count", default=str(default_count)), default_count)
    units = _text(axis_el, "units", default="")
    labels: list[tuple[int, float]] = []
    for label in _children(axis_el, "LABEL"):
        value = _attr(label, "value", "label", default=None)
        if value is None and label.text:
            value = label.text.strip()
        if value is not None:
            index = _parse_int(_attr(label, "index", default=str(len(labels))), len(labels))
            labels.append((index, float(value)))
    if labels:
        labels.sort(key=lambda x: x[0])
        values = [v for _, v in labels]
        return AxisDefinition(mode="static", values=values, count=len(values), units=units, name=axis_id)
    values_el = _child(axis_el, "VALUES")
    if values_el is not None and (values_el.text or "").strip():
        values = [float(x) for x in re.split(r"[,;\s]+", (values_el.text or "").strip()) if x]
        return AxisDefinition(mode="static", values=values, count=len(values), units=units, name=axis_id)
    embedded = _child(axis_el, "EMBEDDEDDATA", "DATA")
    if embedded is not None:
        address = _parse_int(_attr(embedded, "mmedaddress", "address", "offset"), 0)
        expression, _ = _math_expression(axis_el)
        return AxisDefinition(
            mode="linked",
            count=count,
            address=address,
            codec=_codec_from_embedded(embedded),
            math=expression,
            units=units,
            name=axis_id,
        )
    return AxisDefinition(mode="static", values=[float(i) for i in range(count)], count=count, units=units, name=axis_id)


def _parse_table(el: ET.Element, warnings: list[str]) -> TableDefinition:
    name = _text(el, "title", "name", default="Unnamed Table")
    description = _text(el, "description", default="")
    category = _text(el, "category", default="")

    axes = _children(el, "XDFAXIS") + _children(el, "AXIS")
    row_axis_el = None
    col_axis_el = None
    data_axis_el = None
    for axis in axes:
        axis_id = (_attr(axis, "id", "name", default="") or "").lower()
        if axis_id in {"z", "data", "value", "values"} and data_axis_el is None:
            data_axis_el = axis
        elif axis_id in {"y", "row", "rows", "rpm"} and row_axis_el is None:
            row_axis_el = axis
        elif axis_id in {"x", "column", "columns", "col", "tps"} and col_axis_el is None:
            col_axis_el = axis
    if col_axis_el is None and axes:
        col_axis_el = next((axis for axis in axes if axis is not data_axis_el), None)
    if row_axis_el is None:
        remaining = [axis for axis in axes if axis is not data_axis_el and axis is not col_axis_el]
        if remaining:
            row_axis_el = remaining[0]

    # TunerPro 1.50/1.60 commonly stores the table payload in XDFAXIS id="z".
    # Simpler/custom XDFs may put EMBEDDEDDATA directly under XDFTABLE.
    direct_embedded = _child(el, "EMBEDDEDDATA", "DATA")
    z_embedded = _child(data_axis_el, "EMBEDDEDDATA", "DATA") if data_axis_el is not None else None
    embedded = direct_embedded if direct_embedded is not None else z_embedded
    if embedded is not None:
        address = _parse_int(_attr(embedded, "mmedaddress", "address", "offset"), 0)
        codec = _codec_from_embedded(embedded)
    else:
        address = _parse_int(_attr(el, "address", "offset", default="0"), 0)
        bits = _parse_int(_attr(el, "bits", "elementbits", default="8"), 8)
        endian = (_attr(el, "endian", default="big") or "big").lower()
        codec = "B" if bits <= 8 else ("<H" if endian in {"little", "le"} else ">H")

    explicit_rows = _parse_int(_attr(el, "rows", default="0"), 0)
    explicit_cols = _parse_int(_attr(el, "columns", "cols", default="0"), 0)
    if embedded is not None:
        explicit_rows = explicit_rows or _parse_int(_attr(embedded, "mmedrowcount", "rowcount", "rows", default="0"), 0)
        explicit_cols = explicit_cols or _parse_int(_attr(embedded, "mmedcolcount", "colcount", "columns", "cols", default="0"), 0)

    column_axis = _parse_axis(col_axis_el, explicit_cols or 1)
    row_axis = _parse_axis(row_axis_el, explicit_rows or 1)
    columns = explicit_cols or column_axis.count or len(column_axis.values) or 1
    rows = explicit_rows or row_axis.count or len(row_axis.values) or 1

    math_parent = el
    if _child(el, "MATH") is None and data_axis_el is not None and _child(data_axis_el, "MATH") is not None:
        math_parent = data_axis_el
    display_math, inverse_math = _math_expression(math_parent)

    units = _text(el, "units", default="")
    if not units and data_axis_el is not None:
        units = _text(data_axis_el, "units", default="")

    min_text = _text(el, "min", "minimum", default="")
    max_text = _text(el, "max", "maximum", default="")
    if data_axis_el is not None:
        if not min_text:
            min_text = _text(data_axis_el, "min", "minimum", default="")
        if not max_text:
            max_text = _text(data_axis_el, "max", "maximum", default="")

    known = {
        "TITLE", "NAME", "DESCRIPTION", "CATEGORY", "CATEGORYMEM", "UNITS",
        "EMBEDDEDDATA", "DATA", "MATH", "XDFAXIS", "AXIS",
        "MIN", "MAX", "MINIMUM", "MAXIMUM",
    }
    for child in list(el):
        if _tag(child) not in known:
            warnings.append(f"Table '{name}': unsupported tag <{_tag(child)}>")

    return TableDefinition(
        name=name,
        address=address,
        rows=rows,
        columns=columns,
        codec=codec,
        display_math=display_math,
        inverse_math=inverse_math,
        row_axis=row_axis,
        column_axis=column_axis,
        units=units,
        description=description,
        category=category,
        minimum=_parse_float(min_text),
        maximum=_parse_float(max_text),
        unique_id=_attr(el, "uniqueid", "id"),
    )


def _document_from_root(root: ET.Element) -> XdfDocument:
    warnings: list[str] = []
    table_elements = [el for el in root.iter() if _tag(el) in {"XDFTABLE", "TABLE"}]
    tables: list[TableDefinition] = []
    for el in table_elements:
        try:
            tables.append(_parse_table(el, warnings))
        except XdfParseError as exc:
            warnings.append(f"Skipped table: {exc}")
    if not tables:
        warnings.append("No supported table definitions found")
    return XdfDocument(tables=tables, warnings=warnings)


def parse_xdf_text(text: str) -> XdfDocument:
    try:
        root = ET.fromstring(text)
    except ET.ParseError as exc:
        raise XdfParseError(f"Malformed XDF/XML: {exc}") from exc
    return _document_from_root(root)


def parse_xdf_bytes(data: bytes) -> XdfDocument:
    if not data:
        raise XdfParseError("Malformed XDF/XML: file is empty")
    try:
        # Passing raw bytes lets ElementTree honor the XML declaration and
        # BOM itself (UTF-8, UTF-16 LE/BE and other declared encodings).
        root = ET.fromstring(data)
    except ET.ParseError as exc:
        raise XdfParseError(f"Malformed XDF/XML: {exc}") from exc
    return _document_from_root(root)


def parse_xdf(path: str | Path) -> XdfDocument:
    p = Path(path)
    try:
        data = p.read_bytes()
    except OSError as exc:
        raise XdfParseError(f"Unable to read XDF file: {exc}") from exc
    doc = parse_xdf_bytes(data)
    doc.source_path = p
    return doc
