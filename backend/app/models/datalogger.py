from sqlalchemy import Column, Integer, String, Text, DateTime, Date, JSON, ForeignKey, func, Boolean, Float, UniqueConstraint
from sqlalchemy.orm import relationship
from app.database import Base

class RawPacket(Base):
    __tablename__ = "raw_packets"

    id = Column(Integer, primary_key=True, index=True)
    payload = Column(JSON, nullable=False)
    status = Column(String, index=True, default="pending")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    processed_at = Column(DateTime(timezone=True), nullable=True)

    headers = relationship("DataloggerHeader", back_populates="raw_packet", cascade="all, delete-orphan")


class SensorPacket(Base):
    __tablename__ = "sensor_packets"

    id = Column(Integer, primary_key=True, index=True)
    app_id = Column(String, index=True, nullable=False)
    data = Column(JSON, nullable=False)
    timestamp = Column(DateTime(timezone=True), server_default=func.now(), index=True)


class DataloggerHeader(Base):
    __tablename__ = "datalogger_headers"

    id = Column(Integer, primary_key=True, index=True)
    raw_packet_id = Column(Integer, ForeignKey("raw_packets.id", ondelete="CASCADE"), nullable=True)
    app_id = Column(String, index=True, nullable=False)
    device_id = Column(String, index=True, nullable=False)
    packet_id_num = Column(Integer, nullable=False)
    total_packets = Column(Integer, nullable=True)
    raw_data = Column(Text, nullable=True)
    timestamp = Column(DateTime(timezone=True), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    raw_packet = relationship("RawPacket", back_populates="headers")
    points = relationship("DataloggerPoint", back_populates="header", cascade="all, delete-orphan")


class DataloggerPoint(Base):
    __tablename__ = "datalogger_points"

    id = Column(Integer, primary_key=True, index=True)
    header_id = Column(Integer, ForeignKey("datalogger_headers.id", ondelete="CASCADE"), nullable=False)
    point_index = Column(Integer, nullable=False)
    x = Column(Integer, nullable=True)
    y = Column(Integer, nullable=True)
    z = Column(Integer, nullable=True)

    header = relationship("DataloggerHeader", back_populates="points")

class MLInference(Base):
    __tablename__ = "ml_inferences"

    id = Column(Integer, primary_key=True, index=True)
    header_id = Column(Integer, ForeignKey("datalogger_headers.id", ondelete="CASCADE"), unique=True, nullable=False)
    activity_code = Column(String(10), nullable=False)
    confidence = Column(Integer, nullable=False)
    is_heat = Column(Boolean, default=False)
    heat_probability = Column(Float, nullable=False, default=0.0)
    health_risk_decision = Column(String(20), nullable=False, default="HEALTHY")
    is_anomaly = Column(Boolean, default=False)
    anomaly_score = Column(Float, nullable=False, default=0.0)
    
    header = relationship("DataloggerHeader", backref="ml_inference")


class DailyCowSummary(Base):
    """Pre-aggregated daily health summary per cow. Updated by background worker."""
    __tablename__ = "daily_cow_summaries"
    __table_args__ = (
        UniqueConstraint("device_id", "date", name="uq_device_date"),
    )

    id = Column(Integer, primary_key=True, index=True)
    device_id = Column(String, index=True, nullable=False)
    date = Column(Date, index=True, nullable=False)
    total_packets = Column(Integer, default=0)
    monitored_hours = Column(Float, default=0.0)
    rumination_count = Column(Integer, default=0)
    lying_count = Column(Integer, default=0)
    feeding_count = Column(Integer, default=0)
    moving_count = Column(Integer, default=0)
    heat_count = Column(Integer, default=0)
    rumination_hours = Column(Float, default=0.0)
    lying_hours = Column(Float, default=0.0)
    feeding_hours = Column(Float, default=0.0)
    moving_hours = Column(Float, default=0.0)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
