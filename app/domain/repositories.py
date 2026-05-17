from typing import Protocol, Any


class UserRepository(Protocol):
    def find_by_username(self, username: str) -> dict[str, Any] | None: ...


class PlayerRepository(Protocol):
    def find_by_id(self, object_id) -> dict[str, Any] | None: ...


class TeamRepository(Protocol):
    def find_by_id(self, object_id) -> dict[str, Any] | None: ...


class ChampionshipRepository(Protocol):
    def find_by_id(self, object_id) -> dict[str, Any] | None: ...


class MatchRepository(Protocol):
    def find_by_id(self, object_id) -> dict[str, Any] | None: ...
