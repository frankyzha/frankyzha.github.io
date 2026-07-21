from __future__ import annotations

import argparse

from collarai.credentials import AccessTokenStore


def main() -> None:
    parser = argparse.ArgumentParser(description="Manage the CollarAI web-demo access key")
    parser.add_argument("action", choices=("create", "show", "rotate", "forget"))
    action = parser.parse_args().action
    store = AccessTokenStore()

    if action == "forget":
        store.delete()
        print("Removed the web-demo access key from the operating system vault.")
        return

    token = store.create(rotate=action == "rotate") if action != "show" else store.load()
    if not token:
        raise SystemExit("No access key exists. Run 'collarai-access create' first.")
    print(token)


if __name__ == "__main__":
    main()
