"""Settings service for Auth0 config persistence and audit helper actions."""

from pathlib import Path

from ..repositories import settings_repository


def validate_auth0_domain(auth0_domain: str) -> bool:
    return bool(auth0_domain and "." in auth0_domain)


def persist_auth0_config(domain: str, client_id: str, client_secret: str, audience: str) -> None:
    settings_repository.upsert_auth0_settings(domain, client_id, client_secret, audience)


def get_user_id(sub: str) -> int:
    return settings_repository.get_user_id_by_sub(sub)


def update_env_file(env_path: Path, updates: dict[str, str]) -> None:
    if not env_path.exists():
        with open(env_path, "w") as f:
            for key, value in updates.items():
                f.write(f"{key}={value}\n")
        return

    with open(env_path, "r") as f:
        lines = f.readlines()

    updated_keys = set()
    new_lines = []
    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            new_lines.append(line)
            continue

        if "=" in line:
            key = line.split("=")[0].strip()
            if key in updates:
                new_lines.append(f"{key}={updates[key]}\n")
                updated_keys.add(key)
                continue

        new_lines.append(line)

    for key, value in updates.items():
        if key not in updated_keys:
            new_lines.append(f"{key}={value}\n")

    with open(env_path, "w") as f:
        f.writelines(new_lines)
