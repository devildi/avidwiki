"""
视频处理管道 - 串联检测、追踪、识别、行为分析
"""
import cv2
import numpy as np
import threading
import time
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional, Callable

import config
from core.detector import PersonDetector
from core.tracker import PersonTracker
from core.face_recognizer import FaceRecognizer
from core.pose_analyzer import PoseAnalyzer
from core.reid_analyzer import reid_analyzer

logger = logging.getLogger(__name__)


class VideoStream:
    """线程化视频流读取"""

    def __init__(self, source=0, width=1280, height=720):
        self.source = source
        self.width = width
        self.height = height
        self.cap = None
        self.frame = None
        self.ret = False
        self.running = False
        self._lock = threading.Lock()
        self._thread = None

    def start(self):
        """启动视频流读取线程"""
        src = self.source
        if isinstance(src, str) and src.isdigit():
            src = int(src)

        # 如果是 RTSP 视频流，强制使用 TCP 传输，避免 UDP 丢包导致解码报错
        import os
        if isinstance(src, str) and src.startswith("rtsp://"):
            os.environ["OPENCV_FFMPEG_CAPTURE_OPTIONS"] = "rtsp_transport;tcp"

        self.cap = cv2.VideoCapture(src)
        if not self.cap.isOpened():
            raise RuntimeError(f"无法打开视频源: {self.source}")

        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.width)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.height)

        self.running = True
        self._thread = threading.Thread(target=self._read_loop, daemon=True)
        self._thread.start()
        logger.info(f"视频流已启动: {self.source}")
        return self

    def _read_loop(self):
        while self.running:
            ret, frame = self.cap.read()
            with self._lock:
                self.ret = ret
                self.frame = frame
            if not ret:
                time.sleep(0.1)

    def read(self) -> tuple[bool, Optional[np.ndarray]]:
        with self._lock:
            if self.frame is None:
                return False, None
            return self.ret, self.frame.copy()

    def stop(self):
        self.running = False
        if self._thread:
            self._thread.join(timeout=3)
        if self.cap:
            self.cap.release()
        logger.info(f"视频流已停止: {self.source}")


class DetectionPipeline:
    """完整的检测处理管道"""

    def __init__(self, camera_id: int = 1, camera_name: str = "默认摄像头",
                 source=None, on_event: Callable = None):
        self.camera_id = camera_id
        self.camera_name = camera_name
        self.source = source if source is not None else config.DEFAULT_CAMERA_SOURCE

        # 初始化组件
        self.detector = PersonDetector()
        self.tracker = PersonTracker(max_misses=75)  # 容忍连续 75 帧（约 4-5 秒）丢失，防止短暂遮挡导致 ID 重置
        self.face_recognizer = FaceRecognizer()
        self.pose_analyzer = PoseAnalyzer()

        # 初始化自定义体态分类器（YOLOv8-Cls）
        self.body_classifier = None
        self.body_classes = []
        self._load_body_classifier()

        # 视频流
        self.video_stream: Optional[VideoStream] = None

        # 状态
        self.running = False
        self._thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()
        self._current_frame: Optional[np.ndarray] = None
        self._annotated_frame: Optional[np.ndarray] = None
        self._current_detections: list[dict] = []
        self._frame_count = 0

        # 体态特征自学习匹配缓存
        self._registered_persons_cache = []
        self._last_cache_update = 0.0

        # 事件回调
        self.on_event = on_event

        # 统计
        self.stats = {
            "total_persons_detected": 0,
            "current_persons": 0,
            "fps": 0,
            "last_event_time": None,
        }

    def start(self):
        """启动处理管道"""
        if self.running:
            return

        logger.info(f"启动检测管道: camera_id={self.camera_id}, source={self.source}")

        self.video_stream = VideoStream(
            source=self.source,
            width=config.CAMERA_WIDTH,
            height=config.CAMERA_HEIGHT,
        )
        self.video_stream.start()

        self.running = True
        self._thread = threading.Thread(target=self._process_loop, daemon=True)
        self._thread.start()

    def stop(self):
        """停止处理管道"""
        self.running = False
        if self._thread:
            self._thread.join(timeout=5)
        if self.video_stream:
            self.video_stream.stop()
        logger.info(f"检测管道已停止: camera_id={self.camera_id}")

    def _process_loop(self):
        """主处理循环"""
        target_interval = 1.0 / config.CAMERA_FPS
        face_counter = 0

        while self.running:
            loop_start = time.time()

            # 0. 定期更新注册人员特征缓存（每 8 秒）
            if time.time() - self._last_cache_update > 8.0:
                self._update_registered_persons_cache()
                self._load_body_classifier()

            ret, frame = self.video_stream.read()
            if not ret or frame is None:
                time.sleep(0.05)
                continue

            self._frame_count += 1

            # 1. 人员检测
            detections = self.detector.detect(frame)

            # 2. 多目标追踪
            tracked = self.tracker.update(detections)

            # 3. 人脸识别与体态 ReID 兜底识别
            face_counter += 1
            if face_counter >= config.FACE_RECOGNITION_INTERVAL:
                face_counter = 0
                self._do_face_recognition(frame, tracked)
                self._do_body_reid(frame, tracked)
                self._do_custom_body_classification(frame, tracked)

            # 4. 姿态分析与行为识别
            for det in tracked:
                track_id = det.get("track_id", 0)
                pose_result = self.pose_analyzer.analyze(
                    frame, det["bbox"], track_id
                )
                det["behavior"] = pose_result["behavior_cn"]
                det["pose_landmarks"] = pose_result.get("pose_landmarks")  # 保存姿态骨骼点以供 ReID 抓拍使用

                # 同步行为到追踪器
                track = self.tracker.get_track(track_id)
                if track:
                    track.behavior = pose_result["behavior_cn"]
                    # ─── 数据自动收集：保存人体裁剪图 ───
                    if not hasattr(track, 'crop_save_count'):
                        track.crop_save_count = 0
                    if track.crop_save_count % 15 == 0:
                        self._save_body_crop(frame, det["bbox"], track_id)
                    track.crop_save_count += 1

            # 5. 生成事件
            self._generate_events(frame, tracked)

            # 6. 绘制标注
            annotated = self.detector.draw_detections(frame, tracked)
            self._draw_info_overlay(annotated)

            # 更新状态
            with self._lock:
                self._current_frame = frame
                self._annotated_frame = annotated
                self._current_detections = tracked

            # 更新统计
            elapsed = time.time() - loop_start
            self.stats["fps"] = round(1.0 / max(elapsed, 0.001), 1)
            self.stats["current_persons"] = len(tracked)

            # 帧率控制
            sleep_time = target_interval - elapsed
            if sleep_time > 0:
                time.sleep(sleep_time)

    def _do_face_recognition(self, frame, tracked_detections):
        """对追踪到的人进行人脸识别"""
        for det in tracked_detections:
            track = self.tracker.get_track(det.get("track_id", 0))
            if not track or (track.person_name and track.person_name != "未识别"):
                continue  # 已识别的跳过

            x1, y1, x2, y2 = det["bbox"]
            # 取上半部分作为人脸区域
            face_h = int((y2 - y1) * 0.4)
            face_region = frame[y1:y1 + face_h, x1:x2]

            if face_region.size == 0:
                continue

            match = self.face_recognizer.recognize(face_region)
            if match:
                track.person_id = match["person_id"]
                track.person_name = match["name"]
                det["person_name"] = match["name"]
                det["person_id"] = match["person_id"]
                logger.info(f"识别到: {match['name']} (track_id={track.track_id})")

    def _load_body_classifier(self):
        """加载自定义体态分类器（YOLOv8-Cls），仅当文件变化时重载"""
        try:
            model_path = Path("data/camera/models/body_classifier.pt")
            
            # 记录上一次加载的模型修改时间与存在状态
            if not hasattr(self, "_body_classifier_last_mtime"):
                self._body_classifier_last_mtime = 0
            if not hasattr(self, "_body_classifier_exists"):
                self._body_classifier_exists = False

            current_exists = model_path.exists()
            current_mtime = model_path.stat().st_mtime if current_exists else 0

            # 如果文件存在状态发生改变，或者修改时间改变，才重新加载模型
            if current_exists != self._body_classifier_exists or current_mtime != self._body_classifier_last_mtime:
                self._body_classifier_exists = current_exists
                self._body_classifier_last_mtime = current_mtime

                if current_exists:
                    from ultralytics import YOLO
                    self.body_classifier = YOLO(str(model_path))
                    self.body_classes = self.body_classifier.names
                    logger.info(f"成功加载自定义体态分类器模型，包含类别: {self.body_classes}")
                else:
                    self.body_classifier = None
                    self.body_classes = []
                    logger.info("自定义体态分类器模型文件不存在，已卸载模型。")
        except Exception as e:
            logger.error(f"加载自定义体态分类器模型失败: {e}", exc_info=True)

    def _do_custom_body_classification(self, frame, tracked_detections):
        """利用自定义体态分类器进行检测兜底"""
        if not self.body_classifier:
            return

        for det in tracked_detections:
            track = self.tracker.get_track(det.get("track_id", 0))
            if not track or (track.person_name and track.person_name != "未识别"):
                continue

            x1, y1, x2, y2 = det["bbox"]
            h, w = frame.shape[:2]
            
            # 使用与训练数据一致的 20% 外扩边界框
            box_width = x2 - x1
            box_height = y2 - y1
            pad_w = int(box_width * 0.20)
            pad_h = int(box_height * 0.20)
            
            x1_padded = max(0, x1 - pad_w)
            y1_padded = max(0, y1 - pad_h)
            x2_padded = min(w, x2 + pad_w)
            y2_padded = min(h, y2 + pad_h)
            
            body_crop = frame[y1_padded:y2_padded, x1_padded:x2_padded]

            if body_crop.size == 0:
                continue

            try:
                results = self.body_classifier(body_crop, verbose=False)
                if results and len(results) > 0:
                    probs = results[0].probs
                    top1_idx = probs.top1
                    top1_conf = float(probs.top1conf)
                    
                    if top1_conf >= 0.60:  # 降低阈值至 0.60，使小样本体态分类器更灵敏易识别
                        cls_name = self.body_classes[top1_idx]
                        
                        # 查找关联的注册人员
                        matched_person = None
                        for p in self._registered_persons_cache:
                            p_label = getattr(p, "body_label", "")
                            if p_label == cls_name or p.name == cls_name:
                                matched_person = p
                                break
                                
                        if matched_person:
                            display_name = f"{matched_person.name} (体态)"
                            track.person_id = matched_person.id
                            det["person_id"] = matched_person.id
                        else:
                            display_name = f"{cls_name} (体态)"
                            
                        track.person_name = display_name
                        det["person_name"] = display_name
                        logger.info(f"【体态分类匹配】识别到: {display_name} (置信度={round(top1_conf, 3)}, track_id={track.track_id})")
            except Exception as e:
                logger.error(f"自定义体态分类推理失败: {e}")

    def _save_body_crop(self, frame, bbox, track_id):
        """保存人体裁剪框图片到数据收集器中用于模型训练"""
        try:
            collector_dir = Path("data/camera/body_dataset/collector")
            if not collector_dir.exists():
                collector_dir.mkdir(parents=True, exist_ok=True)

            x1, y1, x2, y2 = bbox
            h, w = frame.shape[:2]
            
            # 为人体边界框向四周外扩 20% 的宽度和高度，以便保留头部/面部及背景上下文
            box_width = x2 - x1
            box_height = y2 - y1
            pad_w = int(box_width * 0.20)
            pad_h = int(box_height * 0.20)
            
            x1_padded = max(0, x1 - pad_w)
            y1_padded = max(0, y1 - pad_h)
            x2_padded = min(w, x2 + pad_w)
            y2_padded = min(h, y2 + pad_h)
            
            body_crop = frame[y1_padded:y2_padded, x1_padded:x2_padded]

            if body_crop.size == 0:
                return

            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
            filename = f"body_{track_id}_{timestamp}.jpg"
            filepath = collector_dir / filename
            cv2.imwrite(str(filepath), body_crop, [cv2.IMWRITE_JPEG_QUALITY, 95])
        except Exception as e:
            logger.error(f"保存数据收集样本失败: {e}")

    def _update_registered_persons_cache(self):
        """定期从数据库重新加载已注册人员的体态特征"""
        try:
            from database.db import get_db_session
            from database.models import Person
            with get_db_session() as db:
                persons = db.query(Person).filter(Person.is_active == True).all()
                # 预读到内存缓存，脱离数据库 session 限制并在线程安全下对比
                self._registered_persons_cache = [
                    type('PersonCache', (object,), {
                        'id': p.id,
                        'name': p.name,
                        'body_label': getattr(p, "body_label", ""),
                        'body_signature': p.body_signature
                    })() for p in persons
                ]
                self._last_cache_update = time.time()
        except Exception as e:
            logger.error(f"更新注册人员体态特征缓存失败: {e}")

    def _do_body_reid(self, frame, tracked_detections):
        """对未进行人脸识别的追踪人员进行体态 ReID 识别"""
        if not self._registered_persons_cache:
            return

        for det in tracked_detections:
            track = self.tracker.get_track(det.get("track_id", 0))
            if not track or (track.person_name and track.person_name != "未识别"):
                continue  # 已经被人脸匹配成功，或已识别，或追踪丢失

            # 获取 MediaPipe 骨骼点
            pose_landmarks = det.get("pose_landmarks")
            if not pose_landmarks:
                continue

            # 提取特征
            features = reid_analyzer.extract_features(frame, det["bbox"], pose_landmarks)
            if not features:
                continue

            # 进行 1-to-N 匹配
            match = reid_analyzer.match_identity(features, self._registered_persons_cache)
            if match:
                track.person_id = match["person_id"]
                track.person_name = match["name"]
                det["person_name"] = match["name"]
                det["person_id"] = match["person_id"]
                logger.info(f"【体态重识别成功】匹配到人员: {match['name']} (偏差度: {round(match['distance'], 3)})")

    def _generate_events(self, frame, tracked_detections):
        """根据检测结果生成事件"""
        if not self.on_event:
            return

        for det in tracked_detections:
            track = self.tracker.get_track(det.get("track_id", 0))
            if not track:
                continue

            # 新人进入事件（命中3帧后首次触发）
            if track.hits == 3:
                self._emit_event(frame, det, track, "enter", "有人进入检测区域")

            # 行为变化事件（每隔一段时间记录）
            if track.age > 0 and track.age % 90 == 0:  # 约每6秒
                behavior = det.get("behavior", "")
                if behavior:
                    self._emit_event(frame, det, track, "behavior", behavior)

        # 检查离开事件
        for removed in self.tracker.removed_tracks[-5:]:  # 最近移除的
            if removed.hits >= 3:
                self._emit_event(None, None, removed, "leave", "人员离开检测区域")
        self.tracker.removed_tracks.clear()

    def _emit_event(self, frame, det, track, event_type, description):
        """发送事件"""
        # 事件防抖去重逻辑：同一个事件类型 + 同一个人，在 8 秒内不重复发送，防止 ID 抖动产生重复事件记录
        now = time.time()
        event_key = (event_type, track.person_id, track.person_name)
        if not hasattr(self, "_last_event_timestamps"):
            self._last_event_timestamps = {}
        last_time = self._last_event_timestamps.get(event_key, 0)
        if now - last_time < 8.0:
            logger.debug(f"【事件防抖拦截】8秒内重复触发 {event_type} 事件（人员: {track.person_name}），已自动过滤。")
            return
        self._last_event_timestamps[event_key] = now

        snapshot_path = ""
        body_features_str = ""

        if frame is not None and det:
            snapshot_path = self._save_snapshot(frame, det)
            # 提取体态/衣物特征以备后期用户标注学习
            pose_landmarks = det.get("pose_landmarks")
            if pose_landmarks:
                feat = reid_analyzer.extract_features(frame, det["bbox"], pose_landmarks)
                if feat:
                    import json
                    body_features_str = json.dumps(feat)

        event_data = {
            "camera_id": self.camera_id,
            "camera_name": self.camera_name,
            "person_id": track.person_id,
            "person_name": track.person_name or "未识别",
            "event_type": event_type,
            "behavior": description,
            "confidence": det["confidence"] if det else track.confidence,
            "snapshot_path": snapshot_path,
            "body_features": body_features_str,
            "timestamp": datetime.utcnow().isoformat(),
            "bbox": det["bbox"] if det else track.bbox,
        }

        self.stats["last_event_time"] = event_data["timestamp"]

        if self.on_event:
            try:
                self.on_event(event_data)
            except Exception as e:
                logger.error(f"事件回调异常: {e}")

    def _save_snapshot(self, frame, det) -> str:
        """保存事件截图"""
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
            filename = f"snap_{self.camera_id}_{timestamp}.jpg"
            filepath = config.SNAPSHOTS_DIR / filename
            cv2.imwrite(str(filepath), frame, [cv2.IMWRITE_JPEG_QUALITY, config.SNAPSHOT_QUALITY])
            return str(filepath)
        except Exception as e:
            logger.error(f"截图保存失败: {e}")
            return ""

    def _draw_info_overlay(self, frame):
        """在画面上绘制信息覆盖层"""
        h, w = frame.shape[:2]

        # 半透明信息栏
        overlay = frame.copy()
        cv2.rectangle(overlay, (0, 0), (300, 90), (0, 0, 0), -1)
        cv2.addWeighted(overlay, 0.6, frame, 0.4, 0, frame)

        # 文字信息
        y_offset = 25
        cv2.putText(frame, f"Camera: {self.camera_name}",
                     (10, y_offset), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 200), 1)
        y_offset += 25
        cv2.putText(frame, f"Persons: {self.stats['current_persons']}  FPS: {self.stats['fps']}",
                     (10, y_offset), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 200), 1)
        y_offset += 25
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        cv2.putText(frame, now,
                     (10, y_offset), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (200, 200, 200), 1)

    def get_annotated_frame(self) -> Optional[np.ndarray]:
        """获取当前标注帧"""
        with self._lock:
            return self._annotated_frame.copy() if self._annotated_frame is not None else None

    def get_raw_frame(self) -> Optional[np.ndarray]:
        """获取当前原始帧"""
        with self._lock:
            return self._current_frame.copy() if self._current_frame is not None else None

    def get_detections(self) -> list[dict]:
        """获取当前检测结果"""
        with self._lock:
            return self._current_detections.copy()

    @property
    def is_running(self) -> bool:
        return self.running


# 全局管道管理器
class PipelineManager:
    """管理多个检测管道（多摄像头）"""

    def __init__(self):
        self.pipelines: dict[int, DetectionPipeline] = {}
        self._event_callbacks: list[Callable] = []

    def add_pipeline(self, camera_id: int, camera_name: str, source) -> DetectionPipeline:
        if camera_id in self.pipelines:
            self.pipelines[camera_id].stop()

        pipeline = DetectionPipeline(
            camera_id=camera_id,
            camera_name=camera_name,
            source=source,
            on_event=self._dispatch_event,
        )
        self.pipelines[camera_id] = pipeline
        return pipeline

    def start_all(self):
        for pipeline in self.pipelines.values():
            if not pipeline.is_running:
                pipeline.start()

    def stop_all(self):
        for pipeline in self.pipelines.values():
            pipeline.stop()

    def get_pipeline(self, camera_id: int) -> Optional[DetectionPipeline]:
        return self.pipelines.get(camera_id)

    def on_event(self, callback: Callable):
        self._event_callbacks.append(callback)

    def _dispatch_event(self, event_data):
        for cb in self._event_callbacks:
            try:
                cb(event_data)
            except Exception as e:
                logger.error(f"事件分发异常: {e}")


# 全局单例
pipeline_manager = PipelineManager()
