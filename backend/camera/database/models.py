"""
数据库模型定义
"""
from datetime import datetime
from sqlalchemy import (
    Column, Integer, String, Float, DateTime, Text, Boolean,
    ForeignKey, create_engine, event
)
from sqlalchemy.orm import declarative_base, relationship, sessionmaker

import config

Base = declarative_base()


class Person(Base):
    """注册人员"""
    __tablename__ = "persons"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100), nullable=False)
    department = Column(String(100), default="")
    role = Column(String(50), default="")  # 如: 管理员、运维、访客
    face_image_path = Column(String(500), default="")  # 注册照片路径
    face_encoding = Column(Text, default="")  # 人脸特征向量 (JSON 序列化)
    body_signature = Column(Text, default="")  # 平均体态签名向量 (JSON 序列化)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # 关联事件
    events = relationship("Event", back_populates="person", lazy="dynamic")

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "department": self.department,
            "role": self.role,
            "face_image_path": self.face_image_path,
            "body_signature_registered": bool(self.body_signature),
            "is_active": self.is_active,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class Event(Base):
    """检测事件"""
    __tablename__ = "events"

    id = Column(Integer, primary_key=True, autoincrement=True)
    person_id = Column(Integer, ForeignKey("persons.id"), nullable=True)  # 未识别则为 None
    person_name = Column(String(100), default="未识别")  # 冗余存储方便查询
    camera_id = Column(Integer, ForeignKey("cameras.id"), nullable=True)
    camera_name = Column(String(100), default="")

    event_type = Column(String(50), nullable=False)  # enter, leave, standing, bending, operating, carrying, loitering
    behavior = Column(String(100), default="")  # 行为详细描述
    confidence = Column(Float, default=0.0)  # 检测置信度

    snapshot_path = Column(String(500), default="")  # 事件截图路径
    body_features = Column(Text, default="")  # 即时体态特征向量 (JSON 序列化)
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)

    # 位置信息
    bbox_x = Column(Integer, default=0)
    bbox_y = Column(Integer, default=0)
    bbox_w = Column(Integer, default=0)
    bbox_h = Column(Integer, default=0)

    # 关联
    person = relationship("Person", back_populates="events")
    camera = relationship("Camera", back_populates="events")

    def to_dict(self):
        return {
            "id": self.id,
            "person_id": self.person_id,
            "person_name": self.person_name,
            "camera_id": self.camera_id,
            "camera_name": self.camera_name,
            "event_type": self.event_type,
            "behavior": self.behavior,
            "confidence": round(self.confidence, 2),
            "snapshot_path": self.snapshot_path,
            "has_body_features": bool(self.body_features),
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
            "bbox": {
                "x": self.bbox_x, "y": self.bbox_y,
                "w": self.bbox_w, "h": self.bbox_h
            },
        }


class Camera(Base):
    """摄像头配置"""
    __tablename__ = "cameras"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100), nullable=False)
    source = Column(String(500), nullable=False)  # 0, 1 或 RTSP 地址
    location = Column(String(200), default="")  # 安装位置描述
    is_active = Column(Boolean, default=True)
    width = Column(Integer, default=1280)
    height = Column(Integer, default=720)
    fps = Column(Integer, default=15)
    created_at = Column(DateTime, default=datetime.utcnow)

    # 关联事件
    events = relationship("Event", back_populates="camera", lazy="dynamic")

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "source": self.source,
            "location": self.location,
            "is_active": self.is_active,
            "width": self.width,
            "height": self.height,
            "fps": self.fps,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
