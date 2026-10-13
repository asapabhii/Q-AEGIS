"""Immutable per-access feature bundle for the five scoring agents, ``SPEC.md`` 3.4.

The v1 agents scored only ``{sensitivity_label, risk_value, device_is_new,
after_hours}``, and ``risk_value`` is itself a function of the two booleans
(``app.risk_engine.scorer``), so the whole panel collapsed to ~16 contexts and
the SECURITY and CONTEXTUAL agents merely restated the contextual risk engine.
This module carries the independent, per-access behavioural signals that let each
agent be a genuinely distinct lens.

Discipline that must hold:

* The bundle is computed ONCE, on the request thread that owns the SQLAlchemy
  ``Session`` (:func:`app.db.repositories.risk.access_history`), and frozen onto
  :class:`app.agents.state.AssessmentInput` before the parallel fan-out. Scorers
  never touch the database: the ``Session`` is request-thread-bound and unsafe
  inside the ``ThreadPoolExecutor`` workers, and the per-agent timeout only stays
  a real bound if each worker is a fast pure function over this frozen bundle.
* Neutral defaults make the bundle optional. A freshly deployed system, a unit
  test, or any ``AssessmentInput`` built without history gets a well-defined
  "first-contact" bundle (no known history), which the scorers read as ambiguity
  and resolve toward more protection, per the fail-safe posture.
* Every history count EXCLUDES the current access: ``access_history`` runs before
  the new ``risk_scores`` row is appended.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from enum import Enum
from typing import Any

_ZERO = Decimal("0")


class DataLongevity(str, Enum):
    """How long the content is likely to remain sensitive (quantum HNDL lens).

    Derived only from the file-name suffix — a closed, inline set of file-type
    extensions, never sourced from classifier data or keyword lists.
    """

    LONG = "long-lived"
    MEDIUM = "medium-lived"
    SHORT = "short-lived"


class PayloadCost(str, Enum):
    """Relative protection/storage cost implied by the content type."""

    HEAVY = "heavy"
    MEDIUM = "medium"
    LIGHT = "light"


#: Archives, database dumps, key material and backups stay decryption-worthy for
#: years, so they carry the most harvest-now-decrypt-later exposure. File-type
#: extensions only — never keyword or classifier-derived.
_LONG_LIVED_SUFFIXES = frozenset(
    {
        "zip",
        "tar",
        "gz",
        "tgz",
        "7z",
        "rar",
        "bz2",
        "bak",
        "backup",
        "dump",
        "db",
        "sql",
        "sqlite",
        "mdb",
        "pem",
        "key",
        "pfx",
        "p12",
        "kdbx",
        "pst",
        "parquet",
    }
)

#: Transient artefacts with little long-horizon exposure.
_SHORT_LIVED_SUFFIXES = frozenset({"log", "tmp", "temp", "cache", "swp", "part"})

#: Large / poorly compressible content is heavier to protect and store.
_HEAVY_SUFFIXES = frozenset(
    {
        "zip",
        "tar",
        "gz",
        "tgz",
        "7z",
        "rar",
        "bz2",
        "iso",
        "dump",
        "db",
        "sqlite",
        "parquet",
        "mp4",
        "mov",
        "avi",
        "mkv",
        "png",
        "jpg",
        "jpeg",
        "tiff",
        "bmp",
        "psd",
        "pdf",
    }
)

#: Small, highly compressible plain-text content is the lightest path.
_LIGHT_SUFFIXES = frozenset(
    {"txt", "md", "json", "csv", "log", "html", "htm", "xml", "yaml", "yml", "ini"}
)


def _suffix(filename: str) -> str:
    """Lower-cased final extension of ``filename`` (empty string if none)."""
    name = filename.strip().lower()
    dot = name.rfind(".")
    if dot <= 0 or dot == len(name) - 1:
        return ""
    return name[dot + 1 :]


def data_longevity(filename: str) -> DataLongevity:
    """Classify content longevity from the file-name suffix (closed map)."""
    suffix = _suffix(filename)
    if suffix in _LONG_LIVED_SUFFIXES:
        return DataLongevity.LONG
    if suffix in _SHORT_LIVED_SUFFIXES:
        return DataLongevity.SHORT
    return DataLongevity.MEDIUM


def payload_cost_class(filename: str) -> PayloadCost:
    """Classify protection/storage cost from the file-name suffix (closed map)."""
    suffix = _suffix(filename)
    if suffix in _HEAVY_SUFFIXES:
        return PayloadCost.HEAVY
    if suffix in _LIGHT_SUFFIXES:
        return PayloadCost.LIGHT
    return PayloadCost.MEDIUM


@dataclass(frozen=True)
class AccessFeatures:
    """Frozen, JSON-serialisable per-access signals (see the module docstring).

    All fields default to a conservative "first-contact" bundle so the type is
    optional at every ``AssessmentInput`` construction site that has no history.
    Counts exclude the current access.
    """

    actor_prior_access_count: int = 0
    actor_device_prior_count: int = 0
    actor_after_hours_count: int = 0
    device_distinct_actor_count: int = 0
    document_prior_access_count: int = 0
    document_prior_risk_value: Decimal | None = None
    actor_role: str | None = None
    payload_byte_size: int | None = None

    @property
    def actor_is_known(self) -> bool:
        """The actor has at least one prior recorded access anywhere."""
        return self.actor_prior_access_count > 0

    @property
    def device_known_to_actor(self) -> bool:
        """This actor has used this device before."""
        return self.actor_device_prior_count > 0

    @property
    def device_is_shared(self) -> bool:
        """The device has been seen with more than one distinct actor."""
        return self.device_distinct_actor_count > 1

    @property
    def actor_after_hours_ratio(self) -> Decimal:
        """Share of the actor's prior accesses that were after-hours (baseline).

        Zero for a first-contact actor, so scorers treat an unknown actor's
        after-hours access as a deviation rather than an established pattern.
        """
        if self.actor_prior_access_count <= 0:
            return _ZERO
        return Decimal(self.actor_after_hours_count) / Decimal(
            self.actor_prior_access_count
        )

    def as_json(self) -> dict[str, Any]:
        """Primitive dict for LangGraph state transport (``Decimal`` -> str)."""
        prior = self.document_prior_risk_value
        return {
            "actor_prior_access_count": self.actor_prior_access_count,
            "actor_device_prior_count": self.actor_device_prior_count,
            "actor_after_hours_count": self.actor_after_hours_count,
            "device_distinct_actor_count": self.device_distinct_actor_count,
            "document_prior_access_count": self.document_prior_access_count,
            "document_prior_risk_value": None if prior is None else str(prior),
            "actor_role": self.actor_role,
            "payload_byte_size": self.payload_byte_size,
        }

    @classmethod
    def from_json(cls, data: dict[str, Any]) -> "AccessFeatures":
        """Rebuild from :meth:`as_json` output (str -> ``Decimal``)."""
        prior = data.get("document_prior_risk_value")
        return cls(
            actor_prior_access_count=int(data.get("actor_prior_access_count", 0)),
            actor_device_prior_count=int(data.get("actor_device_prior_count", 0)),
            actor_after_hours_count=int(data.get("actor_after_hours_count", 0)),
            device_distinct_actor_count=int(data.get("device_distinct_actor_count", 0)),
            document_prior_access_count=int(data.get("document_prior_access_count", 0)),
            document_prior_risk_value=(None if prior is None else Decimal(str(prior))),
            actor_role=data.get("actor_role"),
            payload_byte_size=data.get("payload_byte_size"),
        )
