from __future__ import annotations

from dataclasses import dataclass
from typing import Generic, TypeVar

T = TypeVar("T")

@dataclass(slots=True)
class AgentResult(Generic[T]):
    agent_name: str
    payload: T


class Agent:
    name: str

    def __init__(self, name: str) -> None:
        self.name = name
