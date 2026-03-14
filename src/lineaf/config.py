from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    database_url: str
    test_database_url: str = "postgresql://lineaf:lineaf@localhost:5432/lineaf_test"
    debug: bool = False


settings = Settings()
