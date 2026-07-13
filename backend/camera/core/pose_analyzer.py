"""
姿态分析与行为识别模块 - 基于 MediaPipe
"""
import cv2
import numpy as np
import math
from typing import Optional
from collections import deque
import logging

logger = logging.getLogger(__name__)

# 延迟导入
_mp = None
_mp_pose = None


def _get_mediapipe():
    global _mp, _mp_pose
    if _mp is None:
        import os
        os.environ["GLOG_minloglevel"] = "2"
        import mediapipe as mp
        _mp = mp
        _mp_pose = mp.solutions.pose
    return _mp, _mp_pose


import config

# 行为类型定义
BEHAVIORS = {
    "standing": "站立",
    "walking": "行走",
    "bending": "弯腰",
    "crouching": "蹲下",
    "sitting": "坐着",
    "operating": "操作设备",
    "reaching_up": "向上操作",
    "unknown": "未知",
}


class PoseAnalyzer:
    """基于 MediaPipe 的姿态分析与行为识别"""

    def __init__(self):
        mp, mp_pose = _get_mediapipe()
        self.pose = mp_pose.Pose(
            static_image_mode=False,
            model_complexity=1,
            min_detection_confidence=config.POSE_MIN_DETECTION_CONFIDENCE,
            min_tracking_confidence=config.POSE_MIN_TRACKING_CONFIDENCE,
        )
        self.mp_pose = mp_pose
        self.mp_drawing = mp.solutions.drawing_utils

        # 每个追踪目标的行为历史
        self.behavior_history: dict[int, deque] = {}
        self.window_size = config.BEHAVIOR_WINDOW_SIZE

    def analyze(self, frame: np.ndarray, bbox: tuple, track_id: int = 0) -> dict:
        """
        分析人物姿态和行为

        Args:
            frame: 完整帧 (BGR)
            bbox: 人物检测框 (x1, y1, x2, y2)
            track_id: 追踪 ID

        Returns:
            {
                "behavior": 行为类型(英文),
                "behavior_cn": 行为类型(中文),
                "pose_landmarks": 关键点坐标,
                "confidence": 置信度
            }
        """
        x1, y1, x2, y2 = bbox

        # 扩展裁剪区域以包含完整人体
        h, w = frame.shape[:2]
        pad_x = int((x2 - x1) * 0.1)
        pad_y = int((y2 - y1) * 0.1)
        crop_x1 = max(0, x1 - pad_x)
        crop_y1 = max(0, y1 - pad_y)
        crop_x2 = min(w, x2 + pad_x)
        crop_y2 = min(h, y2 + pad_y)

        person_crop = frame[crop_y1:crop_y2, crop_x1:crop_x2]

        if person_crop.size == 0:
            return {"behavior": "unknown", "behavior_cn": "未知", "pose_landmarks": None, "confidence": 0}

        # MediaPipe 处理
        rgb_crop = cv2.cvtColor(person_crop, cv2.COLOR_BGR2RGB)
        results = self.pose.process(rgb_crop)

        if not results.pose_landmarks:
            return {"behavior": "unknown", "behavior_cn": "未知", "pose_landmarks": None, "confidence": 0}

        landmarks = results.pose_landmarks.landmark

        # 分析姿态 → 行为
        behavior = self._classify_behavior(landmarks)

        # 更新行为历史
        if track_id not in self.behavior_history:
            self.behavior_history[track_id] = deque(maxlen=self.window_size)
        self.behavior_history[track_id].append(behavior)

        # 时间平滑：使用最近窗口的多数投票
        smoothed_behavior = self._smooth_behavior(track_id)

        return {
            "behavior": smoothed_behavior,
            "behavior_cn": BEHAVIORS.get(smoothed_behavior, "未知"),
            "pose_landmarks": results.pose_landmarks,
            "confidence": self._get_avg_visibility(landmarks),
        }

    def _classify_behavior(self, landmarks) -> str:
        """基于关键点分类当前帧的行为"""
        mp_pose = self.mp_pose

        # 提取关键点
        nose = landmarks[mp_pose.PoseLandmark.NOSE]
        left_shoulder = landmarks[mp_pose.PoseLandmark.LEFT_SHOULDER]
        right_shoulder = landmarks[mp_pose.PoseLandmark.RIGHT_SHOULDER]
        left_hip = landmarks[mp_pose.PoseLandmark.LEFT_HIP]
        right_hip = landmarks[mp_pose.PoseLandmark.RIGHT_HIP]
        left_knee = landmarks[mp_pose.PoseLandmark.LEFT_KNEE]
        right_knee = landmarks[mp_pose.PoseLandmark.RIGHT_KNEE]
        left_ankle = landmarks[mp_pose.PoseLandmark.LEFT_ANKLE]
        right_ankle = landmarks[mp_pose.PoseLandmark.RIGHT_ANKLE]
        left_wrist = landmarks[mp_pose.PoseLandmark.LEFT_WRIST]
        right_wrist = landmarks[mp_pose.PoseLandmark.RIGHT_WRIST]

        # 计算躯干角度（肩部到臀部的倾斜角）
        shoulder_mid_y = (left_shoulder.y + right_shoulder.y) / 2
        hip_mid_y = (left_hip.y + right_hip.y) / 2
        shoulder_mid_x = (left_shoulder.x + right_shoulder.x) / 2
        hip_mid_x = (left_hip.x + right_hip.x) / 2

        trunk_angle = abs(math.degrees(
            math.atan2(hip_mid_y - shoulder_mid_y, hip_mid_x - shoulder_mid_x)
        ))

        # 膝盖弯曲角度
        knee_angle_left = self._angle_3points(
            left_hip, left_knee, left_ankle
        )
        knee_angle_right = self._angle_3points(
            right_hip, right_knee, right_ankle
        )
        avg_knee_angle = (knee_angle_left + knee_angle_right) / 2

        # 手腕位置相对于肩部
        wrist_above_shoulder = (
            left_wrist.y < left_shoulder.y - 0.05 or
            right_wrist.y < right_shoulder.y - 0.05
        )

        # 行为分类逻辑
        # 1. 向上操作：手臂举过头顶
        if wrist_above_shoulder and (
            left_wrist.y < nose.y or right_wrist.y < nose.y
        ):
            return "reaching_up"

        # 2. 蹲下：膝盖角度很小
        if avg_knee_angle < 100:
            return "crouching"

        # 3. 弯腰：躯干前倾明显
        if trunk_angle < 50:
            return "bending"

        # 4. 坐着：臀部和膝盖高度接近
        hip_knee_diff = abs(hip_mid_y - (left_knee.y + right_knee.y) / 2)
        if hip_knee_diff < 0.08 and avg_knee_angle < 130:
            return "sitting"

        # 5. 默认站立
        return "standing"

    def _angle_3points(self, a, b, c) -> float:
        """计算三个点形成的角度（以 b 为顶点）"""
        ba = np.array([a.x - b.x, a.y - b.y])
        bc = np.array([c.x - b.x, c.y - b.y])

        cos_angle = np.dot(ba, bc) / (np.linalg.norm(ba) * np.linalg.norm(bc) + 1e-6)
        cos_angle = np.clip(cos_angle, -1, 1)
        angle = math.degrees(math.acos(cos_angle))
        return angle

    def _smooth_behavior(self, track_id: int) -> str:
        """基于历史窗口的多数投票平滑行为"""
        if track_id not in self.behavior_history:
            return "unknown"
        history = self.behavior_history[track_id]
        if not history:
            return "unknown"

        # 多数投票
        from collections import Counter
        counts = Counter(history)
        return counts.most_common(1)[0][0]

    def _get_avg_visibility(self, landmarks) -> float:
        """计算所有关键点的平均可见度"""
        visibilities = [lm.visibility for lm in landmarks]
        return sum(visibilities) / len(visibilities) if visibilities else 0

    def cleanup_track(self, track_id: int):
        """清理不再追踪的目标的行为历史"""
        self.behavior_history.pop(track_id, None)
