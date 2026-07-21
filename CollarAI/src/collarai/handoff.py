from __future__ import annotations

import argparse
import asyncio
import getpass

from collarai.browser import BrowserSessionManager
from collarai.config import Settings
from collarai.credentials import CredentialStore
from collarai.pitchbook_auth import PitchBookAuthenticator
from collarai.recording import InteractionRecorder


def save_credentials() -> None:
    username = input("Duke NetID or email: ").strip()
    password = getpass.getpass("Duke password (saved in the OS credential vault): ")
    CredentialStore().save(username, password)
    print("Saved in the operating system credential vault; no .env file was created.")


def forget_credentials() -> None:
    CredentialStore().delete()
    print("Removed the saved Duke credentials from the operating system vault.")


async def authenticate() -> None:
    settings = Settings.from_env()
    sessions = BrowserSessionManager(settings)
    credentials = CredentialStore().load()
    try:
        async with sessions.acquire("pitchbook") as session:
            page = session.page
            if not (await page.current_url()).startswith(settings.pitchbook_url):
                await page.goto(settings.pitchbook_url)
            if credentials is None:
                print(
                    "No saved credentials. Run 'collarai-pitchbook credentials' "
                    "or sign in manually."
                )
                print("Chrome is open. Click 'Sign in with SSO', then complete Duke SSO.")
                await asyncio.to_thread(
                    input,
                    "When the PitchBook application is open, return here and press Enter: ",
                )
                return
            outcome = await PitchBookAuthenticator().authenticate(page, credentials)
            print(outcome.message)
            if not outcome.signed_in:
                print(
                    "Complete the indicated checkpoint in Chrome; "
                    "the password remains in the vault."
                )
    finally:
        await sessions.close()


async def capture() -> None:
    settings = Settings.from_env()
    sessions = BrowserSessionManager(settings)
    try:
        async with sessions.acquire("pitchbook") as session:
            page = session.page
            if not (await page.current_url()).startswith(settings.pitchbook_url):
                await page.goto(settings.pitchbook_url)
            recorder = InteractionRecorder(settings.state_dir / "captures")
            await recorder.attach(page)
            print("Recording the existing authenticated Chrome tab through Stagehand v3.")
            print("Perform the target workflow and leave the completed result table visible.")
            print("Do not close Chrome. Return here when the final table is fully loaded.")
            await asyncio.to_thread(input, "Press Enter to finish the capture: ")
            output = await recorder.save(page)
            print(f"Recorded workflow: {output}")
            print("Chrome remains open so the authenticated session can be replayed immediately.")
    finally:
        await sessions.close()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Safe PitchBook authentication and capture handoff"
    )
    parser.add_argument(
        "action",
        choices=("credentials", "forget-credentials", "auth", "capture"),
    )
    action = parser.parse_args().action
    if action == "credentials":
        save_credentials()
    elif action == "forget-credentials":
        forget_credentials()
    elif action == "auth":
        asyncio.run(authenticate())
    else:
        asyncio.run(capture())


if __name__ == "__main__":
    main()
