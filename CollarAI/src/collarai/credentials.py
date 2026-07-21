from __future__ import annotations

import json
import os
import secrets
from dataclasses import dataclass, field
from typing import Any

import keyring
from keyring.errors import KeyringError, PasswordDeleteError

from collarai.errors import ConfigurationRequired

_SERVICE = "com.collarai.pitchbook.duke-sso"
_SESSION_ACCOUNT = "pitchbook-session"
_API_SERVICE = "com.collarai.browser-demo"
_API_ACCOUNT = "access-token"


@dataclass(slots=True)
class StoredCredentials:
    username: str
    password: str = field(repr=False)

    @property
    def duke_email(self) -> str:
        return self.username if "@" in self.username else f"{self.username}@duke.edu"

    @property
    def netid(self) -> str:
        return self.username.split("@", 1)[0]


class CredentialStore:
    """Store SSO credentials in the operating system vault, never project files or env."""

    def save(self, username: str, password: str) -> None:
        username = username.strip()
        if not username or not password:
            raise ValueError("Duke username and password are required")
        try:
            keyring.set_password(_SERVICE, "username", username)
            keyring.set_password(_SERVICE, "password", password)
        except KeyringError as error:
            raise ConfigurationRequired(
                "The operating system credential vault is unavailable"
            ) from error

    def load(self) -> StoredCredentials | None:
        try:
            username = keyring.get_password(_SERVICE, "username")
            password = keyring.get_password(_SERVICE, "password")
        except KeyringError as error:
            raise ConfigurationRequired(
                "The operating system credential vault is unavailable"
            ) from error
        if not username or not password:
            return None
        return StoredCredentials(username=username, password=password)

    def save_pitchbook_session(self, cookies: list[dict[str, Any]]) -> None:
        scoped = [cookie for cookie in cookies if self._is_pitchbook_domain(cookie.get("domain"))]
        if not scoped:
            raise ValueError("No PitchBook session cookies were available")
        try:
            keyring.set_password(_SERVICE, _SESSION_ACCOUNT, json.dumps(scoped))
        except KeyringError as error:
            raise ConfigurationRequired(
                "The operating system credential vault is unavailable"
            ) from error

    def load_pitchbook_session(self) -> list[dict[str, Any]]:
        try:
            payload = keyring.get_password(_SERVICE, _SESSION_ACCOUNT)
        except KeyringError as error:
            raise ConfigurationRequired(
                "The operating system credential vault is unavailable"
            ) from error
        if not payload:
            return []
        try:
            cookies = json.loads(payload)
        except json.JSONDecodeError as error:
            raise ConfigurationRequired("The saved PitchBook session is invalid") from error
        if not isinstance(cookies, list) or not all(isinstance(item, dict) for item in cookies):
            raise ConfigurationRequired("The saved PitchBook session is invalid")
        return [cookie for cookie in cookies if self._is_pitchbook_domain(cookie.get("domain"))]

    def delete(self) -> None:
        for account in ("username", "password", _SESSION_ACCOUNT):
            try:
                keyring.delete_password(_SERVICE, account)
            except PasswordDeleteError:
                continue
            except KeyringError as error:
                raise ConfigurationRequired(
                    "The operating system credential vault is unavailable"
                ) from error

    @staticmethod
    def _is_pitchbook_domain(value: object) -> bool:
        if not isinstance(value, str):
            return False
        domain = value.lstrip(".").casefold()
        return domain == "pitchbook.com" or domain.endswith(".pitchbook.com")


class AccessTokenStore:
    """Store the web-demo bearer token outside the repository."""

    def create(self, *, rotate: bool = False) -> str:
        existing = self.load()
        if existing and not rotate:
            return existing
        token = secrets.token_urlsafe(32)
        try:
            keyring.set_password(_API_SERVICE, _API_ACCOUNT, token)
        except KeyringError as error:
            raise ConfigurationRequired(
                "The operating system credential vault is unavailable"
            ) from error
        return token

    def load(self) -> str | None:
        if token := os.getenv("COLLAR_API_TOKEN"):
            return token
        try:
            return keyring.get_password(_API_SERVICE, _API_ACCOUNT)
        except KeyringError as error:
            raise ConfigurationRequired(
                "The operating system credential vault is unavailable"
            ) from error

    def delete(self) -> None:
        try:
            keyring.delete_password(_API_SERVICE, _API_ACCOUNT)
        except PasswordDeleteError:
            return
        except KeyringError as error:
            raise ConfigurationRequired(
                "The operating system credential vault is unavailable"
            ) from error
