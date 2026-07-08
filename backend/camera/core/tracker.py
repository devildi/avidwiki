"""
人员追踪模块 - 简化版 ByteTrack 风格追踪器
基于 IoU 匹配的多目标追踪
"""
import numpy as np
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Optional
import time


@dataclass
class Track:
    """追踪目标"""
    track_id: int
    bbox: tuple  # (x1, y1, x2, y2)
    confidence: float
    age: int = 0  # 追踪帧数
    hits: int = 1  # 成功匹配次数
    misses: int = 0  # 连续未匹配次数
    person_id: Optional[int] = None
    person_name: str = "未识别"
    behavior: str = ""
    positions: list = field(default_factory=list)  # 位置历史
    first_seen: float = field(default_factory=time.time)
    last_seen: float = field(default_factory=time.time)

    @property
    def center(self):
        x1, y1, x2, y2 = self.bbox
        return ((x1 + x2) / 2, (y1 + y2) / 2)

    def update(self, bbox, confidence):
        self.bbox = bbox
        self.confidence = confidence
        self.hits += 1
        self.misses = 0
        self.age += 1
        self.last_seen = time.time()
        self.positions.append(self.center)
        # 保留最近 300 个位置
        if len(self.positions) > 300:
            self.positions = self.positions[-300:]


def compute_iou(bbox1, bbox2):
    """计算两个边界框的 IoU"""
    x1 = max(bbox1[0], bbox2[0])
    y1 = max(bbox1[1], bbox2[1])
    x2 = min(bbox1[2], bbox2[2])
    y2 = min(bbox1[3], bbox2[3])

    intersection = max(0, x2 - x1) * max(0, y2 - y1)
    area1 = (bbox1[2] - bbox1[0]) * (bbox1[3] - bbox1[1])
    area2 = (bbox2[2] - bbox2[0]) * (bbox2[3] - bbox2[1])
    union = area1 + area2 - intersection

    return intersection / union if union > 0 else 0


class PersonTracker:
    """基于 IoU 匹配的人员追踪器"""

    def __init__(self, iou_threshold=0.3, max_misses=30, min_hits=3):
        self.iou_threshold = iou_threshold
        self.max_misses = max_misses  # 最大连续未匹配帧数
        self.min_hits = min_hits  # 最少命中次数才认为有效
        self.tracks: dict[int, Track] = {}
        self.next_id = 1
        self.removed_tracks: list[Track] = []  # 最近移除的追踪

    def update(self, detections: list[dict]) -> list[dict]:
        """
        更新追踪状态

        Args:
            detections: PersonDetector.detect() 的输出

        Returns:
            带有 track_id 的检测结果
        """
        if not detections:
            # 没有检测到人，所有追踪增加 miss
            for track in list(self.tracks.values()):
                track.misses += 1
                track.age += 1
                if track.misses > self.max_misses:
                    self._remove_track(track.track_id)
            return []

        det_bboxes = [d["bbox"] for d in detections]
        track_ids = list(self.tracks.keys())

        if not track_ids:
            # 没有现有追踪，全部创建新的
            results = []
            for det in detections:
                track = self._create_track(det["bbox"], det["confidence"])
                det_copy = det.copy()
                det_copy["track_id"] = track.track_id
                det_copy["person_name"] = track.person_name
                det_copy["behavior"] = track.behavior
                results.append(det_copy)
            return results

        # 计算 IoU 矩阵
        track_bboxes = [self.tracks[tid].bbox for tid in track_ids]
        iou_matrix = np.zeros((len(det_bboxes), len(track_bboxes)))
        for i, det_bbox in enumerate(det_bboxes):
            for j, trk_bbox in enumerate(track_bboxes):
                iou_matrix[i, j] = compute_iou(det_bbox, trk_bbox)

        # 贪心匹配
        matched_dets = set()
        matched_trks = set()
        matches = []

        while True:
            if iou_matrix.size == 0:
                break
            max_iou = iou_matrix.max()
            if max_iou < self.iou_threshold:
                break
            i, j = np.unravel_index(iou_matrix.argmax(), iou_matrix.shape)
            matches.append((i, j))
            matched_dets.add(i)
            matched_trks.add(j)
            iou_matrix[i, :] = 0
            iou_matrix[:, j] = 0

        # 更新匹配的追踪
        results = []
        for det_idx, trk_idx in matches:
            tid = track_ids[trk_idx]
            det = detections[det_idx]
            self.tracks[tid].update(det["bbox"], det["confidence"])
            det_copy = det.copy()
            det_copy["track_id"] = tid
            det_copy["person_name"] = self.tracks[tid].person_name
            det_copy["behavior"] = self.tracks[tid].behavior
            results.append(det_copy)

        # 未匹配的检测 → 创建新追踪
        for i, det in enumerate(detections):
            if i not in matched_dets:
                track = self._create_track(det["bbox"], det["confidence"])
                det_copy = det.copy()
                det_copy["track_id"] = track.track_id
                det_copy["person_name"] = track.person_name
                det_copy["behavior"] = track.behavior
                results.append(det_copy)

        # 未匹配的追踪 → 增加 miss
        for j, tid in enumerate(track_ids):
            if j not in matched_trks:
                self.tracks[tid].misses += 1
                self.tracks[tid].age += 1
                if self.tracks[tid].misses > self.max_misses:
                    self._remove_track(tid)

        return results

    def _create_track(self, bbox, confidence) -> Track:
        track = Track(
            track_id=self.next_id,
            bbox=bbox,
            confidence=confidence,
        )
        track.positions.append(track.center)
        self.tracks[self.next_id] = track
        self.next_id += 1
        return track

    def _remove_track(self, track_id):
        if track_id in self.tracks:
            self.removed_tracks.append(self.tracks[track_id])
            # 保留最近 50 个移除的追踪
            if len(self.removed_tracks) > 50:
                self.removed_tracks = self.removed_tracks[-50:]
            del self.tracks[track_id]

    def get_track(self, track_id) -> Optional[Track]:
        return self.tracks.get(track_id)

    def get_active_tracks(self) -> list[Track]:
        """返回所有有效的追踪（命中次数满足最低要求）"""
        return [t for t in self.tracks.values() if t.hits >= self.min_hits]
