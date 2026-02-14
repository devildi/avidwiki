"use client";

import React, { useState } from 'react';
import { ArrowLeft, RefreshCw, Terminal, XCircle, ChevronDown, ChevronUp, Database, Cloud, HardDrive } from 'lucide-react';
import Link from 'next/link';
import clsx from 'clsx';
import PDFManager from '../../components/PDFManager';

type LLMProvider = 'local' | 'cloud' | 'deepseek' | null;

interface Source {
    id: number;
    url: string;
    display_name: string;
    last_updated: string;
}

interface Progress {
    current: number;
    total: number;
}

export default function SettingsPage() {
    const [sources, setSources] = React.useState<Source[]>([]);
    const [activeTasks, setActiveTasks] = React.useState<Record<number, boolean>>({});
    const [taskLogs, setTaskLogs] = React.useState<Record<number, string[]>>({});
    const [taskProgress, setTaskProgress] = React.useState<Record<number, Progress>>({});
    const [expandedConsoles, setExpandedConsoles] = React.useState<Record<number, boolean>>({});
    const [error, setError] = React.useState<string | null>(null);
    const [loading, setLoading] = React.useState(true);
    const [llmProvider, setLlmProvider] = React.useState<LLMProvider>(null);

    // Fetch sources on load
    const fetchSources = React.useCallback(() => {
        const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
        setLoading(true);
        setError(null);

        fetch(`${API_BASE}/sources`)
            .then(res => {
                if (!res.ok) {
                    throw new Error(`HTTP ${res.status}: ${res.statusText}`);
                }
                return res.json();
            })
            .then(data => {
                setSources(data);
                setLoading(false);
            })
            .catch(err => {
                console.error("Failed to fetch sources:", err);
                setError("无法连接到后端服务。请确认后端正在运行 (http://localhost:8000)");
                setLoading(false);
            });
    }, []);

    React.useEffect(() => {
        fetchSources();
    }, [fetchSources]);

    // Load LLM provider preference from localStorage on mount
    React.useEffect(() => {
        const saved = localStorage.getItem('llm_provider');
        if (saved === 'local' || saved === 'deepseek') {
            setLlmProvider(saved);
        } else if (saved === 'cloud' || saved === 'null' || saved === null) {
            // If saved provider is cloud (OpenAI/disabled) or explicitly none, set to null
            setLlmProvider(null);
            localStorage.setItem('llm_provider', 'null');
        }
    }, []);

    // Save LLM provider preference to localStorage when changed
    const handleProviderChange = (provider: LLMProvider) => {
        // If clicking the same provider, toggle it off (set to null)
        if (llmProvider === provider) {
            setLlmProvider(null);
            localStorage.setItem('llm_provider', 'null');
        } else {
            setLlmProvider(provider);
            localStorage.setItem('llm_provider', provider || 'null');
        }
    };

    const handleUpdateNow = async (id: number) => {
        if (activeTasks[id]) return;

        // Reset logs and progress for this ID
        setTaskLogs(prev => ({ ...prev, [id]: ["🚀 Initializing SSE connection..."] }));
        setTaskProgress(prev => ({ ...prev, [id]: { current: 0, total: 0 } }));
        setActiveTasks(prev => ({ ...prev, [id]: true }));
        setExpandedConsoles(prev => ({ ...prev, [id]: true }));

        try {
            const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
            await fetch(`${API_BASE}/crawler/run?source_id=${id}`, { method: 'POST' });

            // Start SSE subscription
            const es = new EventSource(`${API_BASE}/crawler/logs/${id}`);

            es.onmessage = (event) => {
                const data = JSON.parse(event.data);
                if (data.type === 'log') {
                    setTaskLogs(prev => ({
                        ...prev,
                        [id]: [...(prev[id] || []), data.message]
                    }));
                } else if (data.type === 'progress') {
                    setTaskProgress(prev => ({
                        ...prev,
                        [id]: { current: data.current, total: data.total }
                    }));
                } else if (data.type === 'status') {
                    if (data.message === 'finished' || data.message === 'error') {
                        es.close();
                        setActiveTasks(prev => ({ ...prev, [id]: false }));
                        fetchSources(); // Refresh timestamps
                    }
                }
            };

            es.onerror = () => {
                setTaskLogs(prev => ({ ...prev, [id]: [...(prev[id] || []), "❌ SSE connection lost."] }));
                es.close();
                setActiveTasks(prev => ({ ...prev, [id]: false }));
            };

        } catch (err) {
            console.error("Failed to start crawler:", err);
            setTaskLogs(prev => ({ ...prev, [id]: ["❌ Failed to start crawler API call."] }));
            setActiveTasks(prev => ({ ...prev, [id]: false }));
        }
    };

    const handleCancel = async (id: number) => {
        try {
            const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
            await fetch(`${API_BASE}/crawler/stop/${id}`, { method: 'POST' });
        } catch (err) {
            console.error("Failed to stop crawler:", err);
        }
    };

    const toggleConsole = (id: number) => {
        setExpandedConsoles(prev => ({ ...prev, [id]: !prev[id] }));
    };

    const [activeTab, setActiveTab] = useState<'sources' | 'documents'>('sources');

    return (
        <div className="min-h-screen bg-neutral-900 text-neutral-100 p-8 flex flex-col items-center overflow-x-hidden">
            <div className="w-full max-w-3xl">
                {/* Header */}
                <div className="flex items-center gap-4 mb-8">
                    <Link href="/" className="p-2 rounded-full hover:bg-neutral-800 transition-colors">
                        <ArrowLeft size={24} className="text-neutral-400" />
                    </Link>
                    <h1 className="text-2xl font-bold">Settings</h1>
                </div>

                {/* Error Message */}
                {error && (
                    <div className="bg-red-900/20 border border-red-800 rounded-xl p-4 mb-6 break-words">
                        <div className="flex items-start gap-3">
                            <div className="text-red-400 text-xl">⚠️</div>
                            <div className="flex-1 min-w-0">
                                <h3 className="text-red-400 font-semibold mb-1">连接错误</h3>
                                <p className="text-red-300 text-sm break-words">{error}</p>
                                <p className="text-red-400/70 text-xs mt-2">
                                    请运行: <code className="bg-red-900/50 px-2 py-1 rounded text-xs break-all">cd backend/api && python main.py</code>
                                </p>
                            </div>
                        </div>
                    </div>
                )}

                {/* Tabs */}
                <div className="flex gap-2 mb-6">
                    <button
                        onClick={() => setActiveTab('sources')}
                        className={`flex items-center gap-2 px-4 py-2 rounded-lg transition-colors ${activeTab === 'sources'
                                ? 'bg-purple-600 text-white'
                                : 'bg-neutral-800 text-neutral-400 hover:bg-neutral-700'
                            }`}
                    >
                        <Database size={18} />
                        Forum Sources
                    </button>
                    <button
                        onClick={() => setActiveTab('documents')}
                        className={`flex items-center gap-2 px-4 py-2 rounded-lg transition-colors ${activeTab === 'documents'
                                ? 'bg-purple-600 text-white'
                                : 'bg-neutral-800 text-neutral-400 hover:bg-neutral-700'
                            }`}
                    >
                        <Terminal size={18} />
                        PDF Documents
                    </button>
                </div>

                {/* Tab Content */}
                {activeTab === 'sources' ? (
                    <>
                        {/* Data Management Section */}
                        <div className="bg-neutral-800 border border-neutral-700 rounded-xl p-6 shadow-lg mb-8 overflow-x-hidden">
                            <div className="flex items-center justify-between mb-6">
                                <div className="flex items-center gap-2">
                                    <h2 className="text-lg font-semibold text-purple-400">Data Source Management</h2>
                                    {Object.values(activeTasks).some(v => v) && (
                                        <span className="flex h-2 w-2 rounded-full bg-green-500 animate-pulse"></span>
                                    )}
                                </div>
                                <span className="text-xs bg-neutral-700 text-neutral-400 px-2 py-1 rounded whitespace-nowrap">
                                    {sources.length} total topics
                                </span>
                            </div>

                            <div className="space-y-4">
                                {loading ? (
                                    <div className="text-center py-12 text-neutral-500">
                                        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-purple-500 mx-auto mb-4"></div>
                                        <p>加载数据源...</p>
                                    </div>
                                ) : sources.length === 0 ? (
                                    <div className="text-center py-8 text-neutral-500 border border-dashed border-neutral-800 rounded-lg">
                                        No data sources configured.
                                    </div>
                                ) : (
                                    sources.map(source => {
                                        const isActive = activeTasks[source.id];
                                        const progress = taskProgress[source.id];
                                        const logs = taskLogs[source.id] || [];
                                        const isExpanded = expandedConsoles[source.id];

                                        return (
                                            <div key={source.id} className="flex flex-col bg-neutral-900/50 rounded-lg border border-neutral-800 hover:border-neutral-700 transition-all overflow-hidden w-full">
                                                <div className="flex items-center justify-between p-4 flex-wrap gap-4 min-w-0">
                                                    {/* 1. Topic & URL */}
                                                    <div className="flex flex-col flex-1 min-w-[200px] overflow-hidden">
                                                        <div className="flex items-center gap-2 mb-1">
                                                            <span className="text-xs text-neutral-500 font-medium uppercase tracking-wider shrink-0">Topic</span>
                                                            <span className="text-xs text-purple-400 font-mono opacity-50">#{source.id}</span>
                                                        </div>
                                                        <div className="flex flex-col min-w-0">
                                                            <span className="text-neutral-200 font-medium truncate text-base mb-0.5">{source.display_name}</span>
                                                            <span className="text-[11px] text-blue-400 font-mono truncate hover:text-blue-300 transition-colors">
                                                                {source.url}
                                                            </span>
                                                        </div>
                                                    </div>

                                                    {/* 2. Last Updated */}
                                                    <div className="flex flex-col px-4 border-l border-neutral-800">
                                                        <span className="text-xs text-neutral-500 font-medium uppercase tracking-wider mb-1">Last Updated</span>
                                                        <span className="text-neutral-300 font-mono text-sm whitespace-nowrap">
                                                            {isActive ? <span className="text-green-400 animate-pulse">Syncing...</span> : source.last_updated}
                                                        </span>
                                                    </div>

                                                    {/* 3. Controls */}
                                                    <div className="flex items-center gap-2">
                                                        {isActive ? (
                                                            <button
                                                                onClick={() => handleCancel(source.id)}
                                                                className="flex items-center gap-2 px-3 py-2 rounded-lg bg-red-900/30 text-red-400 hover:bg-red-900/50 transition-colors text-sm border border-red-900/50"
                                                            >
                                                                <XCircle size={14} />
                                                                Cancel
                                                            </button>
                                                        ) : (
                                                            <button
                                                                onClick={() => toggleConsole(source.id)}
                                                                className="p-2 rounded-lg bg-neutral-800 text-neutral-400 hover:text-neutral-200 transition-colors"
                                                                title="View Logs"
                                                            >
                                                                {isExpanded ? <ChevronUp size={18} /> : <ChevronDown size={18} />}
                                                            </button>
                                                        )}

                                                        <button
                                                            onClick={() => handleUpdateNow(source.id)}
                                                            disabled={isActive}
                                                            className={clsx(
                                                                "flex items-center justify-center gap-2 px-5 py-2.5 rounded-lg font-medium transition-all text-sm shadow-md min-w-[120px]",
                                                                isActive
                                                                    ? "bg-neutral-800 text-neutral-500 cursor-not-allowed border border-neutral-700"
                                                                    : "bg-purple-600 hover:bg-purple-700 text-white hover:shadow-purple-500/20 active:scale-95"
                                                            )}
                                                        >
                                                            {isActive ? (
                                                                <>
                                                                    <RefreshCw size={14} className="animate-spin text-purple-400" />
                                                                    <span className="font-mono text-xs">
                                                                        {progress?.total ? `${progress.current} / ${progress.total}` : "Loading..."}
                                                                    </span>
                                                                </>
                                                            ) : (
                                                                <>
                                                                    <RefreshCw size={14} className="group-hover:rotate-180 transition-transform duration-500" />
                                                                    Update Now
                                                                </>
                                                            )}
                                                        </button>
                                                    </div>
                                                </div>

                                                {/* Console Panel */}
                                                {isExpanded && (
                                                    <div className="border-t border-neutral-800 bg-black/40 p-3 font-mono text-[11px] h-48 overflow-y-auto scroll-smooth flex flex-col-reverse">
                                                        <div className="flex flex-col gap-1">
                                                            {logs.length > 0 ? (
                                                                logs.map((log, idx) => (
                                                                    <div key={idx} className="flex gap-2">
                                                                        <span className="text-neutral-600 shrink-0">[{new Date().toLocaleTimeString([], { hour12: false })}]</span>
                                                                        <span className={clsx(
                                                                            log.startsWith('❌') ? "text-red-400" :
                                                                                log.startsWith('✅') ? "text-green-400" :
                                                                                    log.startsWith('🚀') ? "text-blue-400" :
                                                                                        log.startsWith('🎯') ? "text-purple-400" :
                                                                                            "text-neutral-400"
                                                                        )}>
                                                                            {log}
                                                                        </span>
                                                                    </div>
                                                                ))
                                                            ) : (
                                                                <div className="text-neutral-700 italic">No logs yet. Click 'Update Now' to begin.</div>
                                                            )}
                                                            <div className="h-0" id={`scroll-anchor-${source.id}`}></div>
                                                        </div>
                                                    </div>
                                                )}
                                            </div>
                                        );
                                    })
                                )}
                            </div>
                        </div>

                        {/* LLM Configuration */}
                        <div className="bg-neutral-800 border border-neutral-700 rounded-xl p-6 shadow-lg">
                            <h2 className="text-lg font-semibold mb-2 text-purple-400 flex items-center gap-2">
                                <Terminal size={18} />
                                LLM Configuration
                            </h2>
                            <p className="text-[13px] text-neutral-400 mb-6 font-light">
                                Choose between local or cloud-based AI models for search responses.
                            </p>

                            {/* Provider Toggle */}
                            <div className="mb-6">
                                <label className="block text-xs font-semibold text-neutral-500 uppercase tracking-wider mb-3">Model Provider</label>
                                <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                                    <button
                                        onClick={() => handleProviderChange('local')}
                                        className={clsx(
                                            "flex items-center justify-center gap-2 px-4 py-3 rounded-lg border-2 transition-all",
                                            llmProvider === 'local'
                                                ? "border-purple-500 bg-purple-500/20 text-purple-300"
                                                : "border-neutral-700 bg-neutral-900/50 text-neutral-500 hover:border-neutral-600"
                                        )}
                                    >
                                        <HardDrive size={18} />
                                        <span className="font-medium">Local</span>
                                    </button>
                                    <button
                                        onClick={() => handleProviderChange('deepseek')}
                                        className={clsx(
                                            "flex items-center justify-center gap-2 px-4 py-3 rounded-lg border-2 transition-all",
                                            llmProvider === 'deepseek'
                                                ? "border-purple-500 bg-purple-500/20 text-purple-300"
                                                : "border-neutral-700 bg-neutral-900/50 text-neutral-500 hover:border-neutral-600"
                                        )}
                                    >
                                        <Cloud size={18} />
                                        <span className="font-medium">DeepSeek</span>
                                    </button>
                                    <button
                                        disabled
                                        className={clsx(
                                            "flex items-center justify-center gap-2 px-4 py-3 rounded-lg border-2 transition-all cursor-not-allowed opacity-50",
                                            "border-neutral-800 bg-neutral-900/50 text-neutral-600"
                                        )}
                                    >
                                        <Cloud size={18} />
                                        <span className="font-medium">OpenAI</span>
                                    </button>
                                </div>
                                <p className="text-xs text-neutral-500 mt-2 text-center">
                                    {llmProvider === null ? "💡 Click a provider to enable AI summarization" : "💡 Click selected provider again to disable AI summarization"}
                                </p>
                            </div>

                            {/* Configuration Details */}
                            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                                <div>
                                    <label className="block text-xs font-semibold text-neutral-500 uppercase tracking-wider mb-2">Provider</label>
                                    <div className={clsx(
                                        "rounded-lg px-3 py-2 text-sm",
                                        llmProvider === 'cloud' ? "bg-neutral-800 border border-neutral-700 text-neutral-500" :
                                            llmProvider === null ? "bg-neutral-800 border border-neutral-700 text-neutral-500 italic" :
                                                "bg-neutral-900 border border-neutral-700 text-neutral-300"
                                    )}>
                                        {llmProvider === 'local' ? 'Ollama (Local)' :
                                            llmProvider === 'deepseek' ? 'DeepSeek' :
                                                llmProvider === 'cloud' ? 'OpenAI (Cloud - Disabled)' :
                                                    llmProvider === null ? 'None (Vector search only)' :
                                                        'OpenAI (Cloud)'}
                                    </div>
                                </div>
                                <div>
                                    <label className="block text-xs font-semibold text-neutral-500 uppercase tracking-wider mb-2">Endpoint</label>
                                    <div className={clsx(
                                        "rounded-lg px-3 py-2 text-sm truncate",
                                        llmProvider === 'cloud' ? "bg-neutral-800 border border-neutral-700 text-neutral-500" :
                                            llmProvider === null ? "bg-neutral-800 border border-neutral-700 text-neutral-500 italic" :
                                                "bg-neutral-900 border border-neutral-700 text-neutral-300"
                                    )}>
                                        {llmProvider === 'local' ? 'localhost:11434' :
                                            llmProvider === 'deepseek' ? 'api.deepseek.com' :
                                                llmProvider === 'cloud' ? 'api.openai.com (Disabled)' :
                                                    llmProvider === null ? 'N/A' :
                                                        'api.openai.com'}
                                    </div>
                                </div>
                                <div>
                                    <label className="block text-xs font-semibold text-neutral-500 uppercase tracking-wider mb-2">Model</label>
                                    <div className={clsx(
                                        "rounded-lg px-3 py-2 text-sm",
                                        llmProvider === 'cloud' ? "bg-neutral-800 border border-neutral-700 text-neutral-500" :
                                            llmProvider === null ? "bg-neutral-800 border border-neutral-700 text-neutral-500 italic" :
                                                "bg-neutral-900 border border-neutral-700 text-neutral-300"
                                    )}>
                                        {llmProvider === 'local' ? 'llama3' :
                                            llmProvider === 'deepseek' ? 'deepseek-chat' :
                                                llmProvider === 'cloud' ? 'gpt-4 (Disabled)' :
                                                    llmProvider === null ? 'N/A' :
                                                        'gpt-4'}
                                    </div>
                                </div>
                            </div>

                            {/* Info Message */}
                            <div className={clsx(
                                "mt-4 p-3 rounded-lg text-xs",
                                llmProvider === 'local'
                                    ? "bg-blue-900/20 text-blue-300 border border-blue-900/50"
                                    : llmProvider === 'deepseek'
                                        ? "bg-orange-900/20 text-orange-300 border border-orange-900/50"
                                        : llmProvider === null
                                            ? "bg-gray-800 text-gray-400 border border-gray-700"
                                            : "bg-neutral-800 text-neutral-500 border border-neutral-700"
                            )}>
                                {llmProvider === 'local' ? (
                                    <span>ℹ️ Local models run on your machine via Ollama. Make sure Ollama is running with the llama3 model.</span>
                                ) : llmProvider === 'deepseek' ? (
                                    <span>ℹ️ DeepSeek models. Ensure DEEPSEEK_API_KEY is configured in backend .env file.</span>
                                ) : llmProvider === null ? (
                                    <span>🔍 AI summarization is disabled. Search results will show vector matching only without AI-generated summaries.</span>
                                ) : (
                                    <span>⚠️ OpenAI option is currently disabled. Please use Local or DeepSeek instead.</span>
                                )}
                            </div>
                        </div>
                    </>
                ) : (
                    <PDFManager />
                )}
            </div>
        </div>
    );
}
