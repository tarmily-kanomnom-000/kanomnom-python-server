from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class MedusaInstanceMetadata:
    instance_key: str
    base_url: str


@dataclass(frozen=True)
class MedusaInstanceCredentials:
    admin_email: str
    admin_password: str


@dataclass(frozen=True)
class MedusaAuthToken:
    token: str
    expires_at: datetime
