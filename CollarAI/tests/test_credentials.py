from __future__ import annotations

import json

from collarai.credentials import AccessTokenStore, CredentialStore, StoredCredentials


def test_stored_credentials_hide_password_and_normalize_identity() -> None:
    credentials = StoredCredentials(username="abc123", password="secret")
    assert credentials.duke_email == "abc123@duke.edu"
    assert credentials.netid == "abc123"
    assert "secret" not in repr(credentials)


def test_pitchbook_session_is_domain_scoped(monkeypatch) -> None:
    saved: dict[tuple[str, str], str] = {}
    monkeypatch.setattr(
        "collarai.credentials.keyring.set_password",
        lambda service, account, value: saved.__setitem__((service, account), value),
    )
    monkeypatch.setattr(
        "collarai.credentials.keyring.get_password",
        lambda service, account: saved.get((service, account)),
    )
    store = CredentialStore()
    store.save_pitchbook_session(
        [
            {"name": "pb", "value": "one", "domain": ".pitchbook.com", "path": "/"},
            {"name": "duke", "value": "two", "domain": "shib.oit.duke.edu", "path": "/"},
        ]
    )

    cookies = store.load_pitchbook_session()
    assert [cookie["name"] for cookie in cookies] == ["pb"]
    assert "duke" not in json.dumps(cookies)


def test_access_token_is_kept_in_the_credential_vault(monkeypatch) -> None:
    saved: dict[tuple[str, str], str] = {}
    monkeypatch.delenv("COLLAR_API_TOKEN", raising=False)
    monkeypatch.setattr(
        "collarai.credentials.keyring.set_password",
        lambda service, account, value: saved.__setitem__((service, account), value),
    )
    monkeypatch.setattr(
        "collarai.credentials.keyring.get_password",
        lambda service, account: saved.get((service, account)),
    )

    store = AccessTokenStore()
    first = store.create()

    assert len(first) >= 32
    assert store.load() == first
    assert store.create() == first
    assert store.create(rotate=True) != first
