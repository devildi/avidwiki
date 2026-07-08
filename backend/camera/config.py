"""
机房人员行为检测系统 - 全局配置
"""
import os
from pathlib import Path

# ─── 项目路径 ────────────────────────────────────────────
BASE_DIR = Path(__file__).resolve().parent.parent.parent
DATA_DIR = BASE_DIR / "data" / "camera"
FACES_DIR = DATA_DIR / "faces"
SNAPSHOTS_DIR = DATA_DIR / "snapshots"
MODELS_DIR = BASE_DIR

# 确保目录存在
for d in [DATA_DIR, FACES_DIR, SNAPSHOTS_DIR]:
    d.mkdir(parents=True, exist_ok=True)

# ─── 数据库 ──────────────────────────────────────────────
DATABASE_URL = f"sqlite:///{DATA_DIR / 'camera.db'}"

# ─── 摄像头配置 ──────────────────────────────────────────
# 默认使用本机摄像头 (0)，也可以设置为 RTSP 地址
# 例如: "rtsp://admin:password@192.168.1.100:554/stream1"
DEFAULT_CAMERA_SOURCE = 0
CAMERA_FPS = 15  # 处理帧率（降低以减少 CPU 负担）
CAMERA_WIDTH = 1280
CAMERA_HEIGHT = 720

# ─── YOLO 检测配置 ────────────────────────────────────────
YOLO_MODEL = str(BASE_DIR / "yolov8n.pt")  # 使用绝对路径指向 wiki 根目录下的 yolov8n.pt
YOLO_CONFIDENCE = 0.5  # 检测置信度阈值
YOLO_IOU_THRESHOLD = 0.45  # NMS IoU 阈值
YOLO_PERSON_CLASS_ID = 0  # COCO 数据集中 person 类别的 ID

# ─── 人脸识别配置 ─────────────────────────────────────────
FACE_RECOGNITION_MODEL = "VGG-Face"  # 可选: VGG-Face, Facenet, ArcFace
FACE_DETECTOR_BACKEND = "opencv"  # 可选: opencv, ssd, mtcnn, retinaface
FACE_DISTANCE_THRESHOLD = 0.6  # 人脸匹配距离阈值（越小越严格）
FACE_RECOGNITION_INTERVAL = 30  # 每隔多少帧进行一次人脸识别

# ─── MediaPipe 姿态配置 ──────────────────────────────────
POSE_MIN_DETECTION_CONFIDENCE = 0.5
POSE_MIN_TRACKING_CONFIDENCE = 0.5

# ─── 行为检测配置 ─────────────────────────────────────────
# 异常逗留检测：某区域停留超过此秒数触发告警
LOITER_THRESHOLD_SECONDS = 300  # 5 分钟
# 行为分析的时间窗口（帧数）
BEHAVIOR_WINDOW_SIZE = 30

# ─── 服务器配置 ───────────────────────────────────────────
API_HOST = "0.0.0.0"
API_PORT = 8000
CORS_ORIGINS = ["*"]  # 生产环境应限制

# ─── 事件截图 ────────────────────────────────────────────
SNAPSHOT_QUALITY = 85  # JPEG 质量
MAX_SNAPSHOTS_PER_DAY = 1000  # 每日最大截图数
