import os
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import List

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
        "https://a03ztkg2f5.execute-api.us-east-1.amazonaws.com/default/CowNeck_API_Function"
    )
    AWS_ENABLED_DEVICE_IDS: List[str] = ["8", "7", "9", "1", "3", "4", "5", "6"]

    model_config = SettingsConfigDict(
        env_file=os.path.join(os.path.dirname(__file__), "..", ".env"), 
        extra="ignore"
    )

    @property
    def sqlalchemy_database_url(self) -> str:
        url = self.DATABASE_URL
        if url.startswith("postgres://"):
            url = url.replace("postgres://", "postgresql://", 1)
        return url

settings = Settings()
