from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Not the jobs database. Jobs read the process environment variable DATABASE_URL
    # when it is set, and sqlite when it is unset. See app.jobs_db.
    database_url: str = "postgresql+psycopg://ingress_job:ingress_job@localhost:5434/ingress_job"
    redis_url: str = "redis://localhost:6380/0"
    oidc_issuer: str = "http://127.0.0.1:8000/"
    oidc_audience: str = "http://127.0.0.1:8010"
    oidc_jwks_url: str = "http://127.0.0.1:8000/portal/oauth/jwks.json"
    oidc_client_id: str = "job-web"
    # Same value as Academy OIDC_JOB_CLIENT_SECRET. Never expose to the frontend.
    oidc_client_secret: str = ""
    oidc_authorize_url: str = "http://127.0.0.1:8000/portal/oauth/authorize"
    oidc_token_url: str = "http://127.0.0.1:8000/portal/oauth/token"
    oidc_redirect_uris: str = (
        "http://localhost:3010/api/auth/callback,"
        "http://127.0.0.1:3010/api/auth/callback"
    )

    def issuer(self) -> str:
        value = self.oidc_issuer.strip()
        if not value:
            return ""
        return value if value.endswith("/") else value + "/"

    def redirect_uri_list(self) -> list[str]:
        return [item.strip() for item in self.oidc_redirect_uris.split(",") if item.strip()]


settings = Settings()
