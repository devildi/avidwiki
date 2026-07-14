"use client";

import React, { useState, useEffect, useRef } from 'react';
import Link from 'next/link';
import Navbar from '../../components/Navbar';
import { Play, Square, Video, Plus, UserPlus, AlertTriangle, ShieldCheck, Clock, Camera as CameraIcon, Trash2, RefreshCw, Folder, FolderOpen, ArrowLeft, Check, Calendar, Brain } from 'lucide-react';
import clsx from 'clsx';

interface Camera {
  id: number;
  name: string;
  source: string;
  location: string;
  is_active: boolean;
  is_running: boolean;
  stats: {
    fps?: number;
    current_persons?: number;
    total_persons_detected?: number;
  };
}

interface EventLog {
  id: number;
  person_name: string;
  camera_name: string;
  event_type: string;
  behavior: string;
  confidence: number;
  snapshot_path: string;
  timestamp: string;
  bbox?: {
    x: number;
    y: number;
    w: number;
    h: number;
  };
}

interface Person {
  id: number;
  name: string;
  department: string;
  role: string;
  face_image_path: string;
}

export default function MonitoringPage() {
  const [cameras, setCameras] = useState<Camera[]>([]);
  const [events, setEvents] = useState<EventLog[]>([]);
  const [persons, setPersons] = useState<Person[]>([]);
  
  // Active states
  const [selectedCameraId, setSelectedCameraId] = useState<number | null>(null);
  const [isAddingCamera, setIsAddingCamera] = useState(false);
  const [isRegisteringPerson, setIsRegisteringPerson] = useState(false);
  const [isRegistering, setIsRegistering] = useState(false);
  
  // Forms
  const [newCamera, setNewCamera] = useState({ name: '', source: '0', location: '' });
  const [sourceType, setSourceType] = useState<'local' | 'rtsp'>('local');
  const [detectedDevices, setDetectedDevices] = useState<{ id: string; name: string }[]>([]);
  const [isDetecting, setIsDetecting] = useState(false);
  const [cameraActionLoadingId, setCameraActionLoadingId] = useState<number | null>(null);
  const [newPerson, setNewPerson] = useState({ name: '', department: '', role: '运维' });
  const [faceFile, setFaceFile] = useState<File | null>(null);
  
  // Real-time Event Feed
  const [wsConnected, setWsConnected] = useState(false);
  const [liveEvents, setLiveEvents] = useState<any[]>([]);
  const [streamError, setStreamError] = useState(false);
  const [snapshotPath, setSnapshotPath] = useState<string>('');
  const [newSnapshotPath, setNewSnapshotPath] = useState<string>('');
  const [isBackendLoading, setIsBackendLoading] = useState(false);
  const [pageLoading, setPageLoading] = useState(true);
  const [filterDate, setFilterDate] = useState<string>('');
  const [historyPage, setHistoryPage] = useState(1);
  const [historyTotal, setHistoryTotal] = useState(0);
  const historyPageSize = 15;
  
  const filterDateRef = useRef(filterDate);
  useEffect(() => {
    filterDateRef.current = filterDate;
  }, [filterDate]);
  
  // Folder picker states
  const [isFolderPickerOpen, setIsFolderPickerOpen] = useState(false);
  const [pickerCurrentPath, setPickerCurrentPath] = useState<string>('');
  const [pickerParentPath, setPickerParentPath] = useState<string>('');
  const [pickerSubdirs, setPickerSubdirs] = useState<string[]>([]);
  const [selectedPickerPath, setSelectedPickerPath] = useState<string>('');
  
  const [isLoading, setIsLoading] = useState({ cameras: true, events: true, persons: true });
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimeoutRef = useRef<any>(null);
  
  const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://127.0.0.1:8000';
  const WS_BASE = API_BASE.replace(/^http/, 'ws');

  // Derived render variables
  const activeCamera = cameras.find(c => c.id === selectedCameraId);
  const videoFeedUrl = activeCamera?.is_running 
    ? `${API_BASE}/api/stream/${activeCamera.id}`
    : null;

  const fetchEvents = async () => {
    try {
      let eventUrl = `${API_BASE}/api/events?page=${historyPage}&page_size=${historyPageSize}`;
      const currentDate = filterDateRef.current;
      if (currentDate) {
        eventUrl += `&start_date=${currentDate}T00:00:00&end_date=${currentDate}T23:59:59`;
      }
      const eventRes = await fetch(eventUrl);
      if (eventRes.ok) {
        const eventData = await eventRes.json();
        setEvents(eventData.items || []);
        setHistoryTotal(eventData.total || 0);
      }
    } catch (e) {
      console.error("Failed to fetch events:", e);
    }
  };

  // Reset to page 1 when date filter changes
  useEffect(() => {
    setHistoryPage(1);
  }, [filterDate]);

  // Re-fetch historical events when page or filterDate changes
  useEffect(() => {
    fetchEvents();
  }, [historyPage, filterDate]);

  // Fetch initial data
  const fetchData = async () => {
    try {
      // 1. Fetch Status
      const statusRes = await fetch(`${API_BASE}/api/status`);
      if (statusRes.ok) {
        const statusData = await statusRes.json();
        if (statusData.status === 'loading') {
          setErrorMsg(null);
          setIsBackendLoading(true);
          setIsLoading({ cameras: true, events: true, persons: true });
          setPageLoading(true);
          // Poll again in 2 seconds
          setTimeout(fetchData, 2000);
          return;
        }
      }

      setIsBackendLoading(false);
      setErrorMsg(null);

      // 2. Fetch Cameras
      const camRes = await fetch(`${API_BASE}/api/cameras`);
      if (camRes.ok) {
        const camData = await camRes.json();
        setCameras(camData.items || []);
        if (camData.items && camData.items.length > 0 && selectedCameraId === null) {
          setSelectedCameraId(camData.items[0].id);
        }
      }

      // 3. Fetch Historical Events
      await fetchEvents();

      // 4. Fetch Registered Persons
      const personRes = await fetch(`${API_BASE}/api/persons`);
      if (personRes.ok) {
        const personData = await personRes.json();
        setPersons(personData.items || []);
      }

      // 5. Fetch Snapshot Path
      const pathRes = await fetch(`${API_BASE}/api/camera-settings/snapshot-path`);
      if (pathRes.ok) {
        const pathData = await pathRes.json();
        setSnapshotPath(pathData.path);
        setNewSnapshotPath(pathData.path);
      }

      setIsLoading({ cameras: false, events: false, persons: false });
      setPageLoading(false);
    } catch (error) {
      console.error("Failed to fetch camera monitoring data:", error);
      setIsBackendLoading(false);
      setErrorMsg("连接后端API服务失败，请确认后端已启动。如果是刚重启后台，系统可能正在加载模型中，请稍候...");
      setPageLoading(true);
      // Poll again in 3 seconds to auto-recover when backend is back online
      setTimeout(fetchData, 3000);
    }
  };

  const detectCameras = async () => {
    setIsDetecting(true);
    try {
      const res = await fetch(`${API_BASE}/api/cameras/detect`);
      if (res.ok) {
        const data = await res.json();
        setDetectedDevices(data.devices || []);
        if (data.devices && data.devices.length > 0) {
          setNewCamera(prev => ({ ...prev, source: data.devices[0].id }));
        } else {
          setNewCamera(prev => ({ ...prev, source: '' }));
        }
      }
    } catch (e) {
      console.error("Failed to detect cameras:", e);
    } finally {
      setIsDetecting(false);
    }
  };

  useEffect(() => {
    fetchData();
    
    // Connect WebSocket for real-time events
    connectWebSocket();

    return () => {
      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current);
      }
      if (wsRef.current) {
        wsRef.current.close();
      }
    };
  }, []);

  // Reset stream error when active camera changes or starts/stops
  useEffect(() => {
    setStreamError(false);
  }, [selectedCameraId, cameras]);

  const connectWebSocket = () => {
    try {
      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current);
      }
      if (wsRef.current) {
        wsRef.current.onclose = null;
        wsRef.current.onerror = null;
        wsRef.current.close();
      }

      const socket = new WebSocket(`${WS_BASE}/ws/events`);
      wsRef.current = socket;

      socket.onopen = () => {
        if (socket !== wsRef.current) return;
        setWsConnected(true);
        console.log("Monitoring WebSocket connected");
      };

      socket.onmessage = (event) => {
        console.log("【WebSocket 收到消息】:", event.data);
        if (socket !== wsRef.current) {
          console.warn("【WebSocket 消息忽略】: socket 与 wsRef.current 不匹配", socket, wsRef.current);
          return;
        }
        try {
          const eventData = JSON.parse(event.data);
          console.log("【WebSocket 解析成功】:", eventData);
          // Add to live alerts list (keep recent 15 events)
          setLiveEvents(prev => [eventData, ...prev].slice(0, 15));
          
          // Re-fetch historical events to stay up to date
          console.log("【WebSocket 触发拉取】: 正在以当前筛选条件重新获取事件记录...");
          fetchEvents();
        } catch (e) {
          console.error("【WebSocket 解析失败】:", e);
        }
      };

      socket.onclose = () => {
        if (socket !== wsRef.current) return;
        setWsConnected(false);
        console.log("Monitoring WebSocket disconnected. Retrying in 5s...");
        reconnectTimeoutRef.current = setTimeout(connectWebSocket, 5000);
      };

      socket.onerror = (e) => {
        if (socket !== wsRef.current) return;
        console.warn("WebSocket error (safe reconnecting):", e);
        socket.close();
      };
    } catch (e) {
      console.warn("WebSocket connection failure (safe reconnecting):", e);
    }
  };

  // Camera Management Handlers
  const handleStartCamera = async (id: number) => {
    setCameraActionLoadingId(id);
    try {
      const res = await fetch(`${API_BASE}/api/cameras/${id}/start`, { method: 'POST' });
      if (res.ok) {
        fetchData();
      } else {
        const errorData = await res.json();
        alert(errorData.detail || "启动摄像头失败，请检查摄像头设备连接或系统权限");
      }
    } catch (e) {
      console.error(e);
      alert("连接服务器失败，请确保后端服务正常运行");
    } finally {
      setCameraActionLoadingId(null);
    }
  };

  const handleStopCamera = async (id: number) => {
    setCameraActionLoadingId(id);
    try {
      const res = await fetch(`${API_BASE}/api/cameras/${id}/stop`, { method: 'POST' });
      if (res.ok) {
        fetchData();
      }
    } catch (e) {
      console.error(e);
    } finally {
      setCameraActionLoadingId(null);
    }
  };

  const handleDeleteCamera = async (id: number) => {
    if (!confirm("确定要删除该摄像头吗？这会清除其所有监控记录！")) return;
    try {
      const res = await fetch(`${API_BASE}/api/cameras/${id}`, { method: 'DELETE' });
      if (res.ok) {
        if (selectedCameraId === id) setSelectedCameraId(null);
        fetchData();
      }
    } catch (e) {
      console.error(e);
    }
  };

  const handleCreateCamera = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newCamera.name || !newCamera.source) return;

    try {
      const res = await fetch(`${API_BASE}/api/cameras`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(newCamera),
      });

      if (res.ok) {
        setIsAddingCamera(false);
        setNewCamera({ name: '', source: '0', location: '' });
        fetchData();
      }
    } catch (e) {
      console.error(e);
    }
  };

  const handleUpdateSnapshotPath = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newSnapshotPath.trim()) return;
    try {
      const res = await fetch(`${API_BASE}/api/camera-settings/snapshot-path`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ path: newSnapshotPath }),
      });
      if (res.ok) {
        const data = await res.json();
        setSnapshotPath(data.path);
        setNewSnapshotPath(data.path);
        alert("截图存储目录修改成功！已更新为: " + data.path);
      } else {
        const err = await res.json();
        alert(`修改存储路径失败: ${err.detail || '未知错误'}`);
      }
    } catch (e) {
      console.error(e);
      alert("请求修改存储路径失败");
    }
  };

  const loadPickerDirs = async (path: string = '') => {
    try {
      const res = await fetch(`${API_BASE}/api/camera-settings/list-dirs`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ path }),
      });
      if (res.ok) {
        const data = await res.json();
        setPickerCurrentPath(data.current_path);
        setPickerParentPath(data.parent_path);
        setPickerSubdirs(data.subdirs || []);
        setSelectedPickerPath(data.current_path);
      }
    } catch (e) {
      console.error("Failed to load directories:", e);
    }
  };

  // Person Registration Handlers
  const handleRegisterPerson = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newPerson.name || !faceFile) {
      alert("请填写姓名并上传人脸照片");
      return;
    }

    try {
      setIsRegistering(true);
      const formData = new FormData();
      formData.append("name", newPerson.name);
      formData.append("department", newPerson.department);
      formData.append("role", newPerson.role);
      formData.append("face_image", faceFile);

      const res = await fetch(`${API_BASE}/api/persons`, {
        method: 'POST',
        body: formData,
      });

      if (res.ok) {
        setIsRegisteringPerson(false);
        setNewPerson({ name: '', department: '', role: '运维' });
        setFaceFile(null);
        fetchData();
      } else {
        const err = await res.json();
        alert(`注册失败: ${err.detail || '无法识别人脸'}`);
      }
    } catch (e) {
      console.error(e);
      alert("注册接口请求失败");
    } finally {
      setIsRegistering(false);
    }
  };

  const handleUnregisterPerson = async (id: number) => {
    if (!confirm("确定要注销该人员吗？这会移除其注册人脸和体态特征！")) return;
    try {
      const res = await fetch(`${API_BASE}/api/persons/${id}`, { method: 'DELETE' });
      if (res.ok) {
        fetchData();
      }
    } catch (e) {
      console.error(e);
    }
  };

  // Format Helper
  const parseUTC = (isoString: string): Date => {
    if (!isoString) return new Date();
    // 如果没有时区标识，自动补上 "Z"（因为后端写入数据库并返回的是 naive 的 UTC 时间）
    const utcString = (isoString.endsWith('Z') || isoString.includes('+')) ? isoString : `${isoString}Z`;
    return new Date(utcString);
  };

  const formatTime = (isoString: string) => {
    try {
      return parseUTC(isoString).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
    } catch (e) {
      return isoString;
    }
  };

  const getSnapshotUrl = (rawPath: string) => {
    if (!rawPath) return '';
    // snapshot_path is absolute backend path, like /Users/.../data/camera/snapshots/snap_1.jpg
    // we need to return /snapshots/snap_1.jpg relative to API_BASE
    const filename = rawPath.split('/').pop();
    return `${API_BASE}/snapshots/${filename}`;
  };

  return (
    <div className="min-h-screen bg-neutral-900 text-neutral-100 flex flex-col overflow-x-hidden">
      <Navbar />

      <main className="flex-1 p-6 md:p-8 max-w-7xl mx-auto w-full flex flex-col min-h-0">
        {pageLoading ? (
          /* Page-specific Loading Panel inside the page layout (Navbar remains visible and clickable!) */
          <div className="w-full flex-1 flex flex-col items-center justify-center p-6 text-neutral-100 font-sans relative overflow-hidden min-h-[400px]">
            {/* Background glow effects */}
            <div className="absolute top-1/4 left-1/4 w-[300px] h-[300px] bg-purple-500/5 rounded-full blur-[100px] pointer-events-none animate-pulse"></div>
            <div className="absolute bottom-1/4 right-1/4 w-[300px] h-[300px] bg-pink-500/5 rounded-full blur-[100px] pointer-events-none animate-pulse"></div>

            <div className="flex flex-col items-center max-w-sm text-center relative z-10">
              {/* Glowing loader */}
              <div className="relative mb-6">
                <div className="absolute inset-0 rounded-full bg-gradient-to-tr from-purple-500 to-pink-500 blur-md opacity-40 animate-pulse"></div>
                <div className="h-12 w-12 rounded-full border-4 border-neutral-800 border-t-purple-500 animate-spin relative"></div>
              </div>
              
              <h2 className="text-xl font-bold text-neutral-200 tracking-wide mb-2">机房行为监测系统</h2>
              
              {isBackendLoading ? (
                <p className="text-sm text-purple-400 font-medium animate-pulse mt-2 px-4 leading-relaxed">
                  正在加载 AI 向量分析模型 (sentence-transformers/all-MiniLM-L6-v2)，这在首次启动或重启时可能需要 10-30 秒，请稍候...
                </p>
              ) : errorMsg ? (
                <div className="mt-2 px-4">
                  <p className="text-xs text-red-400 leading-relaxed mb-4">{errorMsg}</p>
                  <button 
                    onClick={fetchData}
                    className="mx-auto flex items-center gap-2 px-5 py-2.5 bg-red-900/40 hover:bg-red-900/60 border border-red-800/80 text-red-200 text-xs font-semibold rounded-xl transition-all shadow-lg active:scale-95"
                  >
                    <RefreshCw size={12} className="animate-spin" />
                    重试连接
                  </button>
                </div>
              ) : (
                <p className="text-xs text-neutral-500 tracking-wider">正在初始化监控服务...</p>
              )}
            </div>
          </div>
        ) : (
          /* Actual Dashboard layout grid */
          <div className="w-full grid grid-cols-1 lg:grid-cols-3 gap-8">
        
        {/* Backend Loading Alert */}
        {isBackendLoading && (
          <div className="col-span-full bg-purple-950/20 border border-purple-800 rounded-2xl p-5 flex items-start gap-4 shadow-xl backdrop-blur-md">
            <div className="h-6 w-6 rounded-full border-2 border-purple-500 border-t-transparent animate-spin shrink-0 mt-0.5" />
            <div>
              <h3 className="text-purple-400 font-semibold text-lg">系统服务初始化中</h3>
              <p className="text-purple-300/80 text-sm mt-1">
                正在加载 AI 向量分析模型 (sentence-transformers/all-MiniLM-L6-v2)。这在首次启动或重启时可能需要 10-30 秒，请稍候...
              </p>
            </div>
          </div>
        )}

        {/* Error Alert */}
        {errorMsg && !isBackendLoading && (
          <div className="col-span-full bg-red-950/20 border border-red-800 rounded-2xl p-5 flex items-start gap-4 shadow-xl">
            <AlertTriangle className="text-red-500 shrink-0 mt-0.5 animate-bounce" size={24} />
            <div>
              <h3 className="text-red-400 font-semibold text-lg">系统服务未连接</h3>
              <p className="text-red-300/80 text-sm mt-1">{errorMsg}</p>
              <button 
                onClick={fetchData}
                className="mt-3 flex items-center gap-2 px-4 py-2 bg-red-900/40 hover:bg-red-900/60 border border-red-800 text-red-200 text-xs font-semibold rounded-lg transition-all"
              >
                <RefreshCw size={12} />
                重试连接
              </button>
            </div>
          </div>
        )}

        {/* Live Video Monitor Card (Spans 2 columns) */}
        <div className="lg:col-span-2 bg-neutral-800/60 border border-neutral-800/80 rounded-3xl p-5 shadow-2xl relative overflow-hidden backdrop-blur-sm">
          <div className="flex items-center justify-between mb-4 flex-wrap gap-4">
            <div className="flex items-center gap-3">
              <div className="p-2 rounded-xl bg-purple-500/10 text-purple-400">
                <Video size={22} />
              </div>
              <div>
                <h2 className="font-semibold text-lg text-neutral-100">实时视频监控</h2>
                <p className="text-xs text-neutral-500">
                  {activeCamera ? `${activeCamera.name} (${activeCamera.location})` : '请选择或添加摄像头'}
                </p>
              </div>
            </div>

            {/* Select Camera Dropdown */}
            <div className="flex items-center gap-3">
              <select
                value={selectedCameraId || ''}
                onChange={(e) => setSelectedCameraId(Number(e.target.value))}
                className="bg-neutral-900 border border-neutral-700/80 rounded-xl px-3 py-2 text-sm text-neutral-300 focus:outline-none focus:ring-2 focus:ring-purple-500/80 cursor-pointer hover:border-neutral-600 transition-colors"
              >
                <option value="" disabled>-- 选择摄像头 --</option>
                {cameras.map(c => (
                  <option key={c.id} value={c.id}>{c.name}</option>
                ))}
              </select>

              {activeCamera && (
                <button
                  disabled={cameraActionLoadingId !== null}
                  onClick={() => activeCamera.is_running ? handleStopCamera(activeCamera.id) : handleStartCamera(activeCamera.id)}
                  className={clsx(
                    "flex items-center gap-2 px-4 py-2 rounded-xl text-sm font-semibold transition-all shadow-md",
                    cameraActionLoadingId !== null
                      ? "bg-neutral-800 text-neutral-500 border border-neutral-700 cursor-not-allowed"
                      : activeCamera.is_running
                        ? "bg-red-600/90 hover:bg-red-700/90 text-white shadow-red-500/10 active:scale-95"
                        : "bg-purple-600/90 hover:bg-purple-700/90 text-white shadow-purple-500/10 active:scale-95"
                  )}
                >
                  {cameraActionLoadingId === activeCamera.id ? (
                    <>
                      <RefreshCw size={14} className="animate-spin" />
                      <span>处理中...</span>
                    </>
                  ) : activeCamera.is_running ? (
                    <>
                      <Square size={14} fill="white" />
                      <span>停止检测</span>
                    </>
                  ) : (
                    <>
                      <Play size={14} fill="white" />
                      <span>启动检测</span>
                    </>
                  )}
                </button>
              )}
            </div>
          </div>

          {/* Video Container */}
          <div className="w-full aspect-video bg-neutral-950 rounded-2xl overflow-hidden flex items-center justify-center border border-neutral-800/80 relative shadow-inner">
            {videoFeedUrl && !streamError ? (
              <img 
                src={videoFeedUrl} 
                alt="Live Camera Feed" 
                className="w-full h-full object-contain"
                onError={() => {
                  setStreamError(true);
                  console.error("MJPEG video stream connection lost");
                }}
              />
            ) : videoFeedUrl && streamError ? (
              <div className="text-center p-8 flex flex-col items-center">
                <div className="p-4 rounded-full bg-red-950/20 border border-red-800/40 text-red-500 mb-3 animate-pulse">
                  <AlertTriangle size={36} />
                </div>
                <p className="text-red-400 font-semibold mb-1">视频流连接已断开</p>
                <p className="text-xs text-neutral-500 max-w-sm">
                  无法连接至摄像头视频流，请检查摄像头是否在线，或尝试点击“停止检测”后重新“启动检测”
                </p>
              </div>
            ) : (
              <div className="text-center p-8 flex flex-col items-center">
                <div className="p-4 rounded-full bg-neutral-900 border border-neutral-800 text-neutral-500 mb-3">
                  <Video size={36} />
                </div>
                {activeCamera ? (
                  <>
                    <p className="text-neutral-400 font-semibold mb-1">摄像头未启动</p>
                    <p className="text-xs text-neutral-600 max-w-sm">
                      点击右上方“启动检测”按钮开启 YOLOv8 +人脸+体态识别流
                    </p>
                  </>
                ) : (
                  <p className="text-neutral-500 text-sm">请先添加或选择一个摄像头</p>
                )}
              </div>
            )}

            {/* Status overlay */}
            {activeCamera?.is_running && (
              <div className="absolute top-4 left-4 bg-black/60 px-3 py-1.5 rounded-lg border border-neutral-700 text-xs font-mono text-green-400 flex items-center gap-2 backdrop-blur-md">
                <span className="h-2 w-2 rounded-full bg-green-500 animate-ping"></span>
                <span>LIVE | FPS: {activeCamera.stats?.fps || 15} | 目标数: {activeCamera.stats?.current_persons || 0}</span>
              </div>
            )}
          </div>
        </div>

        {/* Live Alerts Stream Card (Spans 1 column) */}
        <div className="bg-neutral-800/60 border border-neutral-800/80 rounded-3xl p-5 shadow-2xl flex flex-col h-[520px] backdrop-blur-sm">
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center gap-2.5">
              <span className={clsx(
                "h-2 w-2 rounded-full",
                wsConnected ? "bg-green-500 animate-pulse" : "bg-red-500 animate-ping"
              )}></span>
              <h2 className="font-semibold text-lg text-neutral-100">实时监控事件流</h2>
            </div>
            <span className="text-[10px] uppercase font-mono px-2 py-0.5 bg-neutral-950/60 border border-neutral-800 text-neutral-500 rounded-lg">
              {wsConnected ? 'Connected' : 'Offline'}
            </span>
          </div>

          {/* Event Alerts Container */}
          <div className="flex-1 overflow-y-auto space-y-3 pr-1 scrollbar-thin">
            {liveEvents.length === 0 ? (
              <div className="h-full flex flex-col items-center justify-center text-center p-6 text-neutral-500 italic text-xs">
                等待摄像头推送实时告警事件...
              </div>
            ) : (
              liveEvents.map((evt, idx) => {
                const isEnter = evt.event_type === 'enter';
                const isBendingOrSquat = evt.event_type === 'bending' || evt.event_type === 'crouching';
                return (
                  <div 
                    key={idx} 
                    className={clsx(
                      "p-3 rounded-2xl border text-xs flex flex-col gap-2 transition-all hover:scale-[1.01]",
                      isEnter 
                        ? "bg-green-950/15 border-green-800/40 text-green-300"
                        : isBendingOrSquat
                          ? "bg-amber-950/15 border-amber-800/40 text-amber-300"
                          : "bg-neutral-900/50 border-neutral-800 text-neutral-300"
                    )}
                  >
                    <div className="flex justify-between items-center">
                      <span className="font-bold uppercase tracking-wider">{evt.event_type}</span>
                      <span className="font-mono opacity-60 text-[10px]">{formatTime(evt.timestamp)}</span>
                    </div>
                    <div>
                      <span className="font-semibold text-neutral-100">{evt.person_name}</span>: {evt.behavior || '行为状态变化'}
                    </div>
                    <div className="flex justify-between items-center text-[10px] opacity-60">
                      <span>设备: {evt.camera_name || '默认摄像头'}</span>
                      <span>置信度: {Math.round(evt.confidence * 100)}%</span>
                    </div>
                  </div>
                );
              })
            )}
          </div>
        </div>

        {/* ================= HISTORICAL EVENT LOGS (FULL ROW) ================= */}
        <div className="col-span-full bg-neutral-800/40 border border-neutral-800/80 rounded-3xl p-6 shadow-2xl backdrop-blur-sm">
          <div className="flex justify-between items-center mb-6 flex-wrap gap-4">
            <h2 className="font-semibold text-lg text-neutral-100 flex items-center gap-2">
              <Clock size={20} className="text-purple-400" />
              历史行为监测记录
            </h2>
            
            {/* 日历筛选器 */}
            <div className="flex items-center gap-2 select-none">
              {filterDate ? (
                /* 已选择日期：显示完整的日期选择框与清除按钮 */
                <div className="flex items-center gap-2 bg-neutral-900/60 border border-neutral-800 rounded-xl px-3 py-1.5 hover:border-neutral-700 transition-all">
                  <Calendar size={14} className="text-purple-400" />
                  <input
                    type="date"
                    value={filterDate}
                    onChange={(e) => setFilterDate(e.target.value)}
                    className="bg-transparent text-xs text-neutral-200 focus:outline-none cursor-pointer [color-scheme:dark]"
                  />
                  <button
                    type="button"
                    onClick={() => setFilterDate('')}
                    className="text-neutral-500 hover:text-neutral-300 transition-colors text-[10px] pl-1 border-l border-neutral-800 ml-1"
                  >
                    清除
                  </button>
                </div>
              ) : (
                /* 未选择日期：只显示一个日历图标按钮，点击后弹出原生选择器 */
                <div className="relative">
                  <button
                    type="button"
                    onClick={() => {
                      const input = document.getElementById('hidden-date-picker') as HTMLInputElement;
                      if (input) {
                        try {
                          input.showPicker();
                        } catch (e) {
                          input.focus();
                        }
                      }
                    }}
                    className="p-2 bg-neutral-800 hover:bg-neutral-700 text-neutral-400 hover:text-neutral-200 rounded-xl border border-neutral-700/80 transition-all active:scale-95 flex items-center justify-center shadow-lg"
                    title="选择日期过滤记录"
                  >
                    <Calendar size={16} />
                  </button>
                  <input
                    id="hidden-date-picker"
                    type="date"
                    value={filterDate}
                    onChange={(e) => setFilterDate(e.target.value)}
                    className="absolute inset-0 opacity-0 pointer-events-none w-0 h-0"
                  />
                </div>
              )}
            </div>
          </div>

          <div className="overflow-x-auto w-full rounded-2xl border border-neutral-800">
            <table className="w-full text-left border-collapse text-xs font-sans">
              <thead>
                <tr className="bg-neutral-900/80 border-b border-neutral-800 text-neutral-400 font-semibold uppercase tracking-wider">
                  <th className="p-4">时间</th>
                  <th className="p-4">摄像头</th>
                  <th className="p-4">姓名</th>
                  <th className="p-4">事件类型</th>
                  <th className="p-4">行为详情</th>
                  <th className="p-4">置信度</th>
                  <th className="p-4 text-center">现场画面</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-neutral-800/80">
                {events.length === 0 ? (
                  <tr>
                    <td colSpan={7} className="p-8 text-center text-neutral-600 italic">暂无历史行为记录</td>
                  </tr>
                ) : (
                  events.map(evt => (
                    <tr key={evt.id} className="hover:bg-neutral-900/30 transition-colors">
                      <td className="p-4 font-mono text-neutral-400">
                        {evt.timestamp ? parseUTC(evt.timestamp).toLocaleString() : 'N/A'}
                      </td>
                      <td className="p-4 text-neutral-200 font-medium">{evt.camera_name}</td>
                      <td className="p-4 text-neutral-200">{evt.person_name}</td>
                      <td className="p-4">
                        <span className={clsx(
                          "px-2.5 py-0.5 rounded-full text-[10px] font-bold uppercase",
                          evt.event_type === 'enter' ? "bg-green-950/40 text-green-400 border border-green-900/30" :
                          evt.event_type === 'leave' ? "bg-red-950/40 text-red-400 border border-red-900/30" :
                          evt.event_type === 'bending' || evt.event_type === 'crouching' ? "bg-amber-950/40 text-amber-400 border border-amber-900/30" :
                          "bg-neutral-950 text-neutral-400 border border-neutral-800"
                        )}>
                          {evt.event_type}
                        </span>
                      </td>
                      <td className="p-4 text-neutral-300">{evt.behavior}</td>
                      <td className="p-4 font-mono text-neutral-400">{Math.round(evt.confidence * 100)}%</td>
                      <td className="p-4 text-center">
                        {evt.snapshot_path ? (
                          <a 
                            href={getSnapshotUrl(evt.snapshot_path)} 
                            target="_blank" 
                            rel="noopener noreferrer"
                            className="inline-flex items-center gap-1 text-purple-400 hover:text-purple-300 transition-colors font-semibold"
                          >
                            <CameraIcon size={12} />
                            查看截图
                          </a>
                        ) : (
                          <span className="text-neutral-600">-</span>
                        )}
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>

          {/* 分页与数据汇总控制栏 */}
          <div className="flex flex-col sm:flex-row justify-between items-center mt-5 pt-4 border-t border-neutral-800 gap-3 text-xs text-neutral-400 select-none">
            <div>
              共 <span className="text-purple-400 font-semibold">{historyTotal}</span> 条历史监测记录
              {historyTotal > 0 && (
                <span>
                  （显示第 <span className="text-neutral-200 font-semibold">{(historyPage - 1) * historyPageSize + 1}</span> - <span className="text-neutral-200 font-semibold">{Math.min(historyPage * historyPageSize, historyTotal)}</span> 条）
                </span>
              )}
            </div>
            {historyTotal > historyPageSize && (
              <div className="flex items-center gap-2">
                <button
                  type="button"
                  disabled={historyPage === 1}
                  onClick={() => setHistoryPage(prev => Math.max(prev - 1, 1))}
                  className="px-3 py-1.5 bg-neutral-800 border border-neutral-700/80 rounded-xl hover:bg-neutral-700 hover:text-neutral-100 disabled:opacity-30 disabled:hover:bg-neutral-800 disabled:hover:text-neutral-400 transition-all active:scale-95 disabled:scale-100 disabled:cursor-not-allowed font-semibold"
                >
                  上一页
                </button>
                <span className="text-neutral-400 px-1 font-sans">
                  {historyPage} / {Math.ceil(historyTotal / historyPageSize)} 页
                </span>
                <button
                  type="button"
                  disabled={historyPage >= Math.ceil(historyTotal / historyPageSize)}
                  onClick={() => setHistoryPage(prev => Math.min(prev + 1, Math.ceil(historyTotal / historyPageSize)))}
                  className="px-3 py-1.5 bg-neutral-800 border border-neutral-700/80 rounded-xl hover:bg-neutral-700 hover:text-neutral-100 disabled:opacity-30 disabled:hover:bg-neutral-800 disabled:hover:text-neutral-400 transition-all active:scale-95 disabled:scale-100 disabled:cursor-not-allowed font-semibold"
                >
                  下一页
                </button>
              </div>
            )}
          </div>
        </div>

        {/* Camera Management Panel (Spans 2 columns, placed below historical logs) */}
        <div className="lg:col-span-2 bg-neutral-800/60 border border-neutral-800/80 rounded-3xl p-5 shadow-2xl backdrop-blur-sm">
          <div className="flex items-center justify-between mb-4 flex-wrap gap-4">
            <h2 className="font-semibold text-lg text-neutral-100 flex items-center gap-2">
              <Video size={20} className="text-purple-400" />
              摄像头设备管理
            </h2>
            <div className="flex items-center gap-4 flex-wrap">
              {/* 截图存储路径展示 & 唤起点选模态框 */}
              <div className="flex items-center gap-2">
                <span className="text-xs text-neutral-400">存储目录:</span>
                <div 
                  className="bg-neutral-900/80 border border-neutral-800 rounded-xl px-3 py-1.5 text-xs text-neutral-400 font-mono max-w-[200px] truncate select-all cursor-default"
                  title={snapshotPath}
                >
                  {snapshotPath || '正在加载...'}
                </div>
                <button
                  type="button"
                  onClick={() => {
                    setIsFolderPickerOpen(true);
                    loadPickerDirs(snapshotPath);
                  }}
                  className="flex items-center gap-1.5 px-3 py-1.5 bg-neutral-900 border border-neutral-700 hover:border-neutral-600 rounded-xl text-xs font-semibold text-neutral-300 transition-colors"
                  title="通过鼠标点选方式选择服务器上的截图存储目录"
                >
                  <FolderOpen size={12} className="text-purple-400" />
                  <span>选择目录</span>
                </button>
              </div>

              <div className="h-4 w-[1px] bg-neutral-700 hidden md:block"></div>

              <button
                onClick={() => {
                  if (!isAddingCamera) {
                    detectCameras();
                  }
                  setIsAddingCamera(!isAddingCamera);
                }}
                className="flex items-center gap-2 px-3 py-1.5 bg-neutral-900 border border-neutral-700 hover:border-neutral-600 rounded-xl text-xs font-semibold text-neutral-300 transition-colors"
              >
                <Plus size={14} />
                添加摄像头
              </button>
            </div>
          </div>

          {/* Add Camera Form */}
          {isAddingCamera && (
            <form onSubmit={handleCreateCamera} className="bg-neutral-900/60 border border-neutral-800 rounded-2xl p-5 mb-5 space-y-4">
              {/* 设备类型选择 */}
              <div className="flex items-center gap-3">
                <span className="text-xs text-neutral-400 font-semibold uppercase tracking-wider">设备类型:</span>
                <div className="flex bg-neutral-950 p-0.5 rounded-lg border border-neutral-800">
                  <button
                    type="button"
                    onClick={() => {
                      setSourceType('local');
                      setNewCamera(prev => ({ ...prev, source: '0' }));
                    }}
                    className={clsx(
                      "px-3 py-1 text-xs font-semibold rounded-md transition-colors",
                      sourceType === 'local' ? "bg-purple-600 text-white" : "text-neutral-400 hover:text-neutral-200"
                    )}
                  >
                    本机摄像头 (电脑自带/USB)
                  </button>
                  <button
                    type="button"
                    onClick={() => {
                      setSourceType('rtsp');
                      setNewCamera(prev => ({ ...prev, source: '' }));
                    }}
                    className={clsx(
                      "px-3 py-1 text-xs font-semibold rounded-md transition-colors",
                      sourceType === 'rtsp' ? "bg-purple-600 text-white" : "text-neutral-400 hover:text-neutral-200"
                    )}
                  >
                    网络摄像机 (RTSP 视频流)
                  </button>
                </div>
              </div>

              {/* 三个输入框 */}
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4 items-end">
                <div className="flex flex-col gap-1.5">
                  <label className="text-[11px] text-neutral-500 font-semibold uppercase tracking-wider">摄像头名称</label>
                  <input
                    type="text"
                    required
                    placeholder="e.g. 机房主门"
                    value={newCamera.name}
                    onChange={e => setNewCamera(prev => ({ ...prev, name: e.target.value }))}
                    className="bg-neutral-950 border border-neutral-800 hover:border-neutral-700 rounded-xl px-3 py-2.5 text-sm text-neutral-200 focus:outline-none focus:ring-1 focus:ring-purple-500 h-10 w-full"
                  />
                </div>
                <div className="flex flex-col gap-1.5">
                  <label className="text-[11px] text-neutral-500 font-semibold uppercase tracking-wider">
                    {sourceType === 'local' ? '选择设备' : '视频源地址 (RTSP)'}
                  </label>
                  {sourceType === 'local' ? (
                    isDetecting ? (
                      <div className="bg-neutral-950 border border-neutral-800 rounded-xl px-3 py-2.5 text-xs text-neutral-400 h-10 w-full flex items-center justify-center gap-2">
                        <RefreshCw size={14} className="animate-spin text-purple-400" />
                        正在检测系统摄像头...
                      </div>
                    ) : detectedDevices.length > 0 ? (
                      <select
                        value={newCamera.source}
                        onChange={e => setNewCamera(prev => ({ ...prev, source: e.target.value }))}
                        className="bg-neutral-950 border border-neutral-800 hover:border-neutral-700 rounded-xl px-3 py-2 text-sm text-neutral-200 focus:outline-none focus:ring-1 focus:ring-purple-500 h-10 w-full"
                      >
                        {detectedDevices.map(device => (
                          <option key={device.id} value={device.id}>
                            {device.name}
                          </option>
                        ))}
                      </select>
                    ) : (
                      <div className="bg-neutral-950 border border-amber-800/40 rounded-xl px-3 py-2.5 text-xs text-amber-500/80 h-10 w-full flex items-center justify-center font-medium">
                        ⚠️ 未检测到可用的本机摄像头
                      </div>
                    )
                  ) : (
                    <input
                      type="text"
                      required
                      placeholder="rtsp://username:password@ip:port/h264"
                      value={newCamera.source}
                      onChange={e => setNewCamera(prev => ({ ...prev, source: e.target.value }))}
                      className="bg-neutral-950 border border-neutral-800 hover:border-neutral-700 rounded-xl px-3 py-2.5 text-sm text-neutral-200 focus:outline-none focus:ring-1 focus:ring-purple-500 h-10 w-full"
                    />
                  )}
                </div>
                <div className="flex flex-col gap-1.5">
                  <label className="text-[11px] text-neutral-500 font-semibold uppercase tracking-wider">安装位置</label>
                  <input
                    type="text"
                    placeholder="e.g. 柜台、机架区"
                    value={newCamera.location}
                    onChange={e => setNewCamera(prev => ({ ...prev, location: e.target.value }))}
                    className="bg-neutral-950 border border-neutral-800 hover:border-neutral-700 rounded-xl px-3 py-2.5 text-sm text-neutral-200 focus:outline-none focus:ring-1 focus:ring-purple-500 h-10 w-full"
                  />
                </div>
              </div>
              <div className="flex justify-end gap-3 pt-1">
                <button
                  type="button"
                  onClick={() => setIsAddingCamera(false)}
                  className="w-[104px] h-10 flex items-center justify-center bg-neutral-800/80 border border-neutral-700 hover:bg-neutral-700/60 text-neutral-300 text-sm font-semibold rounded-xl transition-colors active:scale-95 whitespace-nowrap"
                >
                  取消
                </button>
                <button
                  type="submit"
                  className="w-24 h-10 flex items-center justify-center bg-purple-600 text-white font-semibold text-sm rounded-xl hover:bg-purple-700 transition-colors shadow-md shadow-purple-500/10 active:scale-95 whitespace-nowrap"
                >
                  提交
                </button>
              </div>
            </form>
          )}

          {/* Cameras Table List */}
          <div className="space-y-3">
            {cameras.length === 0 ? (
              <div className="text-center py-6 text-neutral-600 text-xs italic">无摄像头设备，请添加</div>
            ) : (
              cameras.map(cam => (
                <div key={cam.id} className="flex items-center justify-between p-3 bg-neutral-900/40 border border-neutral-800/80 rounded-2xl hover:border-neutral-700 transition-all flex-wrap gap-4">
                  <div className="flex items-center gap-3">
                    <div className={clsx(
                      "h-3 w-3 rounded-full shrink-0",
                      cam.is_running ? "bg-green-500 animate-pulse" : "bg-neutral-600"
                    )}></div>
                    <div>
                      <div className="font-semibold text-sm text-neutral-200">{cam.name}</div>
                      <div className="text-xs text-neutral-500 font-mono truncate max-w-[200px] md:max-w-xs">{cam.source}</div>
                    </div>
                  </div>
                  <div className="flex items-center gap-4">
                    {cam.location && (
                      <span className="text-xs px-2.5 py-1 rounded-lg bg-neutral-950/60 border border-neutral-800 text-neutral-400">
                        {cam.location}
                      </span>
                    )}
                    <button
                      onClick={() => handleDeleteCamera(cam.id)}
                      className="p-2 rounded-xl text-neutral-500 hover:text-red-400 hover:bg-red-500/10 transition-all"
                      title="删除摄像头"
                    >
                      <Trash2 size={16} />
                    </button>
                  </div>
                </div>
              ))
            )}
          </div>
        </div>

        {/* Registered Personnel List Card (Spans 1 column, placed below historical logs) */}
        <div className="bg-neutral-800/60 border border-neutral-800/80 rounded-3xl p-5 shadow-2xl flex flex-col h-[400px] backdrop-blur-sm">
          <div className="flex items-center justify-between mb-4">
            <h2 className="font-semibold text-lg text-neutral-100 flex items-center gap-2">
              <ShieldCheck size={20} className="text-green-400" />
              注册人员管理
            </h2>
            <div className="flex items-center gap-2">
              <Link
                href="/training"
                className="flex items-center gap-1.5 px-3 py-1.5 bg-purple-950/30 border border-purple-800 hover:bg-purple-900/20 rounded-xl text-xs font-semibold text-purple-300 transition-colors"
              >
                <Brain size={14} />
                体态训练
              </Link>
              <button
                onClick={() => setIsRegisteringPerson(!isRegisteringPerson)}
                className="flex items-center gap-1.5 px-3 py-1.5 bg-neutral-900 border border-neutral-700 hover:border-neutral-600 rounded-xl text-xs font-semibold text-neutral-300 transition-colors"
              >
                <UserPlus size={14} />
                注册
              </button>
            </div>
          </div>

          {/* Register form */}
          {isRegisteringPerson ? (
            <form onSubmit={handleRegisterPerson} className="bg-neutral-900/80 border border-neutral-800 rounded-2xl p-4 space-y-3 mb-3">
              <div className="grid grid-cols-2 gap-3">
                <div className="flex flex-col gap-1">
                  <label className="text-[10px] text-neutral-500 font-semibold">姓名</label>
                  <input
                    type="text"
                    required
                    placeholder="姓名"
                    value={newPerson.name}
                    onChange={e => setNewPerson(prev => ({ ...prev, name: e.target.value }))}
                    className="bg-neutral-950 border border-neutral-800 rounded-xl px-2.5 py-1.5 text-xs text-neutral-200 focus:outline-none"
                  />
                </div>
                <div className="flex flex-col gap-1">
                  <label className="text-[10px] text-neutral-500 font-semibold">部门</label>
                  <input
                    type="text"
                    placeholder="IT运维部"
                    value={newPerson.department}
                    onChange={e => setNewPerson(prev => ({ ...prev, department: e.target.value }))}
                    className="bg-neutral-950 border border-neutral-800 rounded-xl px-2.5 py-1.5 text-xs text-neutral-200 focus:outline-none"
                  />
                </div>
              </div>
              
              <div className="grid grid-cols-2 gap-3">
                <div className="flex flex-col gap-1">
                  <label className="text-[10px] text-neutral-500 font-semibold">角色</label>
                  <select
                    value={newPerson.role}
                    onChange={e => setNewPerson(prev => ({ ...prev, role: e.target.value }))}
                    className="bg-neutral-950 border border-neutral-800 rounded-xl px-2.5 py-1.5 text-xs text-neutral-200 focus:outline-none cursor-pointer"
                  >
                    <option value="管理员">管理员</option>
                    <option value="运维">运维人员</option>
                    <option value="剪辑">剪辑人员</option>
                    <option value="导演">导演</option>
                  </select>
                </div>
                <div className="flex flex-col gap-1">
                  <label className="text-[10px] text-neutral-500 font-semibold">正面人脸照</label>
                  <input
                    type="file"
                    required
                    accept="image/*"
                    onChange={e => setFaceFile(e.target.files?.[0] || null)}
                    className="text-[10px] text-neutral-400 file:mr-2 file:py-1 file:px-2 file:rounded-lg file:border-0 file:text-[10px] file:font-semibold file:bg-purple-900/30 file:text-purple-300 hover:file:bg-purple-950/50 cursor-pointer"
                  />
                </div>
              </div>

              <div className="flex gap-2 pt-1.5">
                <button
                  type="submit"
                  disabled={isRegistering}
                  className="flex-1 py-1.5 bg-purple-600 text-white font-semibold text-xs rounded-xl hover:bg-purple-700 transition-colors flex items-center justify-center gap-1.5 disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  {isRegistering ? (
                    <>
                      <div className="h-3.5 w-3.5 rounded-full border-2 border-white border-t-transparent animate-spin" />
                      <span>注册中...</span>
                    </>
                  ) : (
                    <span>提交注册</span>
                  )}
                </button>
                <button
                  type="button"
                  disabled={isRegistering}
                  onClick={() => setIsRegisteringPerson(false)}
                  className="px-3 py-1.5 bg-neutral-800 border border-neutral-700 rounded-xl text-xs text-neutral-400 hover:text-neutral-200 disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  取消
                </button>
              </div>
            </form>
          ) : (
            <div className="flex-1 overflow-y-auto space-y-3 pr-1 scrollbar-thin">
              {persons.length === 0 ? (
                <div className="text-center py-8 text-neutral-600 text-xs italic">无注册人员信息</div>
              ) : (
                persons.map(p => (
                  <div key={p.id} className="flex items-center justify-between p-3 bg-neutral-900/40 border border-neutral-800/80 rounded-2xl hover:border-neutral-700 transition-all">
                    <div className="flex items-center gap-3">
                      <div className="h-8 w-8 rounded-full bg-gradient-to-tr from-purple-500/20 to-pink-500/20 flex items-center justify-center text-purple-300 border border-purple-500/10 text-xs font-bold font-sans">
                        {p.name.slice(0, 2)}
                      </div>
                      <div>
                        <div className="font-semibold text-xs text-neutral-200">{p.name}</div>
                        <div className="text-[10px] text-neutral-500">{p.department} • {p.role}</div>
                      </div>
                    </div>
                    <button
                      onClick={() => handleUnregisterPerson(p.id)}
                      className="p-1 text-neutral-600 hover:text-red-400 hover:bg-red-500/10 rounded-lg transition-colors"
                      title="注销人员"
                    >
                      <Trash2 size={14} />
                    </button>
                  </div>
                ))
              )}
            </div>
          )}
        </div>
          </div>
        )}

      </main>

      {/* Directory Selector Modal */}
      {isFolderPickerOpen && (
        <div className="fixed inset-0 bg-black/75 backdrop-blur-md flex items-center justify-center z-[100] p-4">
          <div className="bg-neutral-900 border border-neutral-800/80 rounded-3xl w-full max-w-lg overflow-hidden shadow-2xl flex flex-col h-[500px] animate-in fade-in zoom-in-95 duration-200">
            {/* Header */}
            <div className="p-5 border-b border-neutral-800/80 flex items-center justify-between">
              <h3 className="text-neutral-100 font-semibold text-base flex items-center gap-2">
                <FolderOpen className="text-purple-400" size={18} />
                选择截图存储目录
              </h3>
              <button 
                onClick={() => setIsFolderPickerOpen(false)}
                className="text-neutral-500 hover:text-neutral-300 text-xs transition-colors"
              >
                关闭
              </button>
            </div>

            {/* Path indicator */}
            <div className="px-5 py-3 bg-neutral-950/60 border-b border-neutral-800/50 flex items-center justify-between gap-3">
              <span className="text-xs text-neutral-400 font-mono truncate select-all" title="当前路径">
                {pickerCurrentPath}
              </span>
              {pickerCurrentPath !== pickerParentPath && (
                <button
                  onClick={() => loadPickerDirs(pickerParentPath)}
                  className="shrink-0 flex items-center gap-1 text-[11px] px-2 py-1 bg-neutral-800 hover:bg-neutral-700 border border-neutral-700/80 text-neutral-300 rounded-lg transition-colors"
                  title="返回上一级"
                >
                  <ArrowLeft size={10} />
                  返回
                </button>
              )}
            </div>

            {/* Folders List */}
            <div className="flex-1 overflow-y-auto p-4 space-y-1 bg-neutral-950/20">
              {pickerSubdirs.length === 0 ? (
                <div className="text-center py-20 text-neutral-600 text-xs italic">
                  无子文件夹
                </div>
              ) : (
                pickerSubdirs.map(dirName => {
                  const fullSubdirPath = pickerCurrentPath.endsWith('/') || pickerCurrentPath.endsWith('\\')
                    ? `${pickerCurrentPath}${dirName}` 
                    : `${pickerCurrentPath}/${dirName}`;
                  return (
                    <div
                      key={dirName}
                      onDoubleClick={() => loadPickerDirs(fullSubdirPath)}
                      onClick={() => setSelectedPickerPath(fullSubdirPath)}
                      className={clsx(
                        "flex items-center justify-between px-4 py-3 rounded-xl border cursor-pointer transition-all",
                        selectedPickerPath === fullSubdirPath
                          ? "bg-purple-600/10 border-purple-500/50 text-purple-200"
                          : "bg-transparent border-transparent text-neutral-300 hover:bg-neutral-800/40 hover:text-neutral-100"
                      )}
                    >
                      <div className="flex items-center gap-3">
                        <Folder size={16} className={clsx(
                          selectedPickerPath === fullSubdirPath ? "text-purple-400" : "text-neutral-500"
                        )} />
                        <span className="text-xs font-medium font-sans">{dirName}</span>
                      </div>
                      <span className="text-[10px] text-neutral-600 italic">双击打开</span>
                    </div>
                  );
                })
              )}
            </div>

            {/* Actions */}
            <div className="p-4 border-t border-neutral-800/80 bg-neutral-900 flex justify-end gap-3">
              <button
                onClick={() => setIsFolderPickerOpen(false)}
                className="px-4 py-2 bg-neutral-800 hover:bg-neutral-700 text-neutral-300 text-xs font-semibold rounded-xl transition-colors"
              >
                取消
              </button>
              <button
                onClick={async () => {
                  try {
                    const res = await fetch(`${API_BASE}/api/camera-settings/snapshot-path`, {
                      method: 'POST',
                      headers: { 'Content-Type': 'application/json' },
                      body: JSON.stringify({ path: selectedPickerPath }),
                    });
                    if (res.ok) {
                      const data = await res.json();
                      setSnapshotPath(data.path);
                      setNewSnapshotPath(data.path);
                      setIsFolderPickerOpen(false);
                      alert("截图存储目录修改成功！已更新为: " + data.path);
                    } else {
                      const err = await res.json();
                      alert(`修改存储路径失败: ${err.detail || '未知错误'}`);
                    }
                  } catch (e) {
                    console.error(e);
                    alert("保存失败");
                  }
                }}
                className="px-4 py-2 bg-purple-600 hover:bg-purple-700 text-white text-xs font-semibold rounded-xl transition-colors flex items-center gap-1.5 shadow-md shadow-purple-500/10"
              >
                <Check size={12} />
                确认选择
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
