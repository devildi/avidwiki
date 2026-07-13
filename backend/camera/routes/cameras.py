"""
摄像头管理路由
"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from typing import Optional

from database.db import get_db
from database.models import Camera
from core.pipeline import pipeline_manager

router = APIRouter()


class CameraCreate(BaseModel):
    name: str
    source: str  # "0" 或 RTSP 地址
    location: str = ""
    width: int = 1280
    height: int = 720
    fps: int = 15


class CameraUpdate(BaseModel):
    name: Optional[str] = None
    source: Optional[str] = None
    location: Optional[str] = None
    is_active: Optional[bool] = None
    width: Optional[int] = None
    height: Optional[int] = None
    fps: Optional[int] = None


@router.get("/cameras")
def list_cameras(db: Session = Depends(get_db)):
    """获取摄像头列表"""
    cameras = db.query(Camera).all()
    result = []
    for cam in cameras:
        cam_dict = cam.to_dict()
        pipeline = pipeline_manager.get_pipeline(cam.id)
        cam_dict["is_running"] = pipeline.is_running if pipeline else False
        cam_dict["stats"] = pipeline.stats if pipeline else {}
        result.append(cam_dict)

    return {"items": result}


@router.post("/cameras")
def create_camera(data: CameraCreate, db: Session = Depends(get_db)):
    """添加摄像头"""
    camera = Camera(
        name=data.name,
        source=data.source,
        location=data.location,
        width=data.width,
        height=data.height,
        fps=data.fps,
        is_active=True,
    )
    db.add(camera)
    db.commit()
    db.refresh(camera)

    return {"camera": camera.to_dict(), "message": "摄像头已添加"}


@router.put("/cameras/{camera_id}")
def update_camera(camera_id: int, data: CameraUpdate, db: Session = Depends(get_db)):
    """修改摄像头配置"""
    camera = db.query(Camera).filter(Camera.id == camera_id).first()
    if not camera:
        raise HTTPException(status_code=404, detail="摄像头不存在")

    for field, value in data.model_dump(exclude_none=True).items():
        setattr(camera, field, value)

    db.commit()
    db.refresh(camera)

    return {"camera": camera.to_dict(), "message": "更新成功"}


@router.delete("/cameras/{camera_id}")
def delete_camera(camera_id: int, db: Session = Depends(get_db)):
    """删除摄像头"""
    camera = db.query(Camera).filter(Camera.id == camera_id).first()
    if not camera:
        raise HTTPException(status_code=404, detail="摄像头不存在")

    # 停止管道
    pipeline = pipeline_manager.get_pipeline(camera_id)
    if pipeline:
        pipeline.stop()
        del pipeline_manager.pipelines[camera_id]

    db.delete(camera)
    db.commit()

    return {"message": f"摄像头 {camera.name} 已删除"}


@router.post("/cameras/{camera_id}/start")
def start_camera(camera_id: int, db: Session = Depends(get_db)):
    """启动摄像头检测"""
    camera = db.query(Camera).filter(Camera.id == camera_id).first()
    if not camera:
        raise HTTPException(status_code=404, detail="摄像头不存在")

    pipeline = pipeline_manager.get_pipeline(camera_id)
    if pipeline and pipeline.is_running:
        return {"message": "摄像头已在运行中"}

    # 创建/重建管道
    pipeline = pipeline_manager.add_pipeline(camera.id, camera.name, camera.source)
    try:
        pipeline.start()
        return {"message": f"摄像头 {camera.name} 已启动"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"启动失败: {str(e)}")


@router.post("/cameras/{camera_id}/stop")
def stop_camera(camera_id: int, db: Session = Depends(get_db)):
    """停止摄像头检测"""
    pipeline = pipeline_manager.get_pipeline(camera_id)
    if not pipeline:
        raise HTTPException(status_code=404, detail="摄像头管道不存在")

    pipeline.stop()
    return {"message": "摄像头已停止"}


@router.get("/cameras/detect")
def detect_local_cameras():
    """检测本机可用的摄像头设备"""
    import cv2
    available = []
    # 快速检测索引 0 到 4 的摄像头
    for index in range(5):
        cap = cv2.VideoCapture(index)
        if cap is not None and cap.isOpened():
            available.append({
                "id": str(index),
                "name": f"默认摄像头 / 电脑自带 (设备 {index})" if index == 0 else f"USB 外接摄像头 (设备 {index})"
            })
            cap.release()
    return {"devices": available}
