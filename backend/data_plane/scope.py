"""OwnerScope value object: identifies who owns a data-plane resource."""
from __future__ import annotations

from typing import Literal


_VALID_KINDS = frozenset({"user", "team", "org"})


class OwnerScope:
    """Identifies the owner of a DataPlane path or resource.

    kind: "user" | "team" | "org"
    id: string identifier matching the respective table's PK (string UUID for
        organizations, string for users; teams use integer IDs stored as str).
    """

    __slots__ = ("kind", "id")

    def __init__(self, kind: Literal["user", "team", "org"], id: str) -> None:
        if kind not in _VALID_KINDS:
            raise ValueError(f"OwnerScope kind must be one of {_VALID_KINDS!r}, got {kind!r}")
        object.__setattr__(self, "kind", kind)
        object.__setattr__(self, "id", str(id))

    def __setattr__(self, name, value):
        raise AttributeError("OwnerScope is immutable")

    def as_path(self) -> str:
        """Return the path segment for this scope, e.g. 'user/42' or 'org/abc-uuid'."""
        return f"{self.kind}/{self.id}"

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, OwnerScope):
            return NotImplemented
        return self.kind == other.kind and self.id == other.id

    def __hash__(self) -> int:
        return hash((self.kind, self.id))

    def __repr__(self) -> str:
        return f"OwnerScope({self.kind!r}, {self.id!r})"

    @classmethod
    def from_connection(cls, connection) -> "OwnerScope":
        """Derive scope from a DatabaseConnection row.

        Prefers org scope when the connection has an org_id; falls back to user.
        After the Phase 1 migration the columns owner_scope_kind / owner_scope_id
        are used directly; this factory is kept for code that hasn't migrated yet.
        """
        if hasattr(connection, "owner_scope_kind") and connection.owner_scope_kind:
            return cls(connection.owner_scope_kind, connection.owner_scope_id)
        if connection.org_id:
            return cls("org", connection.org_id)
        return cls("user", connection.user_id)
