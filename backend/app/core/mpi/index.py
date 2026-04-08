"""
Master Patient Index — almacena y busca pacientes con matching.

Mantiene un índice in-memory (para MVP) con:
  - Add patient: registrar nuevo paciente
  - Search: buscar matches contra el índice
  - Link: vincular dos registros como el mismo paciente
  - Merge: fusionar registros duplicados
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Optional

import structlog

from .matcher import PatientMatcher, PatientRecord, MatchResult, MatchScore

logger = structlog.get_logger()


@dataclass
class MPIEntry:
    """Entrada en el Master Patient Index."""
    mpi_id: str  # MPI universal ID
    records: list[PatientRecord] = field(default_factory=list)
    source_ids: dict[str, str] = field(default_factory=dict)  # source_system -> local_id
    is_active: bool = True


class MasterPatientIndex:
    """Master Patient Index con matching determinístico + probabilístico."""

    def __init__(self, matcher: Optional[PatientMatcher] = None):
        self._matcher = matcher or PatientMatcher()
        self._entries: dict[str, MPIEntry] = {}  # mpi_id -> entry
        self._id_index: dict[str, str] = {}  # "type:value" -> mpi_id (fast lookup)

    @property
    def count(self) -> int:
        return len(self._entries)

    def add_patient(
        self, record: PatientRecord, source_system: str = "unknown"
    ) -> tuple[str, list[MatchResult]]:
        """Agregar paciente al MPI.

        1. Busca matches contra el índice
        2. Si hay match definite → vincula al existente
        3. Si hay match probable → retorna para review
        4. Si no hay match → crea nueva entrada

        Returns:
            (mpi_id, list of match results)
        """
        matches = self.search(record)

        # Check for definite match
        for match_result, entry in matches:
            if match_result.level == MatchScore.definite:
                # Auto-link
                entry.records.append(record)
                for id_type, id_value in record.identifiers.items():
                    self._id_index[f"{id_type}:{id_value}"] = entry.mpi_id
                    entry.source_ids[source_system] = id_value

                logger.info(
                    "mpi_auto_linked",
                    mpi_id=entry.mpi_id,
                    score=match_result.score,
                    fields=match_result.matched_fields,
                )
                return entry.mpi_id, [match_result]

        # No definite match → create new entry
        mpi_id = str(uuid.uuid4())
        entry = MPIEntry(
            mpi_id=mpi_id,
            records=[record],
        )
        for id_type, id_value in record.identifiers.items():
            if id_value:
                self._id_index[f"{id_type}:{id_value}"] = mpi_id
                entry.source_ids[source_system] = id_value

        self._entries[mpi_id] = entry

        logger.info(
            "mpi_new_patient",
            mpi_id=mpi_id,
            probable_matches=sum(1 for m, _ in matches if m.level == MatchScore.probable),
        )

        return mpi_id, [m for m, _ in matches]

    def search(self, record: PatientRecord, limit: int = 10) -> list[tuple[MatchResult, MPIEntry]]:
        """Buscar matches en el índice.

        Returns:
            Lista de (MatchResult, MPIEntry) ordenada por score descendente.
        """
        results = []

        # Fast path: check identifier index
        for id_type, id_value in record.identifiers.items():
            key = f"{id_type}:{id_value}"
            if key in self._id_index:
                mpi_id = self._id_index[key]
                entry = self._entries.get(mpi_id)
                if entry and entry.is_active:
                    result = MatchResult(
                        score=1.0,
                        level=MatchScore.definite,
                        matched_fields=[f"identifier:{id_type}"],
                    )
                    return [(result, entry)]

        # Slow path: compare against all entries
        for entry in self._entries.values():
            if not entry.is_active:
                continue
            # Compare against the first (canonical) record
            if entry.records:
                result = self._matcher.match(record, entry.records[0])
                if result.level != MatchScore.no_match:
                    results.append((result, entry))

        # Sort by score descending
        results.sort(key=lambda x: x[0].score, reverse=True)
        return results[:limit]

    def get(self, mpi_id: str) -> Optional[MPIEntry]:
        """Obtener entrada por MPI ID."""
        return self._entries.get(mpi_id)

    def lookup_by_identifier(self, id_type: str, id_value: str) -> Optional[MPIEntry]:
        """Buscar por identificador exacto."""
        key = f"{id_type}:{id_value}"
        mpi_id = self._id_index.get(key)
        if mpi_id:
            return self._entries.get(mpi_id)
        return None

    def merge(self, surviving_id: str, retiring_id: str) -> bool:
        """Fusionar dos entradas MPI (merge duplicados).

        El surviving_id absorbe los records del retiring_id.
        """
        surviving = self._entries.get(surviving_id)
        retiring = self._entries.get(retiring_id)
        if not surviving or not retiring:
            return False

        # Move records
        surviving.records.extend(retiring.records)
        surviving.source_ids.update(retiring.source_ids)

        # Update index
        for key, mpi_id in list(self._id_index.items()):
            if mpi_id == retiring_id:
                self._id_index[key] = surviving_id

        # Deactivate retiring
        retiring.is_active = False

        logger.info("mpi_merged", surviving=surviving_id, retired=retiring_id)
        return True

    def get_stats(self) -> dict:
        """Estadísticas del MPI."""
        active = sum(1 for e in self._entries.values() if e.is_active)
        return {
            "total_entries": len(self._entries),
            "active_entries": active,
            "indexed_ids": len(self._id_index),
        }
