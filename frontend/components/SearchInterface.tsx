"use client";

import React, { useState, useEffect, useRef } from 'react';
import { Search, Loader2, BookOpen, ExternalLink, MessageSquare, Settings, FileText, Clock, X } from 'lucide-react';
import clsx from 'clsx';
import Link from 'next/link';

type Source = {
    title: string;
    url: string;
    snippet: string;
    filename?: string;
    page?: number;
};

export default function SearchInterface() {
    const [query, setQuery] = useState('');
    const [hasSearched, setHasSearched] = useState(false);
    const [loading, setLoading] = useState(false);
    const [llmLoading, setLlmLoading] = useState(false);  // LLM总结中
    const [sources, setSources] = useState<Source[]>([]);
    const [answer, setAnswer] = useState('');
    const [llmProvider, setLlmProvider] = useState<'local' | 'cloud' | 'deepseek' | null>(null);
    const [resultLimit, setResultLimit] = useState<number>(10);
    const [elapsedTime, setElapsedTime] = useState(0);  // 计时器
    const timerRef = useRef<NodeJS.Timeout | null>(null);

    // Load LLM provider preference from localStorage on mount
    React.useEffect(() => {
        const saved = localStorage.getItem('llm_provider');
        if (saved === 'local' || saved === 'deepseek') {
            setLlmProvider(saved);
        } else if (saved === 'cloud' || saved === 'null' || saved === null) {
            setLlmProvider(null);
            localStorage.setItem('llm_provider', 'null');
        }

        const savedLimit = localStorage.getItem('result_limit');
        if (savedLimit) {
            const limit = parseInt(savedLimit);
            if (!isNaN(limit) && limit >= 1 && limit <= 50) {
                setResultLimit(limit);
            }
        }
    }, []);

    // 计时器效果
    useEffect(() => {
        if (llmLoading) {
            timerRef.current = setInterval(() => {
                setElapsedTime(prev => prev + 1);
            }, 1000);
        } else {
            if (timerRef.current) {
                clearInterval(timerRef.current);
                timerRef.current = null;
            }
        }
        return () => {
            if (timerRef.current) {
                clearInterval(timerRef.current);
            }
        };
    }, [llmLoading]);

    // 格式化时间显示
    const formatTime = (seconds: number) => {
        const mins = Math.floor(seconds / 60);
        const secs = seconds % 60;
        if (mins > 0) {
            return `${mins}分${secs}秒`;
        }
        return `${secs}秒`;
    };

    const handleLimitChange = (limit: number) => {
        setResultLimit(limit);
        localStorage.setItem('result_limit', limit.toString());
    };

    const handleClear = () => {
        setQuery('');
        setHasSearched(false);
        setSources([]);
        setAnswer('');
        setLlmLoading(false);
        setElapsedTime(0);
    };

    const handleSearch = async (e: React.FormEvent) => {
        e.preventDefault();
        if (!query.trim()) return;

        setLoading(true);
        setLlmLoading(false);
        setHasSearched(true);
        setSources([]);
        setAnswer('');
        setElapsedTime(0);

        try {
            const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
            const response = await fetch(`${API_BASE}/search/stream`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    query: query,
                    limit: resultLimit,
                    llm_provider: llmProvider || 'none'
                })
            });

            if (!response.ok) {
                throw new Error('Network response was not ok');
            }

            const reader = response.body?.getReader();
            const decoder = new TextDecoder();

            if (!reader) {
                throw new Error('Response body is null');
            }

            setLoading(false);

            let buffer = '';
            let sourcesReceived = false;

            while (true) {
                const { done, value } = await reader.read();

                if (done) break;

                buffer += decoder.decode(value, { stream: true });

                const lines = buffer.split('\n');
                buffer = lines.pop() || '';

                for (const line of lines) {
                    if (line.startsWith('data: ')) {
                        const data = line.slice(6);
                        try {
                            const parsed = JSON.parse(data);

                            if (parsed.type === 'ping') {
                                // 忽略 ping 消息，仅用于触发流刷新
                                continue;
                            } else if (parsed.type === 'sources') {
                                // 立即显示向量搜索结果
                                console.log('收到向量搜索结果:', parsed.data.length, '条');
                                console.log('设置sources状态...');
                                setSources(parsed.data);
                                sourcesReceived = true;
                                console.log('sources状态已设置，长度:', parsed.data.length);
                                // 只有当使用LLM且有数据时才显示LLM loading
                                console.log('当前LLM提供商:', llmProvider);
                                if (parsed.data.length > 0 && llmProvider) {
                                    console.log('开始LLM总结...');
                                    setLlmLoading(true);
                                }
                            } else if (parsed.type === 'answer') {
                                // 流式显示答案
                                console.log('收到AI内容片段:', parsed.content);
                                setAnswer(prev => prev + parsed.content);
                            } else if (parsed.type === 'done') {
                                setLlmLoading(false);
                            } else if (parsed.type === 'error') {
                                setAnswer(`错误: ${parsed.message}`);
                                setLlmLoading(false);
                            }
                        } catch (e) {
                            console.error('Failed to parse SSE data:', e);
                        }
                    }
                }
            }

        } catch (err) {
            console.error(err);
            setSources([]);
            setAnswer("抱歉，搜索时出现错误。请确保后端服务正在运行。");
            setLlmLoading(false);
        } finally {
            setLoading(false);
        }
    };

    const getProviderName = () => {
        if (llmProvider === 'local') return '本地 Ollama';
        if (llmProvider === 'deepseek') return 'DeepSeek';
        if (llmProvider === null) return null;
        return 'OpenAI';
    };

    return (
        <div className={clsx("min-h-screen bg-neutral-900 text-neutral-100 transition-all duration-500 flex flex-col items-center",
            hasSearched ? "pt-4" : "justify-center -mt-20"
        )}>

            {/* Top Right Settings */}
            <Link href="/settings" className="absolute top-6 right-6 p-2 rounded-full hover:bg-neutral-800 transition-colors text-neutral-400 hover:text-white">
                <Settings size={24} />
            </Link>

            {/* Search Header Area */}
            <div className={clsx("w-full max-w-4xl px-4 transition-all duration-500",
                hasSearched ? "mb-6" : "mb-0"
            )}>

                {/* Logo / Title */}
                <div className={clsx("flex items-center gap-2 mb-8 transition-opacity duration-300",
                    hasSearched ? "opacity-100" : "justify-center opacity-100 scale-110 mb-12"
                )}>
                    {!hasSearched ? (
                        <h1 className="text-4xl font-bold bg-clip-text text-transparent bg-gradient-to-r from-purple-400 to-pink-600">
                            Avid Knowledge Base
                        </h1>
                    ) : (
                        <div className="text-xl font-bold text-neutral-300 mr-4 cursor-pointer" onClick={() => window.location.reload()}>
                            Avid Knowledge Base
                        </div>
                    )}
                </div>

                {/* Search Bar */}
                <form onSubmit={handleSearch} className="relative w-full">
                    <input
                        type="text"
                        className="w-full bg-neutral-800 border border-neutral-700 rounded-full px-6 py-4 pl-14 text-lg focus:outline-none focus:ring-2 focus:ring-purple-500 shadow-xl transition-all"
                        placeholder=""
                        value={query}
                        onChange={(e) => setQuery(e.target.value)}
                    />
                    <Search className="absolute left-5 top-1/2 transform -translate-y-1/2 text-neutral-400" size={24} />
                    {loading && (
                        <Loader2 className="absolute right-5 top-1/2 transform -translate-y-1/2 text-purple-500 animate-spin" size={24} />
                    )}
                    {!loading && query && (
                        <button
                            type="button"
                            onClick={handleClear}
                            className="absolute right-5 top-1/2 transform -translate-y-1/2 text-neutral-400 hover:text-neutral-200 transition-colors rounded-full hover:bg-neutral-700 p-1"
                            title="清空"
                        >
                            <X size={20} />
                        </button>
                    )}
                </form>

                {/* Search Options */}
                <div className={clsx(
                    "mt-4 flex items-center justify-between transition-all duration-300",
                    hasSearched ? "opacity-100" : "opacity-0 -mt-2 pointer-events-none"
                )}>
                    <div className="flex items-center gap-3">
                        <span className="text-xs text-neutral-500 uppercase tracking-wider">Sources:</span>
                        <select
                            value={resultLimit}
                            onChange={(e) => handleLimitChange(Number(e.target.value))}
                            className="bg-neutral-800 border border-neutral-700 rounded-lg px-3 py-1.5 text-sm text-neutral-300 focus:outline-none focus:ring-2 focus:ring-purple-500 cursor-pointer hover:border-neutral-600 transition-colors"
                        >
                            <option value={5}>5</option>
                            <option value={10}>10</option>
                            <option value={15}>15</option>
                            <option value={20}>20</option>
                            <option value={30}>30</option>
                            <option value={50}>50</option>
                        </select>
                    </div>
                    <div className="text-xs text-neutral-600">
                        {llmProvider === 'local' ? 'Using Local (Ollama)' :
                            llmProvider === 'deepseek' ? 'Using DeepSeek' :
                                llmProvider === null ? 'Vector search only (no AI)' :
                                    'Using OpenAI'}
                    </div>
                </div>
            </div>

            {/* Results Area */}
            {hasSearched && (
                <div className="w-full max-w-4xl px-4 pb-20 fade-in-up">

                    {/* LLM Loading Indicator with Timer - 最上方 */}
                    {llmLoading && getProviderName() && (
                        <div className="mb-8 p-6 bg-gradient-to-r from-purple-900/30 to-pink-900/30 border border-purple-700/50 rounded-xl shadow-lg">
                            <div className="flex items-center gap-4">
                                <Loader2 className="text-purple-400 animate-spin" size={24} />
                                <div className="flex-1">
                                    <div className="text-lg font-semibold text-purple-300 mb-1">
                                        {getProviderName()} 正在总结内容...
                                    </div>
                                    <div className="flex items-center gap-2 text-sm text-neutral-400">
                                        <Clock size={16} />
                                        <span>已等待 {formatTime(elapsedTime)}</span>
                                        <span className="text-neutral-500">•</span>
                                        <span>请耐心等待，本地模型可能需要几分钟</span>
                                    </div>
                                </div>
                            </div>
                        </div>
                    )}

                    {/* AI Answer Card - 第二个显示 */}
                    {(answer || llmLoading) && (
                        <div className="mb-8 p-6 bg-neutral-800/50 border border-neutral-700 rounded-xl shadow-lg backdrop-blur-sm">
                            <div className="flex items-center gap-3 mb-4 text-purple-400">
                                <MessageSquare size={20} />
                                <h2 className="text-lg font-semibold">AI 总结</h2>
                                {llmLoading && <Loader2 className="animate-spin" size={16} />}
                            </div>
                            <div className="prose prose-invert max-w-none text-neutral-200 leading-relaxed">
                                {answer || <span className="text-neutral-500 italic">正在生成总结...</span>}
                                {llmLoading && <span className="inline-block w-2 h-4 bg-purple-400 ml-1 animate-pulse"></span>}
                            </div>
                        </div>
                    )}

                    {/* Sources List - 最后显示（向量搜索结果） */}
                    {sources.length > 0 && (
                        <div className="grid gap-4 mb-8">
                            <h3 className="text-neutral-400 font-medium mb-2 pl-1">
                                向量搜索结果 ({sources.length})
                            </h3>
                            {sources.map((source, idx) => {
                                const isPDF = 'filename' in source && source.filename;
                                return (
                                    <a
                                        key={idx}
                                        href={source.url}
                                        target="_blank"
                                        rel="noopener noreferrer"
                                        className="group p-5 bg-neutral-800 border border-neutral-700 rounded-lg hover:border-purple-500/50 hover:bg-neutral-800/80 transition-all"
                                    >
                                        <div className="flex items-start justify-between">
                                            <div className="flex-1 min-w-0">
                                                {/* 来源标识 */}
                                                <div className="flex items-center gap-2 mb-2">
                                                    {isPDF ? (
                                                        <>
                                                            <FileText size={16} className="text-blue-400" />
                                                            <span className="text-xs bg-blue-900/30 text-blue-300 px-2 py-0.5 rounded">
                                                                文档
                                                            </span>
                                                        </>
                                                    ) : (
                                                        <>
                                                            <BookOpen size={16} className="text-green-400" />
                                                            <span className="text-xs bg-green-900/30 text-green-300 px-2 py-0.5 rounded">
                                                                论坛
                                                            </span>
                                                        </>
                                                    )}
                                                </div>

                                                {/* 标题 */}
                                                <h4 className="text-purple-300 font-medium group-hover:text-purple-200 mb-1 truncate">
                                                    {source.title}
                                                </h4>

                                                {/* PDF 元数据 */}
                                                {isPDF && (
                                                    <div className="text-xs text-neutral-500 mb-1">
                                                        文档: {source.filename}
                                                        {source.page && ` • 第 {source.page} 页`}
                                                    </div>
                                                )}

                                                {/* 内容片段 */}
                                                <p className="text-sm text-neutral-400 line-clamp-2">
                                                    {source.snippet}
                                                </p>
                                            </div>

                                            <ExternalLink size={16} className="text-neutral-500 group-hover:text-purple-400 flex-shrink-0 ml-2" />
                                        </div>
                                    </a>
                                );
                            })}
                        </div>
                    )}

                    {sources.length === 0 && !loading && !llmLoading && (
                        <div className="text-center text-neutral-500 mt-12">
                            未找到相关结果。请尝试运行爬虫或添加PDF文档。
                        </div>
                    )}
                </div>
            )}

            <style jsx global>{`
        @keyframes fadeInUp {
            from { opacity: 0; transform: translateY(10px); }
            to { opacity: 1; transform: translateY(0); }
        }
        .fade-in-up {
            animation: fadeInUp 0.5s ease-out forwards;
        }
      `}</style>
        </div>
    );
}
