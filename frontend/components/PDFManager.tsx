"use client";

import React, { useState, useCallback } from 'react';
import { Upload, FileText, Trash2, RefreshCw, CheckCircle, XCircle, AlertCircle } from 'lucide-react';
import axios from 'axios';

interface PDFDocument {
    id: number;
    filename: string;
    original_name: string;
    file_size: number;
    total_pages: number;
    total_chunks: number;
    upload_date: string;
    last_indexed: string;
    status: 'pending' | 'processing' | 'completed' | 'failed';
    error: string | null;
}

export default function PDFManager() {
    const [pdfs, setPdfs] = useState<PDFDocument[]>([]);
    const [loading, setLoading] = useState(true);
    const [uploading, setUploading] = useState(false);
    const [activeIndexing, setActiveIndexing] = useState<Record<number, boolean>>({});
    const [indexLogs, setIndexLogs] = useState<Record<number, string[]>>({});
    const [expandedLogs, setExpandedLogs] = useState<Record<number, boolean>>({});

    const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

    const fetchPDFs = useCallback(async () => {
        setLoading(true);
        try {
            const res = await axios.get(`${API_BASE}/pdf/list`);
            setPdfs(res.data);
        } catch (err) {
            console.error("Failed to fetch PDFs:", err);
        } finally {
            setLoading(false);
        }
    }, [API_BASE]);

    React.useEffect(() => {
        fetchPDFs();
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, []);

    const handleUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
        const file = e.target.files?.[0];
        if (!file) return;

        if (!file.name.endsWith('.pdf')) {
            alert('Please upload a PDF file');
            return;
        }

        setUploading(true);
        const formData = new FormData();
        formData.append('file', file);

        try {
            await axios.post(`${API_BASE}/pdf/upload`, formData, {
                headers: { 'Content-Type': 'multipart/form-data' }
            });

            // Refresh list
            await fetchPDFs();

            // Auto-start indexing
            const res = await axios.get(`${API_BASE}/pdf/list`);
            const newPdf = res.data.find((p: PDFDocument) => p.original_name === file.name);
            if (newPdf) {
                handleIndex(newPdf.id);
            }
        } catch (err: any) {
            alert(`Upload failed: ${err.response?.data?.detail || err.message}`);
        } finally {
            setUploading(false);
        }
    };

    const handleIndex = async (pdfId: number) => {
        if (activeIndexing[pdfId]) return;

        setActiveIndexing(prev => ({ ...prev, [pdfId]: true }));
        setIndexLogs(prev => ({ ...prev, [pdfId]: ["Starting indexing..."] }));
        setExpandedLogs(prev => ({ ...prev, [pdfId]: true }));

        try {
            // Start indexing
            await axios.post(`${API_BASE}/pdf/${pdfId}/index`);

            // Subscribe to progress
            const eventSource = new EventSource(`${API_BASE}/pdf/indexing/progress/${pdfId}`);

            eventSource.onmessage = (event) => {
                const data = JSON.parse(event.data);

                if (data.type === 'log') {
                    setIndexLogs(prev => ({
                        ...prev,
                        [pdfId]: [...(prev[pdfId] || []), data.message]
                    }));
                } else if (data.type === 'status' && data.message === 'finished') {
                    eventSource.close();
                    setActiveIndexing(prev => ({ ...prev, [pdfId]: false }));
                    fetchPDFs(); // Refresh list
                } else if (data.type === 'status' && data.message === 'error') {
                    eventSource.close();
                    setActiveIndexing(prev => ({ ...prev, [pdfId]: false }));
                }
            };

            eventSource.onerror = () => {
                setIndexLogs(prev => ({
                    ...prev,
                    [pdfId]: [...(prev[pdfId] || []), "Connection lost"]
                }));
                eventSource.close();
                setActiveIndexing(prev => ({ ...prev, [pdfId]: false }));
            };

        } catch (err: any) {
            alert(`Indexing failed: ${err.response?.data?.detail || err.message}`);
            setActiveIndexing(prev => ({ ...prev, [pdfId]: false }));
        }
    };

    const handleDelete = async (pdfId: number) => {
        if (!confirm('Are you sure you want to delete this PDF and all its indexed data?')) {
            return;
        }

        try {
            await axios.delete(`${API_BASE}/pdf/${pdfId}`);
            await fetchPDFs();
        } catch (err: any) {
            alert(`Delete failed: ${err.response?.data?.detail || err.message}`);
        }
    };

    const formatFileSize = (bytes: number) => {
        if (bytes < 1024) return bytes + ' B';
        if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
        return (bytes / (1024 * 1024)).toFixed(1) + ' MB';
    };

    const getStatusIcon = (status: string) => {
        switch (status) {
            case 'completed':
                return <CheckCircle className="text-green-400" size={18} />;
            case 'processing':
                return <RefreshCw className="text-blue-400 animate-spin" size={18} />;
            case 'failed':
                return <XCircle className="text-red-400" size={18} />;
            default:
                return <AlertCircle className="text-yellow-400" size={18} />;
        }
    };

    return (
        <div>
            {/* Upload Section */}
            <div className="bg-neutral-800 border border-neutral-700 rounded-xl p-6 mb-6">
                <h2 className="text-lg font-semibold text-purple-400 mb-4">Upload PDF Document</h2>

                <div className="border-2 border-dashed border-neutral-600 rounded-lg p-8 text-center hover:border-purple-500/50 transition-colors">
                    <input
                        type="file"
                        accept=".pdf"
                        onChange={handleUpload}
                        disabled={uploading}
                        className="hidden"
                        id="pdf-upload"
                    />
                    <label htmlFor="pdf-upload" className="cursor-pointer">
                        <Upload className="mx-auto mb-3 text-neutral-400" size={32} />
                        <p className="text-neutral-300 mb-1">
                            {uploading ? "Uploading..." : "Click to upload or drag and drop"}
                        </p>
                        <p className="text-sm text-neutral-500">PDF files only</p>
                    </label>
                </div>
            </div>

            {/* PDF List */}
            <div className="bg-neutral-800 border border-neutral-700 rounded-xl p-6">
                <div className="flex items-center justify-between mb-6">
                    <h2 className="text-lg font-semibold text-purple-400">Document Library</h2>
                    <span className="text-xs bg-neutral-700 text-neutral-400 px-2 py-1 rounded">
                        {pdfs.filter(p => p.status === 'completed').length} indexed
                    </span>
                </div>

                {loading ? (
                    <div className="text-center py-12 text-neutral-500">
                        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-purple-500 mx-auto mb-4"></div>
                        <p>Loading documents...</p>
                    </div>
                ) : pdfs.length === 0 ? (
                    <div className="text-center py-12 text-neutral-500 border border-dashed border-neutral-700 rounded-lg">
                        <FileText className="mx-auto mb-3" size={48} />
                        <p>No documents uploaded yet</p>
                    </div>
                ) : (
                    <div className="space-y-4">
                        {pdfs.map((pdf) => {
                            const isIndexing = activeIndexing[pdf.id];
                            const logs = indexLogs[pdf.id] || [];
                            const isExpanded = expandedLogs[pdf.id];

                            return (
                                <div key={pdf.id} className="bg-neutral-900/50 rounded-lg border border-neutral-800 overflow-hidden">
                                    {/* Main Content */}
                                    <div className="p-4">
                                        <div className="flex items-start justify-between">
                                            <div className="flex-1">
                                                <div className="flex items-center gap-2 mb-1">
                                                    {getStatusIcon(pdf.status)}
                                                    <h3 className="font-medium text-neutral-200">
                                                        {pdf.original_name}
                                                    </h3>
                                                </div>
                                                <div className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-neutral-400 mt-2">
                                                    <span>{pdf.total_pages || '?'} pages</span>
                                                    <span>{pdf.total_chunks || '?'} chunks</span>
                                                    <span>{formatFileSize(pdf.file_size)}</span>
                                                    {pdf.status === 'completed' && (
                                                        <span className="text-green-400">Indexed</span>
                                                    )}
                                                </div>
                                                {pdf.error && (
                                                    <p className="text-xs text-red-400 mt-1">{pdf.error}</p>
                                                )}
                                            </div>

                                            <div className="flex items-center gap-2 ml-4">
                                                {!isIndexing && pdf.status !== 'completed' && (
                                                    <button
                                                        onClick={() => handleIndex(pdf.id)}
                                                        className="px-3 py-1.5 bg-purple-600 hover:bg-purple-700 text-white text-sm rounded-lg transition-colors"
                                                    >
                                                        Index
                                                    </button>
                                                )}

                                                {isIndexing && (
                                                    <button
                                                        onClick={() => setExpandedLogs(prev => ({ ...prev, [pdf.id]: !isExpanded }))}
                                                        className="px-3 py-1.5 bg-blue-600 hover:bg-blue-700 text-white text-sm rounded-lg transition-colors"
                                                    >
                                                        {isExpanded ? 'Hide' : 'Show'} Logs
                                                    </button>
                                                )}

                                                <button
                                                    onClick={() => handleDelete(pdf.id)}
                                                    className="p-1.5 text-red-400 hover:bg-red-900/30 rounded-lg transition-colors"
                                                    title="Delete"
                                                >
                                                    <Trash2 size={16} />
                                                </button>
                                            </div>
                                        </div>

                                        {/* Indexing Logs */}
                                        {isExpanded && logs.length > 0 && (
                                            <div className="mt-4 bg-black/40 rounded-lg p-3 font-mono text-[11px] h-48 overflow-y-auto">
                                                <div className="flex flex-col gap-1">
                                                    {logs.map((log, idx) => (
                                                        <div key={idx} className="flex gap-2">
                                                            <span className="text-neutral-600 shrink-0">
                                                                [{new Date().toLocaleTimeString([], { hour12: false })}]
                                                            </span>
                                                            <span
                                                                className={
                                                                    log.startsWith('Error') ? "text-red-400" :
                                                                    log.startsWith('Success') ? "text-green-400" :
                                                                    log.startsWith('Starting') ? "text-blue-400" :
                                                                    "text-neutral-400"
                                                                }
                                                            >
                                                                {log}
                                                            </span>
                                                        </div>
                                                    ))}
                                                </div>
                                            </div>
                                        )}
                                    </div>
                                </div>
                            );
                        })}
                    </div>
                )}
            </div>
        </div>
    );
}
