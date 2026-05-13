from typing import Any


class Component:
    def get(self, key: str, default: Any = ...) -> Any: ...
    def walk(self, name: str | None = ...) -> list[Component]: ...


class Calendar(Component):
    @classmethod
    def from_ical(cls, st: bytes | str, multiple: bool = ...) -> Calendar: ...
