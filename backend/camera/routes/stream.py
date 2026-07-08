"""
视频流路由 - MJPEG 实时视频推送
"""
import cv2
import time
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from core.pipeline import pipeline_manager

router = APIRouter()


def generate_mjpeg(camera_id: int, annotated: bool = True):
    """生成 MJPEG 视频流"""
    pipeline = pipeline_manager.get_pipeline(camera_id)
    if not pipeline:
        return

    while True:
        if annotated:
            frame = pipeline.get_annotated_frame()
        else:
            frame = pipeline.get_raw_frame()

        if frame is None:
            # 没有帧时生成一个黑色占位帧
            import numpy as np
            frame = np.zeros((480, 640, 3), dtype=np.uint8)
            cv2.putText(frame, "Waiting for camera...",
                       (150, 240), cv2.FONT_HERSHEY_SIMPLEX,
                       1, (100, 100, 100), 2)

        _, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 80])
        frame_bytes = buffer.tobytes()

        yield (
            b'--frame\r\n'
            b'Content-Type: image/jpeg\r\n\r\n'
            + frame_bytes +
            b'\r\n'
        )

        time.sleep(1.0 / 15)  # ~15 FPS


@router.get("/stream/{camera_id}")
async def video_stream(camera_id: int):
    """获取标注后的实时视频流（MJPEG）"""
    pipeline = pipeline_manager.get_pipeline(camera_id)
    if not pipeline:
        raise HTTPException(status_code=404, detail=f"摄像头 {camera_id} 不存在")

    return StreamingResponse(
        generate_mjpeg(camera_id, annotated=True),
        media_type="multipart/x-mixed-replace; boundary=frame"
    )


@router.get("/stream/{camera_id}/raw")
async def raw_video_stream(camera_id: int):
    """获取原始视频流（MJPEG）"""
    pipeline = pipeline_manager.get_pipeline(camera_id)
    if not pipeline:
        raise HTTPException(status_code=404, detail=f"摄像头 {camera_id} 不存在")

    return StreamingResponse(
        generate_mjpeg(camera_id, annotated=False),
        media_type="multipart/x-mixed-replace; boundary=frame"
    )


@router.get("/stream/{camera_id}/snapshot")
async def get_snapshot(camera_id: int):
    """获取当前帧截图"""
    pipeline = pipeline_manager.get_pipeline(camera_id)
    if not pipeline:
        raise HTTPException(status_code=404, detail=f"摄像头 {camera_id} 不存在")

    frame = pipeline.get_annotated_frame()
    if frame is None:
        raise HTTPException(status_code=503, detail="暂无视频帧")

    _, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 90])
    from fastapi.responses import Response
    return Response(
        content=buffer.tobytes(),
        media_type="image/jpeg"
    )
