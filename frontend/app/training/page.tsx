"use client";

import React, { useState, useEffect, useRef } from 'react';
import Navbar from '../../components/Navbar';
import { ArrowLeft, Play, RefreshCw, Tag, Plus, Info, Terminal, Image, Check } from 'lucide-react';
import Link from 'next/link';

export default function TrainingPage() {
  const API_BASE = (process.env.NEXT_PUBLIC_API_URL || 'http://127.0.0.1:8000').replace(/\/$/, '');

  // State Management
  const [unlabeledCrops, setUnlabeledCrops] = useState<string[]>([]);
  const [labels, setLabels] = useState<string[]>([]);
  const [selectedLabel, setSelectedLabel] = useState<string>('');
  const [newLabelInput, setNewLabelInput] = useState<string>('');
  const [isTraining, setIsTraining] = useState<boolean>(false);
  const [trainingLogs, setTrainingLogs] = useState<string>('');
  const [loadingCrops, setLoadingCrops] = useState<boolean>(true);
  const [fadeImages, setFadeImages] = useState<Record<string, boolean>>({});

  // Console log scrolling ref
  const terminalRef = useRef<HTMLDivElement>(null);
  const logIntervalRef = useRef<NodeJS.Timeout | null>(null);

  // Fetch unlabeled crops
  const fetchCrops = async () => {
    try {
      setLoadingCrops(true);
      const res = await fetch(`${API_BASE}/api/training/unlabeled`);
      if (res.ok) {
        const data = await res.json();
        setUnlabeledCrops(data.items || []);
      }
    } catch (e) {
      console.error("Failed to load crops:", e);
    } finally {
      setLoadingCrops(false);
    }
  };

  // Fetch labels
  const fetchLabels = async () => {
    try {
      const res = await fetch(`${API_BASE}/api/training/labels`);
      if (res.ok) {
        const data = await res.json();
        setLabels(data.labels || []);
        // Set default selected label if none is active
        if (data.labels && data.labels.length > 0 && !selectedLabel) {
          setSelectedLabel(data.labels[0]);
        }
      }
    } catch (e) {
      console.error("Failed to load labels:", e);
    }
  };

  // Load initial data
  useEffect(() => {
    fetchCrops();
    fetchLabels();
    checkTrainingStatus();

    return () => {
      if (logIntervalRef.current) {
        clearInterval(logIntervalRef.current);
      }
    };
  }, []);

  // Auto-scroll terminal logs to bottom
  useEffect(() => {
    if (terminalRef.current) {
      terminalRef.current.scrollTop = terminalRef.current.scrollHeight;
    }
  }, [trainingLogs]);

  // Check backend training status & logs
  const checkTrainingStatus = async () => {
    try {
      const res = await fetch(`${API_BASE}/api/training/status`);
      if (res.ok) {
        const data = await res.json();
        setIsTraining(data.is_training);
        setTrainingLogs(data.logs || '等待开始训练...\n');

        // If training is active, start polling if not already doing so
        if (data.is_training && !logIntervalRef.current) {
          startPollingLogs();
        } else if (!data.is_training && logIntervalRef.current) {
          stopPollingLogs();
        }
      }
    } catch (e) {
      console.error("Failed to query training status:", e);
    }
  };

  const startPollingLogs = () => {
    if (logIntervalRef.current) return;
    logIntervalRef.current = setInterval(checkTrainingStatus, 1500);
  };

  const stopPollingLogs = () => {
    if (logIntervalRef.current) {
      clearInterval(logIntervalRef.current);
      logIntervalRef.current = null;
    }
  };

  // Create new label folder
  const handleCreateLabel = (e: React.FormEvent) => {
    e.preventDefault();
    const cleanLabel = newLabelInput.trim();
    if (!cleanLabel) return;
    
    // Check if label already exists
    if (labels.includes(cleanLabel)) {
      setSelectedLabel(cleanLabel);
      setNewLabelInput('');
      return;
    }

    setLabels(prev => {
      const updated = [...prev, cleanLabel].sort();
      return updated;
    });
    setSelectedLabel(cleanLabel);
    setNewLabelInput('');
  };

  // Label an image (Move crop file)
  const handleLabelCrop = async (filename: string) => {
    if (!selectedLabel) {
      alert("请先选择或新建一个标注标签！");
      return;
    }

    // Set fade-out class instantly for smooth UI transition
    setFadeImages(prev => ({ ...prev, [filename]: true }));

    // Wait briefly for the fade-out animation to finish, then delete from state
    setTimeout(() => {
      setUnlabeledCrops(prev => prev.filter(f => f !== filename));
    }, 200);

    try {
      const res = await fetch(`${API_BASE}/api/training/label`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ filename, label: selectedLabel }),
      });
      if (!res.ok) {
        const data = await res.json();
        // Rollback state if server-side move failed
        setFadeImages(prev => ({ ...prev, [filename]: false }));
        fetchCrops();
        alert(`标注失败: ${data.detail || '移动文件失败'}`);
      } else {
        // Refresh label list to include newly created label folders if they were empty
        fetchLabels();
      }
    } catch (e) {
      console.error("Failed to label crop:", e);
      setFadeImages(prev => ({ ...prev, [filename]: false }));
      fetchCrops();
    }
  };

  // Start training
  const handleStartTraining = async () => {
    if (isTraining) return;
    
    try {
      const res = await fetch(`${API_BASE}/api/training/train`, { method: 'POST' });
      const data = await res.json();
      if (res.ok && data.status !== 'error') {
        setIsTraining(true);
        setTrainingLogs("=== 启动训练后台进程 ===\n初始化算法配置中...\n");
        startPollingLogs();
      } else {
        alert(data.detail || data.message || "无法启动训练，请确保 labeled 文件夹中已有已标注的数据！");
      }
    } catch (e) {
      console.error("Failed to start training:", e);
      alert("启动训练失败");
    }
  };

  return (
    <div className="min-h-screen bg-neutral-900 text-neutral-100 flex flex-col overflow-x-hidden">
      <Navbar />

      <main className="flex-1 p-6 md:p-8 max-w-7xl mx-auto w-full grid grid-cols-1 lg:grid-cols-4 gap-8">
        
        {/* Left Column: Tools, Labels & Controls */}
        <div className="lg:col-span-1 space-y-6 flex flex-col h-full">
          
          {/* Back link */}
          <Link 
            href="/monitoring" 
            className="inline-flex items-center gap-2 text-xs text-neutral-400 hover:text-neutral-200 transition-colors bg-neutral-800/40 border border-neutral-800 rounded-xl px-3.5 py-2 w-fit"
          >
            <ArrowLeft size={12} />
            返回行为监测
          </Link>

          {/* Active Label Panel */}
          <div className="bg-neutral-800/40 border border-neutral-800 rounded-3xl p-5 shadow-xl backdrop-blur-sm space-y-4">
            <div>
              <h3 className="font-bold text-sm text-neutral-200">1. 选择标注类别</h3>
              <p className="text-[10px] text-neutral-500 mt-0.5">点击照片时，照片会被归类至当前选择的标签下</p>
            </div>

            {/* List labels */}
            <div className="space-y-1.5 max-h-48 overflow-y-auto pr-1 scrollbar-thin">
              {labels.length === 0 ? (
                <div className="text-xs text-neutral-600 italic py-2">暂无可用类别，请在下方新建。</div>
              ) : (
                labels.map(lbl => (
                  <button
                    key={lbl}
                    type="button"
                    onClick={() => setSelectedLabel(lbl)}
                    className={`w-full flex items-center justify-between px-3 py-2 rounded-xl text-xs font-semibold transition-all border ${
                      selectedLabel === lbl
                        ? "bg-purple-600 border-purple-500 text-white shadow-lg shadow-purple-600/10"
                        : "bg-neutral-900/60 border-neutral-800 text-neutral-400 hover:text-neutral-200 hover:border-neutral-700"
                    }`}
                  >
                    <div className="flex items-center gap-2">
                      <Tag size={12} />
                      <span>{lbl}</span>
                    </div>
                    {selectedLabel === lbl && <Check size={12} />}
                  </button>
                ))
              )}
            </div>

            {/* Create new label */}
            <form onSubmit={handleCreateLabel} className="pt-2 border-t border-neutral-800/80 flex gap-2">
              <input
                type="text"
                required
                placeholder="新类别 (例: wudi)"
                value={newLabelInput}
                onChange={e => setNewLabelInput(e.target.value.replace(/[^a-zA-Z0-9_\u4e00-\u9fa5]/g, ''))}
                className="flex-1 bg-neutral-950 border border-neutral-800 rounded-xl px-2.5 py-1.5 text-xs text-neutral-200 focus:outline-none focus:border-neutral-700 placeholder:text-neutral-600"
              />
              <button
                type="submit"
                className="p-1.5 bg-neutral-800 hover:bg-neutral-700 border border-neutral-700 rounded-xl text-neutral-300 transition-colors"
                title="新建类别"
              >
                <Plus size={16} />
              </button>
            </form>
          </div>

          {/* Action / Training Card */}
          <div className="bg-neutral-800/40 border border-neutral-800 rounded-3xl p-5 shadow-xl backdrop-blur-sm space-y-4 flex-1 flex flex-col justify-between">
            <div className="space-y-4">
              <div>
                <h3 className="font-bold text-sm text-neutral-200">2. 训练分类模型</h3>
                <p className="text-[10px] text-neutral-500 mt-0.5">将已标定的人像进行深度微调学习</p>
              </div>

              {/* Tips */}
              <div className="bg-neutral-950/40 border border-neutral-800/80 rounded-xl p-3 flex gap-2">
                <Info size={14} className="text-purple-400 shrink-0 mt-0.5" />
                <p className="text-[10px] text-neutral-400 leading-relaxed">
                  提示：为了训练稳定性，请确保您在每个类别目录下归纳了至少 <span className="text-purple-400 font-semibold">15 张</span> 照片，然后再启动训练。
                </p>
              </div>
            </div>

            {/* Train button */}
            <button
              type="button"
              disabled={isTraining || labels.length === 0}
              onClick={handleStartTraining}
              className="w-full mt-4 py-2.5 bg-gradient-to-r from-purple-600 to-indigo-600 hover:from-purple-700 hover:to-indigo-700 text-white font-bold text-xs rounded-xl shadow-lg shadow-purple-500/10 transition-all flex items-center justify-center gap-1.5 disabled:opacity-50 disabled:cursor-not-allowed disabled:from-neutral-800 disabled:to-neutral-800 disabled:text-neutral-500 disabled:border disabled:border-neutral-800"
            >
              {isTraining ? (
                <>
                  <RefreshCw size={12} className="animate-spin" />
                  <span>正在训练中...</span>
                </>
              ) : (
                <>
                  <Play size={12} />
                  <span>启动模型训练</span>
                </>
              )}
            </button>
          </div>

        </div>

        {/* Right Column: Grid and Console Logger */}
        <div className="lg:col-span-3 space-y-6 flex flex-col h-[calc(100vh-140px)]">
          
          {/* Main workspace */}
          <div className="bg-neutral-800/40 border border-neutral-800 rounded-3xl p-6 shadow-xl backdrop-blur-sm flex-1 flex flex-col min-h-0">
            <div className="flex justify-between items-center mb-6">
              <div className="flex items-center gap-2">
                <Image size={18} className="text-purple-400" />
                <h2 className="font-semibold text-base text-neutral-100">待标注体态库</h2>
              </div>
              <span className="text-[10px] uppercase font-mono px-2 py-0.5 bg-neutral-950/60 border border-neutral-800 text-neutral-400 rounded-lg">
                待标注样本: {unlabeledCrops.length}
              </span>
            </div>

            {/* Photo Grid */}
            <div className="flex-1 overflow-y-auto min-h-0 pr-1 scrollbar-thin">
              {loadingCrops ? (
                <div className="h-full flex items-center justify-center">
                  <div className="h-6 w-6 rounded-full border-2 border-purple-500 border-t-transparent animate-spin" />
                </div>
              ) : unlabeledCrops.length === 0 ? (
                <div className="h-full flex flex-col items-center justify-center text-center p-6 text-neutral-500 italic text-xs space-y-2">
                  <p>🎉 暂无待标注的图片。</p>
                  <p className="text-[10px] text-neutral-600">摄像头在监测到人员时，会自动裁剪并收集人像样本至此处。</p>
                </div>
              ) : (
                <div className="grid grid-cols-3 sm:grid-cols-4 md:grid-cols-6 lg:grid-cols-8 gap-3">
                  {unlabeledCrops.map(filename => (
                    <button
                      key={filename}
                      type="button"
                      disabled={!selectedLabel}
                      onClick={() => handleLabelCrop(filename)}
                      className={`relative aspect-[3/4] bg-neutral-950 border border-neutral-800/80 rounded-xl overflow-hidden group hover:border-purple-500/50 transition-all select-none duration-200 active:scale-95 cursor-pointer disabled:cursor-not-allowed ${
                        fadeImages[filename] ? "scale-0 opacity-0" : "scale-100 opacity-100"
                      }`}
                    >
                      {/* Crop Image */}
                      <img
                        src={`${API_BASE}/body-crops/${filename}`}
                        alt="Crop"
                        className="w-full h-full object-cover group-hover:scale-105 transition-transform"
                        loading="lazy"
                      />

                      {/* Click overlay tooltips */}
                      {selectedLabel ? (
                        <div className="absolute inset-0 bg-purple-950/80 opacity-0 group-hover:opacity-100 flex flex-col items-center justify-center text-center p-1.5 transition-all">
                          <Tag size={10} className="text-purple-300 animate-bounce" />
                          <span className="text-[9px] text-purple-200 font-bold mt-1 line-clamp-2">分类至</span>
                          <span className="text-[10px] text-white font-black truncate max-w-full">{selectedLabel}</span>
                        </div>
                      ) : (
                        <div className="absolute inset-0 bg-black/60 opacity-0 group-hover:opacity-100 flex items-center justify-center p-2 text-center transition-all">
                          <span className="text-[8px] text-neutral-400">请选择标签</span>
                        </div>
                      )}
                    </button>
                  ))}
                </div>
              )}
            </div>
          </div>

          {/* Training Terminal Output Console */}
          <div className="bg-neutral-950/80 border border-neutral-800 rounded-3xl p-5 shadow-xl flex flex-col h-48">
            <div className="flex items-center gap-2 mb-3 shrink-0">
              <Terminal size={14} className="text-purple-400" />
              <h3 className="font-semibold text-xs text-neutral-300">后台模型训练终端输出</h3>
            </div>

            {/* Scrollable logger terminal */}
            <div 
              ref={terminalRef}
              className="flex-1 overflow-y-auto font-mono text-[10px] text-green-400 leading-relaxed bg-black/60 border border-neutral-900 rounded-xl p-3 scrollbar-thin scrollbar-track-transparent scrollbar-thumb-neutral-800 whitespace-pre-wrap select-text"
            >
              {trainingLogs}
            </div>
          </div>

        </div>

      </main>
    </div>
  );
}
