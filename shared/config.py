from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class ServiceSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    service_name: str = Field(alias="SERVICE_NAME")
    host: str = Field(default="0.0.0.0", alias="HOST")
    port: int = Field(alias="PORT")
    log_dir: str = Field(default="/var/log/security-platform", alias="LOG_DIR")
    default_latency_ms: int = Field(default=40, alias="DEFAULT_LATENCY_MS")
    latency_jitter_ms: int = Field(default=80, alias="LATENCY_JITTER_MS")
    error_rate: float = Field(default=0.03, alias="ERROR_RATE")

    auth_service_url: str = Field(default="http://auth-service:8001", alias="AUTH_SERVICE_URL")
    vault_service_url: str = Field(default="http://vault-service:8002", alias="VAULT_SERVICE_URL")
    scan_service_url: str = Field(default="http://scan-service:8003", alias="SCAN_SERVICE_URL")

    failed_login_spike_multiplier: int = Field(default=1, alias="FAILED_LOGIN_SPIKE_MULTIPLIER")
    token_failure_spike_multiplier: int = Field(default=1, alias="TOKEN_FAILURE_SPIKE_MULTIPLIER")
    scan_backlog_spike_multiplier: int = Field(default=1, alias="SCAN_BACKLOG_SPIKE_MULTIPLIER")
    vault_dependency_failure: int = Field(default=0, alias="VAULT_DEPENDENCY_FAILURE")
    memory_pressure_enabled: int = Field(default=0, alias="MEMORY_PRESSURE_ENABLED")


@lru_cache(maxsize=8)
def get_settings(service_name: str, port: int) -> ServiceSettings:
    return ServiceSettings(SERVICE_NAME=service_name, PORT=port)
