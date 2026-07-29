from __future__ import annotations

from app.assistant.outputs import AssistantSearchProgress


class AssistantProgressTracker:
    def __init__(self) -> None:
        self._events: list[AssistantSearchProgress] = []

    def add(self, stage: str, detail: str) -> None:
        self._events.append(AssistantSearchProgress(stage=stage, detail=detail))

    def snapshot(self) -> list[AssistantSearchProgress]:
        return list(self._events)
