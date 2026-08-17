from sqlalchemy import Column, Integer, String, Text, DateTime, JSON, ForeignKey, func, Boolean, Float
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
    
    header = relationship("DataloggerHeader", backref="ml_inference")
