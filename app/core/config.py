from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "NetDoc"
    app_version: str = "0.11.0"

    netbox_url: str
    netbox_token: str
    netbox_token_type: str = "token"
    netbox_verify_ssl: bool = False
    netbox_timeout: float = 15.0
    netbox_write_enabled: bool = False

    # Descubrimiento LLDP por SSH. Los perfiles se reciben como JSON desde .env.
    # Ejemplo: {"default":{"username":"netdoc-read","password":"..."},
    # "arista_eos":{"username":"netdoc-arista","password":"..."}}
    netdoc_ssh_discovery_enabled: bool = False
    netdoc_ssh_profiles_json: str = "{}"
    netdoc_ssh_connect_timeout: int = 10
    netdoc_ssh_command_timeout: int = 30
    netdoc_ssh_max_neighbors: int = 256

    session_secret: str
    session_cookie_name: str = "netdoc_session"
    session_cookie_secure: bool = False
    session_max_age: int = 28800

    login_max_attempts: int = 5
    login_window_seconds: int = 900

    admin_username: str
    admin_password_hash: str

    database_url: str = "sqlite:///./data/netdoc.db"
    audit_page_size: int = 50

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
