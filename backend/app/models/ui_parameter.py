from sqlalchemy import Column, Integer, String
from app.database import Base

class ActivityConfig(Base):
    __tablename__ = "activity_config"

    id = Column(Integer, primary_key=True, index=True)
    code = Column(String(10), unique=True, index=True, nullable=False)
    name = Column(String(100), nullable=False)
    color = Column(String(20), nullable=False)
    icon = Column(String(50), nullable=True)
    category = Column(String(50), nullable=True)
