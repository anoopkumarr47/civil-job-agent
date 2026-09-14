from __future__ import annotations

from abc import ABC, abstractmethod

from ..models import Job


class Source(ABC):
    name: str

    @abstractmethod
    def discover(self) -> list[Job]:
        raise NotImplementedError
