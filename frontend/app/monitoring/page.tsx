"use client";

import React, { useState, useEffect, useRef } from 'react';
import Navbar from '../../components/Navbar';
import { Play, Square, Video, Plus, UserPlus, AlertTriangle, ShieldCheck, Clock, Camera as CameraIcon, Trash2, RefreshCw } from 'lucide-react';
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
  
  // Forms
  const [newCamera, setNewCamera] = useState({ name: '', source: '0', location: '' });
  const [newPerson, setNewPerson] = useState({ name: '', department: '', role: '运维' });
  const [faceFile, setFaceFile] = useState<File | null>(null);
  
  // Real-time Event Feed
  const [wsConnected, setWsConnected] = useState(false);
  const [liveEvents, setLiveEvents] = useState<any[]>([]);
  
  const [isLoading, setIsLoading] = useState({ cameras: true, events: true, persons: true });
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimeoutRef = useRef<any>(null);
  
  const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://127.0.0.1:8000';
  const WS_BASE = API_BASE.replace(/^http/, 'ws');

  // Fetch initial data
  const fetchData = async () => {
    try {
      // 1. Fetch Cameras
      const camRes = await fetch(`${API_BASE}/api/cameras`);
      if (camRes.ok) {
        const camData = await camRes.json();
        setCameras(camData.items || []);
        if (camData.items && camData.items.length > 0 && selectedCameraId === null) {
          setSelectedCameraId(camData.items[0].id);
        }
      }

      // 2. Fetch Historical Events
      const eventRes = await fetch(`${API_BASE}/api/events?limit=20`);
      if (eventRes.ok) {
        const eventData = await eventRes.json();
        setEvents(eventData.items || []);
      }

      // 3. Fetch Registered Persons
      const personRes = await fetch(`${API_BASE}/api/persons`);
      if (personRes.ok) {
        const personData = await personRes.json();
        setPersons(personData.items || []);
      }

      setIsLoading({ cameras: false, events: false, persons: false });
    } catch (error) {
      console.error("Failed to fetch camera monitoring data:", error);
      setErrorMsg("连接后端API服务失败，请确认后端运行在端口 8000");
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
        if (socket !== wsRef.current) return;
        try {
          const eventData = JSON.parse(event.data);
          // Add to live alerts list (keep recent 15 events)
          setLiveEvents(prev => [eventData, ...prev].slice(0, 15));
          
          // Re-fetch historical events to stay up to date
          fetch(`${API_BASE}/api/events?limit=20`)
            .then(res => res.json())
            .then(data => setEvents(data.items || []))
            .catch(err => console.error(err));
        } catch (e) {
          console.error("Failed to parse WS event data:", e);
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
        console.error("WebSocket error:", e);
        socket.close();
      };
    } catch (e) {
      console.error("WebSocket connection failure:", e);
    }
  };

  // Camera Management Handlers
  const handleStartCamera = async (id: number) => {
    try {
      const res = await fetch(`${API_BASE}/api/cameras/${id}/start`, { method: 'POST' });
      if (res.ok) {
        fetchData();
      }
    } catch (e) {
      console.error(e);
    }
  };

  const handleStopCamera = async (id: number) => {
    try {
      const res = await fetch(`${API_BASE}/api/cameras/${id}/stop`, { method: 'POST' });
      if (res.ok) {
        fetchData();
      }
    } catch (e) {
      console.error(e);
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

  // Person Registration Handlers
  const handleRegisterPerson = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newPerson.name || !faceFile) {
      alert("请填写姓名并上传人脸照片");
      return;
    }

    try {
      const formData = new FormData();
      formData.append("name", newPerson.name);
      formData.append("department", newPerson.department);
      formData.append("role", newPerson.role);
      formData.append("file", faceFile);

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

  // Render variables
  const activeCamera = cameras.find(c => c.id === selectedCameraId);
  const videoFeedUrl = activeCamera?.is_running 
    ? `${API_BASE}/api/stream/${activeCamera.id}/video`
    : null;

  // Format Helper
  const formatTime = (isoString: string) => {
    try {
      const date = new Date(isoString);
      return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
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

      <main className="flex-1 p-6 md:p-8 max-w-7xl mx-auto w-full grid grid-cols-1 lg:grid-cols-3 gap-8">
        
        {/* Error Alert */}
        {errorMsg && (
          <div className="col-span-full bg-red-950/20 border border-red-800 rounded-2xl p-5 flex items-start gap-4 shadow-xl">
            <AlertTriangle className="text-red-500 shrink-0 mt-0.5 animate-bounce" size={24} />
            <div>
              <h3 className="text-red-400 font-semibold text-lg">系统服务未运行</h3>
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

        {/* ================= COLUMN 1 & 2: MONITOR & LIVE ALERTS ================= */}
        <div className="lg:col-span-2 flex flex-col gap-8">
          
          {/* Live Video Monitor Card */}
          <div className="bg-neutral-800/60 border border-neutral-800/80 rounded-3xl p-5 shadow-2xl relative overflow-hidden backdrop-blur-sm">
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
                    onClick={() => activeCamera.is_running ? handleStopCamera(activeCamera.id) : handleStartCamera(activeCamera.id)}
                    className={clsx(
                      "flex items-center gap-2 px-4 py-2 rounded-xl text-sm font-semibold transition-all active:scale-95 shadow-md",
                      activeCamera.is_running
                        ? "bg-red-600/90 hover:bg-red-700/90 text-white shadow-red-500/10"
                        : "bg-purple-600/90 hover:bg-purple-700/90 text-white shadow-purple-500/10"
                    )}
                  >
                    {activeCamera.is_running ? (
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
              {videoFeedUrl ? (
                <img 
                  src={videoFeedUrl} 
                  alt="Live Camera Feed" 
                  className="w-full h-full object-contain"
                  onError={() => {
                    console.error("MJPEG video stream connection lost");
                  }}
                />
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

          {/* Camera Management Panel */}
          <div className="bg-neutral-800/60 border border-neutral-800/80 rounded-3xl p-5 shadow-2xl backdrop-blur-sm">
            <div className="flex items-center justify-between mb-4 flex-wrap gap-4">
              <h2 className="font-semibold text-lg text-neutral-100 flex items-center gap-2">
                <Video size={20} className="text-purple-400" />
                摄像头设备管理
              </h2>
              <button
                onClick={() => setIsAddingCamera(!isAddingCamera)}
                className="flex items-center gap-2 px-3 py-1.5 bg-neutral-900 border border-neutral-700 hover:border-neutral-600 rounded-xl text-xs font-semibold text-neutral-300 transition-colors"
              >
                <Plus size={14} />
                添加摄像头
              </button>
            </div>

            {/* Add Camera Form */}
            {isAddingCamera && (
              <form onSubmit={handleCreateCamera} className="bg-neutral-900/60 border border-neutral-800 rounded-2xl p-5 mb-5 space-y-4">
                <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
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
                    <label className="text-[11px] text-neutral-500 font-semibold uppercase tracking-wider">视频源 (0 或 RTSP地址)</label>
                    <input
                      type="text"
                      required
                      placeholder="0 或 rtsp://..."
                      value={newCamera.source}
                      onChange={e => setNewCamera(prev => ({ ...prev, source: e.target.value }))}
                      className="bg-neutral-950 border border-neutral-800 hover:border-neutral-700 rounded-xl px-3 py-2.5 text-sm text-neutral-200 focus:outline-none focus:ring-1 focus:ring-purple-500 h-10 w-full"
                    />
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

        </div>

        {/* ================= COLUMN 3: REAL-TIME EVENT STREAM ================= */}
        <div className="flex flex-col gap-8">
          
          {/* Live Alerts Stream Card */}
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
                  <div className="animate-spin rounded-full h-5 w-5 border-b-2 border-purple-500 mb-3"></div>
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

          {/* Registered Personnel List Card */}
          <div className="bg-neutral-800/60 border border-neutral-800/80 rounded-3xl p-5 shadow-2xl flex flex-col h-[400px] backdrop-blur-sm">
            <div className="flex items-center justify-between mb-4">
              <h2 className="font-semibold text-lg text-neutral-100 flex items-center gap-2">
                <ShieldCheck size={20} className="text-green-400" />
                注册人员管理
              </h2>
              <button
                onClick={() => setIsRegisteringPerson(!isRegisteringPerson)}
                className="flex items-center gap-1.5 px-3 py-1.5 bg-neutral-900 border border-neutral-700 hover:border-neutral-600 rounded-xl text-xs font-semibold text-neutral-300 transition-colors"
              >
                <UserPlus size={14} />
                注册
              </button>
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
                      <option value="访客">访客</option>
                    </select>
                  </div>
                  <div className="flex flex-col gap-1">
                    <label className="text-[10px] text-neutral-500 font-semibold">正面人脸照</label>
                    <input
                      type="file"
                      required
                      accept="image/*"
                      onChange={e => setFaceFile(e.target.files?.[0] || null)}
                      className="text-[10px] text-neutral-400 file:mr-2 file:py-1 file:px-2 file:rounded-lg file:border-0 file:text-[10px] file:font-semibold file:bg-purple-900/30 file:text-purple-300 hover:file:bg-purple-900/50 cursor-pointer"
                    />
                  </div>
                </div>

                <div className="flex gap-2 pt-1.5">
                  <button
                    type="submit"
                    className="flex-1 py-1.5 bg-purple-600 text-white font-semibold text-xs rounded-xl hover:bg-purple-700 transition-colors"
                  >
                    提交注册
                  </button>
                  <button
                    type="button"
                    onClick={() => setIsRegisteringPerson(false)}
                    className="px-3 py-1.5 bg-neutral-800 border border-neutral-700 rounded-xl text-xs text-neutral-400 hover:text-neutral-200"
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

        {/* ================= HISTORICAL EVENT LOGS (FULL ROW) ================= */}
        <div className="col-span-full bg-neutral-800/40 border border-neutral-800/80 rounded-3xl p-6 shadow-2xl backdrop-blur-sm">
          <h2 className="font-semibold text-lg text-neutral-100 mb-6 flex items-center gap-2">
            <Clock size={20} className="text-purple-400" />
            历史行为监测记录
          </h2>

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
                        {evt.timestamp ? new Date(evt.timestamp).toLocaleString() : 'N/A'}
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
        </div>

      </main>
    </div>
  );
}
