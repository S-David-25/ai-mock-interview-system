from dataclasses import dataclass
from typing import Optional

@dataclass
class User:
    id: Optional[int] = None
    name: str = ""
    email: str = ""
    password_hash: str = ""
    created_at: Optional[str] = None

    @classmethod
    def from_row(cls, row: dict):
        if not row:
            return None
        return cls(
            id=row.get("id"),
            name=row.get("name"),
            email=row.get("email"),
            password_hash=row.get("password_hash"),
            created_at=row.get("created_at"),
        )

    def to_dict(self, include_sensitive: bool = False) -> dict:
        data = {
            "id": self.id,
            "name": self.name,
            "email": self.email,
            "created_at": self.created_at,
        }
        if include_sensitive:
            data["password_hash"] = self.password_hash
        return data
