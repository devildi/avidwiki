"""
YOLOv8 人员检测模块
"""
import cv2
import numpy as np
from ultralytics import YOLO
import config


class PersonDetector:
    """使用 YOLOv8 检测画面中的人员"""

    def __init__(self):
        self.model = YOLO(config.YOLO_MODEL)
        self.confidence = config.YOLO_CONFIDENCE
        self.iou_threshold = config.YOLO_IOU_THRESHOLD
        self.person_class_id = config.YOLO_PERSON_CLASS_ID

    def detect(self, frame: np.ndarray) -> list[dict]:
        """
        检测帧中的人员

        Args:
            frame: BGR 格式图像

        Returns:
            检测结果列表，每个元素包含:
            - bbox: (x1, y1, x2, y2) 检测框坐标
            - confidence: 置信度
            - class_id: 类别 ID
        """
        results = self.model(
            frame,
            conf=self.confidence,
            iou=self.iou_threshold,
            classes=[self.person_class_id],
            verbose=False
        )

        detections = []
        for result in results:
            if result.boxes is None:
                continue
            for box in result.boxes:
                x1, y1, x2, y2 = box.xyxy[0].cpu().numpy().astype(int)
                conf = float(box.conf[0].cpu().numpy())
                detections.append({
                    "bbox": (int(x1), int(y1), int(x2), int(y2)),
                    "confidence": conf,
                    "class_id": int(box.cls[0].cpu().numpy()),
                })

        return detections

    def draw_detections(self, frame: np.ndarray, detections: list[dict],
                        labels: dict = None) -> np.ndarray:
        """
        在帧上绘制检测框

        Args:
            frame: BGR 格式图像
            detections: detect() 返回的检测结果
            labels: {track_id: label_text} 标签映射

        Returns:
            绘制后的图像
        """
        annotated = frame.copy()

        for det in detections:
            x1, y1, x2, y2 = det["bbox"]
            conf = det["confidence"]
            track_id = det.get("track_id", None)

            # 根据是否已识别选择颜色
            person_name = det.get("person_name", None)
            if person_name and person_name != "未识别":
                color = (0, 200, 100)  # 绿色 - 已识别
            elif person_name == "未识别":
                color = (0, 100, 255)  # 橙色 - 未识别
            else:
                color = (255, 200, 0)  # 蓝色 - 检测中

            # 绘制检测框
            cv2.rectangle(annotated, (x1, y1), (x2, y2), color, 2)

            # 构建标签文本
            label_parts = []
            if track_id is not None:
                label_parts.append(f"ID:{track_id}")
            if person_name:
                label_parts.append(person_name)
            if "behavior" in det and det["behavior"]:
                label_parts.append(det["behavior"])
            label_parts.append(f"{conf:.0%}")

            label = " | ".join(label_parts)

            # 绘制标签背景
            (label_w, label_h), baseline = cv2.getTextSize(
                label, cv2.FONT_HERSHEY_SIMPLEX, 0.6, 1
            )
            cv2.rectangle(
                annotated,
                (x1, y1 - label_h - 10),
                (x1 + label_w + 5, y1),
                color, -1
            )
            cv2.putText(
                annotated, label,
                (x1 + 2, y1 - 5),
                cv2.FONT_HERSHEY_SIMPLEX, 0.6,
                (255, 255, 255), 1, cv2.LINE_AA
            )

        return annotated
