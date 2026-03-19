from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional, Type, Callable

from fastapi import APIRouter


@dataclass
class ConnectorRegistration:
    """Metadata + class for a connector type a plugin provides."""
    type_id: str
    display_name: str
    description: str
    default_port: int
    badge_variant: str
    connector_class: Type
    on_delete: Optional[Callable] = None
    on_test: Optional[Callable] = None
    skip_schema_refresh: bool = False
    sql_dialect_hint: Optional[str] = None


class BingoPlugin(ABC):
    """Base class for all Bingo plugins."""

    @property
    @abstractmethod
    def name(self) -> str: ...

    @property
    @abstractmethod
    def version(self) -> str: ...

    @property
    def description(self) -> str:
        return ""

    @property
    def dependencies(self) -> list[str]:
        return []

    def connectors(self) -> list[ConnectorRegistration]:
        return []

    def api_routers(self) -> list[tuple[APIRouter, str]]:
        """Return (router, url_prefix) tuples."""
        return []

    def on_startup(self) -> None:
        pass

    def on_shutdown(self) -> None:
        pass
