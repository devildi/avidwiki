"""
人脸识别模块 - 基于 DeepFace
"""
import os
import json
import cv2
import numpy as np
from pathlib import Path
from typing import Optional
import logging

logger = logging.getLogger(__name__)

# 延迟导入 DeepFace 以加速启动
_deepface = None


def _get_deepface():
    global _deepface
    if _deepface is None:
        from deepface import DeepFace
        _deepface = DeepFace
    return _deepface


import config


class FaceRecognizer:
    """人脸识别管理器"""

    def __init__(self):
        self.model_name = config.FACE_RECOGNITION_MODEL
        self.detector_backend = config.FACE_DETECTOR_BACKEND
        self.distance_threshold = config.FACE_DISTANCE_THRESHOLD
        self.faces_dir = config.FACES_DIR
        self.registered_faces: dict[int, dict] = {}  # person_id -> {name, encoding, image_path}
        self._load_registered_faces()

    def _load_registered_faces(self):
        """从磁盘加载已注册的人脸"""
        faces_index = self.faces_dir / "index.json"
        if faces_index.exists():
            try:
                with open(faces_index, "r", encoding="utf-8") as f:
                    data = json.load(f)
                self.registered_faces = {int(k): v for k, v in data.items()}
                logger.info(f"已加载 {len(self.registered_faces)} 个注册人脸")
            except Exception as e:
                logger.error(f"加载人脸索引失败: {e}")

    def _save_index(self):
        """保存人脸索引到磁盘"""
        faces_index = self.faces_dir / "index.json"
        try:
            with open(faces_index, "w", encoding="utf-8") as f:
                json.dump(self.registered_faces, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"保存人脸索引失败: {e}")

    def register_face(self, person_id: int, name: str, image_path: str) -> bool:
        """
        注册人脸

        Args:
            person_id: 人员 ID
            name: 姓名
            image_path: 人脸照片路径

        Returns:
            是否注册成功
        """
        try:
            DeepFace = _get_deepface()

            # 提取人脸特征
            embeddings = DeepFace.represent(
                img_path=image_path,
                model_name=self.model_name,
                detector_backend=self.detector_backend,
                enforce_detection=True
            )

            if not embeddings:
                logger.warning(f"未在图片中检测到人脸: {image_path}")
                return False

            # 保存注册信息
            self.registered_faces[person_id] = {
                "name": name,
                "encoding": embeddings[0]["embedding"],
                "image_path": image_path,
            }
            self._save_index()
            logger.info(f"成功注册人脸: {name} (ID: {person_id})")
            return True

        except Exception as e:
            logger.error(f"人脸注册失败 ({name}): {e}")
            return False

    def unregister_face(self, person_id: int):
        """注销人脸"""
        if person_id in self.registered_faces:
            name = self.registered_faces[person_id]["name"]
            del self.registered_faces[person_id]
            self._save_index()
            logger.info(f"已注销人脸: {name} (ID: {person_id})")

    def recognize(self, face_image: np.ndarray) -> Optional[dict]:
        """
        识别人脸

        Args:
            face_image: BGR 格式的人脸区域图像

        Returns:
            匹配结果 {"person_id", "name", "distance"} 或 None
        """
        if not self.registered_faces:
            return None

        try:
            DeepFace = _get_deepface()

            # 提取当前人脸特征
            embeddings = DeepFace.represent(
                img_path=face_image,
                model_name=self.model_name,
                detector_backend=self.detector_backend,
                enforce_detection=False
            )

            if not embeddings:
                return None

            current_encoding = np.array(embeddings[0]["embedding"])

            # 与所有注册人脸比较
            best_match = None
            best_distance = float("inf")

            for pid, face_data in self.registered_faces.items():
                registered_encoding = np.array(face_data["encoding"])
                # 余弦距离
                distance = 1 - np.dot(current_encoding, registered_encoding) / (
                    np.linalg.norm(current_encoding) * np.linalg.norm(registered_encoding)
                )
                if distance < best_distance:
                    best_distance = distance
                    best_match = {
                        "person_id": pid,
                        "name": face_data["name"],
                        "distance": float(distance),
                    }

            if best_match and best_match["distance"] < self.distance_threshold:
                return best_match

            return None

        except Exception as e:
            logger.debug(f"人脸识别异常: {e}")
            return None

    def get_registered_count(self) -> int:
        return len(self.registered_faces)
