"""
HL7 v2.x ER7 Parser — schema-free, preserva Z-segments.

Diseñado desde la experiencia real de UC CHRISTUS donde:
- GetValueAt falla sin EVN segment (SAP messages)
- SetValueAt falla después de DTL reimport
- Z-segments deben preservarse en tránsito
- Multi-OBR/OBX/FT1 son comunes

Este parser trabaja con strings crudos ($PIECE-style) sin depender de schemas.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


SEGMENT_SEPARATOR = "\r"
DEFAULT_FIELD_SEP = "|"
DEFAULT_ENCODING_CHARS = "^~\\&"


@dataclass
class HL7Segment:
    """Un segmento HL7 (PID, PV1, OBR, etc.)."""

    name: str
    fields: list[str]
    _field_sep: str = DEFAULT_FIELD_SEP
    _comp_sep: str = "^"
    _rep_sep: str = "~"
    _esc_char: str = "\\"
    _sub_sep: str = "&"

    def get_field(self, index: int) -> str:
        """Obtener campo por índice (1-based, como HL7 spec).

        PID.3 → get_field(3)
        Para MSH, MSH.1 = field separator, MSH.2 = encoding chars.
        """
        if self.name == "MSH":
            if index == 1:
                return self._field_sep
            if index == 2:
                return f"{self._comp_sep}{self._rep_sep}{self._esc_char}{self._sub_sep}"
            # MSH: fields[0]=encoding_chars(MSH.2), fields[1]=MSH.3, ...
            # So MSH.N → fields[N-2] for N>=3
            actual_index = index - 2
        else:
            # Non-MSH: fields[0]=SEG.1, fields[1]=SEG.2, ...
            # So SEG.N → fields[N-1]
            actual_index = index - 1

        if 0 <= actual_index < len(self.fields):
            return self.fields[actual_index]
        return ""

    def get_component(self, field_index: int, comp_index: int) -> str:
        """Obtener componente. PID.3.1 → get_component(3, 1)."""
        field_val = self.get_field(field_index)
        parts = field_val.split(self._comp_sep)
        if 1 <= comp_index <= len(parts):
            return parts[comp_index - 1]
        return ""

    def get_subcomponent(self, field_index: int, comp_index: int, sub_index: int) -> str:
        """Obtener subcomponente. PID.3.1.2 → get_subcomponent(3, 1, 2)."""
        comp_val = self.get_component(field_index, comp_index)
        parts = comp_val.split(self._sub_sep)
        if 1 <= sub_index <= len(parts):
            return parts[sub_index - 1]
        return ""

    def get_repetition(self, field_index: int, rep_index: int = 0) -> str:
        """Obtener repetición. PID.3(2) → get_repetition(3, 1)."""
        field_val = self.get_field(field_index)
        parts = field_val.split(self._rep_sep)
        if 0 <= rep_index < len(parts):
            return parts[rep_index]
        return ""

    def set_field(self, index: int, value: str) -> None:
        """Modificar un campo."""
        if self.name == "MSH":
            actual_index = index - 2
        else:
            actual_index = index - 1
        while len(self.fields) <= actual_index:
            self.fields.append("")
        self.fields[actual_index] = value

    def to_er7(self) -> str:
        """Serializar segmento a ER7."""
        if self.name == "MSH":
            # MSH.1 is the field separator, MSH.2 is encoding chars
            # fields[0] = encoding_chars, fields[1:] = MSH.3+
            return self.name + self._field_sep + self._field_sep.join(self.fields)
        return self.name + self._field_sep + self._field_sep.join(self.fields)

    @property
    def field_count(self) -> int:
        return len(self.fields)


@dataclass
class HL7Message:
    """Mensaje HL7 v2.x parseado desde ER7.

    Acceso a campos:
        msg.get("MSH-9")     → "ADT^A08"
        msg.get("PID-3.1")   → "PAC123"
        msg.get("PID-5.1")   → "APELLIDO"
        msg.get("OBR-4", 1)  → segundo OBR campo 4
    """

    raw: str
    segments: list[HL7Segment] = field(default_factory=list)
    _field_sep: str = DEFAULT_FIELD_SEP
    _encoding_chars: str = DEFAULT_ENCODING_CHARS

    @classmethod
    def parse(cls, raw: str) -> HL7Message:
        """Parsear mensaje HL7 desde string ER7."""
        # Normalize line endings: LF→CR, CRLF→CR, strip empty
        normalized = raw.replace("\r\n", "\r").replace("\n", "\r")
        # Remove trailing CRs and whitespace
        normalized = normalized.strip()
        # Remove duplicate CRs
        while "\r\r" in normalized:
            normalized = normalized.replace("\r\r", "\r")

        lines = [line for line in normalized.split("\r") if line.strip()]
        if not lines:
            raise ValueError("Empty HL7 message")

        # Parse MSH to get delimiters
        first_line = lines[0]
        if not first_line.startswith("MSH"):
            raise ValueError(f"HL7 message must start with MSH, got: {first_line[:10]}")

        field_sep = first_line[3]  # Character after "MSH"
        encoding_chars = first_line[4:8] if len(first_line) >= 8 else DEFAULT_ENCODING_CHARS
        comp_sep = encoding_chars[0] if len(encoding_chars) > 0 else "^"
        rep_sep = encoding_chars[1] if len(encoding_chars) > 1 else "~"
        esc_char = encoding_chars[2] if len(encoding_chars) > 2 else "\\"
        sub_sep = encoding_chars[3] if len(encoding_chars) > 3 else "&"

        msg = cls(raw=raw, _field_sep=field_sep, _encoding_chars=encoding_chars)

        for line in lines:
            seg_name = line[:3]
            if seg_name == "MSH":
                # MSH is special: field[0] = encoding chars, field[1:] = MSH.3+
                parts = line.split(field_sep)
                # parts[0] = "MSH", parts[1] = encoding chars, parts[2:] = fields 3+
                fields = parts[1:]  # encoding_chars + MSH.3+
            else:
                parts = line.split(field_sep)
                # parts[0] = segment name, parts[1:] = fields
                fields = parts[1:]

            segment = HL7Segment(
                name=seg_name,
                fields=fields,
                _field_sep=field_sep,
                _comp_sep=comp_sep,
                _rep_sep=rep_sep,
                _esc_char=esc_char,
                _sub_sep=sub_sep,
            )
            msg.segments.append(segment)

        return msg

    def get_segment(self, name: str, index: int = 0) -> Optional[HL7Segment]:
        """Obtener segmento por nombre. index para segmentos repetidos (OBR, OBX, FT1)."""
        count = 0
        for seg in self.segments:
            if seg.name == name:
                if count == index:
                    return seg
                count += 1
        return None

    def get_all_segments(self, name: str) -> list[HL7Segment]:
        """Obtener todos los segmentos de un tipo."""
        return [seg for seg in self.segments if seg.name == name]

    def count_segments(self, name: str) -> int:
        """Contar segmentos de un tipo (para multi-OBR, multi-FT1, etc.)."""
        return sum(1 for seg in self.segments if seg.name == name)

    def get(self, path: str, segment_index: int = 0) -> str:
        """Acceso universal a campos HL7.

        Formatos soportados:
            "PID-3"       → campo 3 del PID
            "PID-3.1"     → componente 1 del campo 3 del PID
            "PID-3.1.2"   → subcomponente 2 del componente 1 del campo 3
            "PID:3.1"     → formato IRIS (: en vez de -)
            "OBR-4"       → campo 4 del primer OBR (segment_index=0)
        """
        # Normalize separators
        path = path.replace(":", "-")

        # Parse path: SEGMENT-FIELD.COMPONENT.SUBCOMPONENT
        match = re.match(r"^([A-Z][A-Z0-9]{2})-(\d+)(?:\.(\d+))?(?:\.(\d+))?$", path)
        if not match:
            raise ValueError(f"Invalid HL7 path: {path}. Expected format: SEG-N or SEG-N.N or SEG-N.N.N")

        seg_name = match.group(1)
        field_idx = int(match.group(2))
        comp_idx = int(match.group(3)) if match.group(3) else None
        sub_idx = int(match.group(4)) if match.group(4) else None

        segment = self.get_segment(seg_name, segment_index)
        if segment is None:
            return ""

        if sub_idx is not None and comp_idx is not None:
            return segment.get_subcomponent(field_idx, comp_idx, sub_idx)
        elif comp_idx is not None:
            return segment.get_component(field_idx, comp_idx)
        else:
            return segment.get_field(field_idx)

    def set(self, path: str, value: str, segment_index: int = 0) -> None:
        """Modificar un campo. Solo modifica el campo completo por ahora."""
        path = path.replace(":", "-")
        match = re.match(r"^([A-Z][A-Z0-9]{2})-(\d+)$", path)
        if not match:
            raise ValueError(f"set() only supports SEG-N format for now: {path}")

        seg_name = match.group(1)
        field_idx = int(match.group(2))

        segment = self.get_segment(seg_name, segment_index)
        if segment is None:
            raise ValueError(f"Segment {seg_name} not found")

        segment.set_field(field_idx, value)

    @property
    def msh(self) -> Optional[HL7Segment]:
        """Acceso rápido al MSH."""
        return self.get_segment("MSH")

    @property
    def message_type(self) -> str:
        """MSH.9 — e.g. 'ADT^A08'."""
        return self.get("MSH-9")

    @property
    def message_type_code(self) -> str:
        """Primer componente de MSH.9 — e.g. 'ADT'."""
        return self.get("MSH-9.1")

    @property
    def trigger_event(self) -> str:
        """Segundo componente de MSH.9 — e.g. 'A08'."""
        return self.get("MSH-9.2")

    @property
    def message_control_id(self) -> str:
        """MSH.10 — ID único del mensaje."""
        return self.get("MSH-10")

    @property
    def sending_application(self) -> str:
        """MSH.3 — aplicación que envía."""
        return self.get("MSH-3")

    @property
    def sending_facility(self) -> str:
        """MSH.4 — facilidad que envía."""
        return self.get("MSH-4")

    @property
    def receiving_application(self) -> str:
        """MSH.5 — aplicación que recibe."""
        return self.get("MSH-5")

    @property
    def receiving_facility(self) -> str:
        """MSH.6 — facilidad que recibe."""
        return self.get("MSH-6")

    @property
    def version(self) -> str:
        """MSH.12 — versión HL7."""
        return self.get("MSH-12")

    @property
    def timestamp(self) -> str:
        """MSH.7 — timestamp del mensaje."""
        return self.get("MSH-7")

    def to_er7(self) -> str:
        """Serializar mensaje completo a ER7."""
        return SEGMENT_SEPARATOR.join(seg.to_er7() for seg in self.segments)

    def clone(self) -> HL7Message:
        """Crear copia profunda del mensaje."""
        return HL7Message.parse(self.to_er7())

    def add_segment(self, segment: HL7Segment, after: Optional[str] = None) -> None:
        """Agregar segmento al mensaje. Si after="PID", agrega después del PID."""
        if after:
            for i, seg in enumerate(self.segments):
                if seg.name == after:
                    self.segments.insert(i + 1, segment)
                    return
        self.segments.append(segment)

    def remove_segment(self, name: str, index: int = 0) -> bool:
        """Eliminar segmento por nombre e índice."""
        count = 0
        for i, seg in enumerate(self.segments):
            if seg.name == name:
                if count == index:
                    self.segments.pop(i)
                    return True
                count += 1
        return False

    def __repr__(self) -> str:
        return f"HL7Message(type={self.message_type}, id={self.message_control_id}, segments={len(self.segments)})"
