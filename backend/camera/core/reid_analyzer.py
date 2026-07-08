"""
体态重识别分析与相似度匹配模块 - 基于骨骼比例与衣着 HSV 颜色
"""
import cv2
import numpy as np
import math
import json
import logging
from typing import Optional

logger = logging.getLogger(__name__)


class BodyReIDAnalyzer:
    """提取与匹配人员体态特征的分析器"""

    def __init__(self):
        # 匹配阈值定义
        self.ratio_match_threshold = 0.12  # 骨骼比例偏差在 12% 以内判定为相同体态
        self.color_match_threshold = 0.15  # 颜色偏差在 15% 以内判定为相同衣着
        self.combined_threshold = 0.15      # 综合体态判定阈值

    def extract_features(self, frame: np.ndarray, bbox: tuple, pose_landmarks) -> Optional[dict]:
        """
        根据人物裁剪框和 MediaPipe 关键点提取体态比例与 HSV 颜色特征

        Args:
            frame: 原始视频帧 (BGR)
            bbox: 人物检测框 (x1, y1, x2, y2)
            pose_landmarks: MediaPipe 提取出的 33 个姿态骨骼点

        Returns:
            {
                "ratios": [肩宽/臀宽比, 躯干/腿长比, 大腿/小腿比, 手臂/躯干比],
                "colors": [上衣H, 上衣S, 上衣V, 下装H, 下装S, 下装V]
            } 或 None
        """
        if not pose_landmarks or frame is None:
            return None

        try:
            # 1. 提取骨骼比例 (Ratios) - 解剖学特征，不随尺度/远近变化
            ratios = self._extract_bone_ratios(pose_landmarks.landmark)
            if not ratios:
                return None

            # 2. 提取衣着 HSV 颜色 (Colors) - 短期衣着特征
            colors = self._extract_clothing_colors(frame, bbox)
            if not colors:
                return None

            return {
                "ratios": ratios,
                "colors": colors
            }
        except Exception as e:
            logger.error(f"提取体态特征失败: {e}")
            return None

    def compare(self, feat_a: dict, feat_b: dict, same_day: bool = True) -> float:
        """
        比对两组体态特征的差异度 (返回 0 到 1 之间的距离值，值越小越相似)

        Args:
            feat_a: 特征 A
            feat_b: 特征 B
            same_day: 是否是同一天/同一次会话（若是，则将衣着颜色纳入比对；若不是，仅比对骨骼比例）
        """
        try:
            # 1. 骨骼比例差异 (均值百分比偏差)
            r_a = feat_a["ratios"]
            r_b = feat_b["ratios"]
            ratio_diffs = []
            for val_a, val_b in zip(r_a, r_b):
                ratio_diffs.append(abs(val_a - val_b) / (max(val_a, val_b) + 1e-6))
            ratio_dist = sum(ratio_diffs) / len(ratio_diffs)

            if not same_day:
                # 跨天匹配：仅使用骨骼比例特征进行判断
                return ratio_dist

            # 2. 衣物 HSV 颜色差异
            c_a = feat_a["colors"]
            c_b = feat_b["colors"]
            
            # 上衣和下装分别计算
            dist_upper = self._hsv_distance(c_a[:3], c_b[:3])
            dist_lower = self._hsv_distance(c_a[3:], c_b[3:])
            color_dist = (dist_upper + dist_lower) / 2.0

            # 3. 混合匹配：60% 骨骼比例 + 40% 衣着颜色
            combined_dist = 0.6 * ratio_dist + 0.4 * color_dist
            return combined_dist
        except Exception as e:
            logger.error(f"比对特征失败: {e}")
            return 1.0

    def match_identity(self, current_feat: dict, registered_persons: list) -> Optional[dict]:
        """
        在已注册的人员体态数据库中寻找最匹配的身份

        Args:
            current_feat: 当前提取出的特征
            registered_persons: 人员列表，每个元素包含 { "id", "name", "body_signature" (JSON 字符串) }
        """
        best_match = None
        min_distance = 999.0

        for person in registered_persons:
            if not person.body_signature:
                continue

            try:
                sig = json.loads(person.body_signature)
            except Exception:
                continue

            # 进行相似度比对
            distance = self.compare(current_feat, sig, same_day=True)

            if distance < min_distance and distance < self.combined_threshold:
                min_distance = distance
                best_match = {
                    "person_id": person.id,
                    "name": person.name,
                    "distance": distance,
                    "confidence": max(0.0, 1.0 - distance)
                }

        return best_match

    def merge_signatures(self, old_sig_str: str, new_feat: dict, lr: float = 0.3) -> str:
        """
        合并体态特征（利用增量移动平均更新注册特征库）

        Args:
            old_sig_str: 现有的 body_signature 字段的 JSON 字符串（若为空则新建）
            new_feat: 要并入的新特征 dict
            lr: 学习率 (0-1)，越大对新特性的融合越快
        """
        if not old_sig_str:
            return json.dumps(new_feat)

        try:
            old_sig = json.loads(old_sig_str)
            merged = {}

            # 融合骨骼比例
            merged["ratios"] = []
            for o_val, n_val in zip(old_sig["ratios"], new_feat["ratios"]):
                merged["ratios"].append((1.0 - lr) * o_val + lr * n_val)

            # 融合颜色特征
            merged["colors"] = []
            for o_val, n_val in zip(old_sig["colors"], new_feat["colors"]):
                merged["colors"].append((1.0 - lr) * o_val + lr * n_val)

            return json.dumps(merged)
        except Exception as e:
            logger.error(f"合并特征失败: {e}")
            return json.dumps(new_feat)

    # ── 内部辅助函数 ──

    def _extract_bone_ratios(self, landmarks) -> Optional[list[float]]:
        """计算姿态估计的骨骼点相对长度比例"""
        try:
            def dist(p1, p2):
                return math.sqrt((p1.x - p2.x)**2 + (p1.y - p2.y)**2 + (p1.z - p2.z)**2)

            # 获取关键点对象
            left_shoulder = landmarks[11]
            right_shoulder = landmarks[12]
            left_hip = landmarks[23]
            right_hip = landmarks[24]
            left_knee = landmarks[25]
            right_knee = landmarks[26]
            left_ankle = landmarks[27]
            right_ankle = landmarks[28]
            left_wrist = landmarks[15]
            right_wrist = landmarks[16]

            # 1. 肩宽 / 臀宽
            shoulder_width = dist(left_shoulder, right_shoulder)
            hip_width = dist(left_hip, right_hip)
            ratio_shoulder_hip = shoulder_width / (hip_width + 1e-6)

            # 2. 躯干长度 / 双腿平均长度
            shoulder_mid_x = (left_shoulder.x + right_shoulder.x) / 2
            shoulder_mid_y = (left_shoulder.y + right_shoulder.y) / 2
            shoulder_mid_z = (left_shoulder.z + right_shoulder.z) / 2
            class Point:
                def __init__(self, x, y, z):
                    self.x, self.y, self.z = x, y, z
            
            shoulder_mid = Point(shoulder_mid_x, shoulder_mid_y, shoulder_mid_z)
            hip_mid_x = (left_hip.x + right_hip.x) / 2
            hip_mid_y = (left_hip.y + right_hip.y) / 2
            hip_mid_z = (left_hip.z + right_hip.z) / 2
            hip_mid = Point(hip_mid_x, hip_mid_y, hip_mid_z)
            
            torso_length = dist(shoulder_mid, hip_mid)
            
            left_leg = dist(left_hip, left_knee) + dist(left_knee, left_ankle)
            right_leg = dist(right_hip, right_knee) + dist(right_knee, right_ankle)
            avg_leg_length = (left_leg + right_leg) / 2.0
            
            ratio_torso_leg = torso_length / (avg_leg_length + 1e-6)

            # 3. 大腿长度 / 小腿长度
            thigh_length = (dist(left_hip, left_knee) + dist(right_hip, right_knee)) / 2.0
            calf_length = (dist(left_knee, left_ankle) + dist(right_knee, right_ankle)) / 2.0
            ratio_upper_lower_leg = thigh_length / (calf_length + 1e-6)

            # 4. 手臂长度 / 躯干长度
            left_arm = dist(left_shoulder, left_wrist)
            right_arm = dist(right_shoulder, right_wrist)
            avg_arm_length = (left_arm + right_arm) / 2.0
            ratio_arm_torso = avg_arm_length / (torso_length + 1e-6)

            # 对异常值进行保护
            ratios = [ratio_shoulder_hip, ratio_torso_leg, ratio_upper_lower_leg, ratio_arm_torso]
            if any(math.isnan(x) or math.isinf(x) or x <= 0 for x in ratios):
                return None
            return ratios
        except Exception:
            return None

    def _extract_clothing_colors(self, frame: np.ndarray, bbox: tuple) -> Optional[list[float]]:
        """提取上装与下装中心区域的平均 HSV 颜色向量"""
        try:
            x1, y1, x2, y2 = bbox
            h, w = frame.shape[:2]
            bw = x2 - x1
            bh = y2 - y1

            # 1. 截取胸腹部区域 (约占据人体高度的 25% ~ 50%) -> 上衣颜色
            ux1 = int(max(0, x1 + 0.25 * bw))
            ux2 = int(min(w, x1 + 0.75 * bw))
            uy1 = int(max(0, y1 + 0.25 * bh))
            uy2 = int(min(h, y1 + 0.50 * bh))
            
            # 2. 截取下肢大腿区域 (约占据人体高度的 60% ~ 80%) -> 裤装颜色
            lx1 = int(max(0, x1 + 0.25 * bw))
            lx2 = int(min(w, x1 + 0.75 * bw))
            ly1 = int(max(0, y1 + 0.60 * bh))
            ly2 = int(min(h, y1 + 0.80 * bh))

            upper_crop = frame[uy1:uy2, ux1:ux2]
            lower_crop = frame[ly1:ly2, lx1:lx2]

            if upper_crop.size == 0 or lower_crop.size == 0:
                return None

            # 计算 HSV
            upper_hsv = cv2.cvtColor(upper_crop, cv2.COLOR_BGR2HSV)
            lower_hsv = cv2.cvtColor(lower_crop, cv2.COLOR_BGR2HSV)

            # 计算各个通道的中位数/均值，防御阴影和极亮噪点
            u_avg = cv2.mean(upper_hsv)[:3]
            l_avg = cv2.mean(lower_hsv)[:3]

            return [
                u_avg[0], u_avg[1], u_avg[2],  # 上衣 HSV
                l_avg[0], l_avg[1], l_avg[2]   # 下装 HSV
            ]
        except Exception:
            return None

    def _hsv_distance(self, hsv1: list[float], hsv2: list[float]) -> float:
        """计算两组 HSV 颜色的标准化欧氏距离"""
        h1, s1, v1 = hsv1
        h2, s2, v2 = hsv2

        # 1. H 通道为圆形循环 (0 ~ 180)
        dh = min(abs(h1 - h2), 180 - abs(h1 - h2)) / 90.0
        # 2. S、V 通道线性差异 (0 ~ 255)
        ds = abs(s1 - s2) / 255.0
        dv = abs(v1 - v2) / 255.0

        # 标准化距离，颜色差异加权
        return float(math.sqrt(0.5 * dh**2 + 0.3 * ds**2 + 0.2 * dv**2))


# 全局单例
reid_analyzer = BodyReIDAnalyzer()
