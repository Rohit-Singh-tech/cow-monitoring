import os
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import field_validator
from typing import List, Union, Any

class Settings(BaseSettings):
    PROJECT_NAME: str = "Cow Logger Gateway-Less Livestock Monitoring API"
    VERSION: str = "1.0.0"
    API_V1_STR: str = "/api/v1"
    
    # Database Settings
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL", 
        "postgresql://ble_sense_p1fq_user:U99Ev57Lm8lijJSo80lznjCDxp0KjHo8@dpg-dapn2h8u01pc73d894bg-a.ohio-postgres.render.com/ble_sense_p1fq"
    )
    
    # CORS Settings
    CORS_ORIGINS: List[str] = [
        "http://localhost:5173",
        "http://localhost:3000",
        "http://127.0.0.1:5173",
        "https://cow-monitoring-li58.onrender.com",
        "*"
    ]
    
    # ML Model Path
    MODEL_PATH: str = os.getenv(
        "MODEL_PATH",
        os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "cow_ml_models"))
    )

    # AWS CowNeck API Settings
    AWS_COWNECK_API_URL: str = os.getenv(
        "AWS_COWNECK_API_URL",
        "https://a03ztkg2f5.execute-api.us-east-1.amazonaws.com/default/CowNeck_API_Function?type=cow01"
    )
    AWS_COWNECK_API_TYPE: str = os.getenv("AWS_COWNECK_API_TYPE", "cow01")
    # Optional seed device IDs (devices are dynamically auto-discovered and tracked)
    AWS_ENABLED_DEVICE_IDS: Union[List[str], str] = []
    AWS_DISCOVERY_SCAN_MAX: int = int(os.getenv("AWS_DISCOVERY_SCAN_MAX", "100"))
    AWS_AUTO_DISCOVERY_INTERVAL_MINUTES: int = int(os.getenv("AWS_AUTO_DISCOVERY_INTERVAL_MINUTES", "10"))

    @field_validator("AWS_ENABLED_DEVICE_IDS", mode="before")
    @classmethod
    def parse_device_ids(cls, v):
        if not v:
            return []
        if isinstance(v, str):
            if v.startswith("["):
                try:
                    import json
                    return json.loads(v)
                except Exception:
                    pass
            return [x.strip() for x in v.split(",") if x.strip()]
        return v

    model_config = SettingsConfigDict(
        env_file=os.path.join(os.path.dirname(__file__), "..", ".env"), 
        extra="ignore"
    )

    @property
    def sqlalchemy_database_url(self) -> str:
        url = self.DATABASE_URL
        if url.startswith("postgres://"):
            url = url.replace("postgres://", "postgresql+psycopg2://", 1)
        elif url.startswith("postgresql://") and not url.startswith("postgresql+"):
            url = url.replace("postgresql://", "postgresql+psycopg2://", 1)
        return url

settings = Settings()
