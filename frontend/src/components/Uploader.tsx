"use client";

import React, { useState, useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { 
  Upload, FileText, CheckCircle2, AlertCircle, 
  Loader2, ArrowRight, ShieldCheck, PieChart, 
  Clock, FileSearch, Trash2, Download, Edit3
} from "lucide-react";
import axios from "axios";
import * as XLSX from "xlsx";
import { ReviewModal } from "./ReviewModal";

interface ExtractionResult {
  status: string;
  request_id: string;
  doc_type: string;
  filename: string;
  extracted_data: Record<string, any>;
  confidence: number;
  compliance_flags: string[];
  processing_time_ms: number;
  message?: string;
  partial_data?: Record<string, any>;
}

export const Uploader = () => {
  const [file, setFile] = useState<File | null>(null);
  const [isUploading, setIsUploading] = useState(false);
  const [progress, setProgress] = useState(0);
  const [result, setResult] = useState<ExtractionResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isReviewOpen, setIsReviewOpen] = useState(false);
  const [isResolved, setIsResolved] = useState(false);

  // Simulate progress when uploading
  useEffect(() => {
    let interval: NodeJS.Timeout;
    if (isUploading) {
      setProgress(0);
      interval = setInterval(() => {
        setProgress((prev) => {
          if (prev >= 95) return prev;
          return prev + Math.random() * 15;
        });
      }, 500);
    }
    return () => clearInterval(interval);
  }, [isUploading]);

  const onFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      setFile(e.target.files[0]);
      setError(null);
    }
  };

  const handleUpload = async () => {
    if (!file) return;

    setIsUploading(true);
    setError(null);
    setResult(null);
    setIsResolved(false);

    const formData = new FormData();
    formData.append("file", file);
    formData.append("tenant_id", "demo_user");
    formData.append("doc_type", "unknown");

    try {
      const response = await axios.post("http://localhost:8000/api/v1/extract", formData);
      setProgress(100);
      setTimeout(() => {
        setResult(response.data);
        setIsUploading(false);
      }, 500);
    } catch (err: any) {
      setError(err.response?.data?.detail || "Failed to process document. Make sure backend is running on port 8000.");
      setIsUploading(false);
    }
  };

  const reset = () => {
    setFile(null);
    setResult(null);
    setError(null);
    setProgress(0);
    setIsResolved(false);
  };

  const getFilteredData = () => {
    const data = result?.extracted_data || result?.partial_data || {};
    return Object.entries(data).filter(([key]) => !["raw_text", "char_count"].includes(key));
  };

  const formatValueForExcel = (value: any): string => {
    if (value === null || value === undefined) return "";
    if (Array.isArray(value)) {
      if (value.length === 0) return "";
      if (typeof value[0] === "object") {
        // Convert list of objects (like transactions) into a readable multi-line string for the cell
        return value.map(item => 
          Object.entries(item)
            .map(([k, v]) => `${k.replace(/_/g, " ")}: ${v}`)
            .join(" | ")
        ).join("\n");
      }
      return value.join(", ");
    }
    if (typeof value === "object") return JSON.stringify(value);
    return String(value);
  };

  const renderValue = (value: any): React.ReactNode => {
    if (value === null || value === undefined) return <span style={{ color: "rgba(255,255,255,0.2)" }}>null</span>;
    
    if (Array.isArray(value)) {
      if (value.length === 0) return "[]";
      // If it's an array of objects (like transactions), render a nested table
      if (typeof value[0] === "object") {
        const columns = Object.keys(value[0]);
        return (
          <div className="extraction-table-container" style={{ margin: "0.5rem 0", background: "rgba(0,0,0,0.2)" }}>
            <table className="extraction-table" style={{ fontSize: "0.8rem" }}>
              <thead>
                <tr>
                  {columns.map(col => <th key={col}>{col.replace(/_/g, " ")}</th>)}
                </tr>
              </thead>
              <tbody>
                {value.map((item, i) => (
                  <tr key={i}>
                    {columns.map(col => <td key={col}>{String(item[col] ?? "-")}</td>)}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        );
      }
      return value.join(", ");
    }

    if (typeof value === "object") {
      return JSON.stringify(value);
    }

    return String(value);
  };

  const downloadExcel = () => {
    if (!result) return;
    
    // Format data for Excel
    const data = getFilteredData().map(([key, value]) => ({
      "Field Name": key.replace(/_/g, " ").toUpperCase(),
      "Extracted Value": formatValueForExcel(value)
    }));

    // Create worksheet
    const worksheet = XLSX.utils.json_to_sheet(data);
    
    // Adjust column widths
    const maxWidth = data.reduce((w, r) => Math.max(w, r["Field Name"].length), 15);
    worksheet["!cols"] = [{ wch: maxWidth }, { wch: 30 }];

    // Create workbook and append sheet
    const workbook = XLSX.utils.book_new();
    XLSX.utils.book_append_sheet(workbook, worksheet, "Extraction Results");

    // Save file
    const fileName = result.filename ? `${result.filename.split('.')[0]}_extraction.xlsx` : "taxyn_extraction.xlsx";
    XLSX.writeFile(workbook, fileName);
  };

  return (
    <div className="uploader-container">
      <AnimatePresence mode="wait">
        {!result ? (
          <motion.div
            key="upload"
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.95 }}
          >
            <div 
              className="dropzone glass glass-hover"
              onClick={() => !isUploading && document.getElementById("fileInput")?.click()}
              style={{ cursor: isUploading ? "default" : "pointer" }}
            >
              <input 
                type="file" 
                id="fileInput" 
                hidden 
                accept=".pdf"
                onChange={onFileChange} 
                disabled={isUploading}
              />
              
              <div className="dropzone-icon">
                {isUploading ? (
                  <Loader2 className="animate-spin" size={64} />
                ) : (
                  <Upload size={64} />
                )}
              </div>

              {isUploading ? (
                <div className="progress-container">
                  <h3 style={{ marginBottom: "1rem" }}>Analyzing Document...</h3>
                  <div className="progress-track">
                    <motion.div 
                      className="progress-bar" 
                      animate={{ width: `${progress}%` }}
                      transition={{ type: "spring", stiffness: 50 }}
                    />
                  </div>
                  <p style={{ color: "rgba(255,255,255,0.5)", fontSize: "0.875rem" }}>
                    {progress < 40 ? "Extracting Text..." : progress < 80 ? "Parsing Fields..." : "Validating Compliance..."}
                  </p>
                </div>
              ) : (
                <div style={{ textAlign: "center" }}>
                  <h3 style={{ marginBottom: "0.5rem" }}>{file ? file.name : "Upload your document"}</h3>
                  <p style={{ color: "rgba(255,255,255,0.5)" }}>
                    {file ? `${(file.size / 1024 / 1024).toFixed(2)} MB • PDF` : "Drag and drop or click to browse"}
                  </p>
                </div>
              )}

              {file && !isUploading && (
                <motion.button
                  initial={{ opacity: 0, y: 10 }}
                  animate={{ opacity: 1, y: 0 }}
                  className="btn btn-primary"
                  style={{ marginTop: "2rem" }}
                  onClick={(e) => {
                    e.stopPropagation();
                    handleUpload();
                  }}
                >
                  Start Extraction <ArrowRight size={18} />
                </motion.button>
              )}
            </div>

            {error && (
              <motion.div 
                initial={{ opacity: 0 }} 
                animate={{ opacity: 1 }}
                style={{ 
                  marginTop: "1.5rem", 
                  color: "var(--error)", 
                  display: "flex", 
                  alignItems: "center", 
                  gap: "0.5rem",
                  justifyContent: "center"
                }}
              >
                <AlertCircle size={18} /> {error}
              </motion.div>
            )}
          </motion.div>
        ) : (
          <motion.div
            key="result"
            initial={{ opacity: 0, scale: 0.9 }}
            animate={{ opacity: 1, scale: 1 }}
            className="result-card glass"
          >
            <div className="result-header">
              <div>
                <div style={{ display: "flex", alignItems: "center", gap: "1rem", marginBottom: "0.5rem" }}>
                  <h2 className="text-gradient" style={{ fontSize: "2rem" }}>
                    {isResolved ? "Correction Complete" : result.status === "completed" ? "Extraction Complete" : "Review Required"}
                  </h2>
                  <span className={`status-badge ${isResolved || result.status === "completed" ? "status-completed" : "status-review"}`}>
                    {isResolved ? "resolved" : result.status.replace("_", " ")}
                  </span>
                </div>
                <p style={{ color: "rgba(255,255,255,0.5)" }}>
                  {result.filename} • {result.doc_type}
                </p>
              </div>
              
              <div className="confidence-ring">
                <svg width="120" height="120" viewBox="0 0 120 120">
                  <circle
                    cx="60" cy="60" r="54"
                    fill="none"
                    stroke="rgba(255,255,255,0.1)"
                    strokeWidth="8"
                  />
                  <motion.circle
                    cx="60" cy="60" r="54"
                    fill="none"
                    stroke={isResolved || result.confidence > 0.85 ? "var(--success)" : "var(--warning)"}
                    strokeWidth="8"
                    strokeDasharray="339.292"
                    initial={{ strokeDashoffset: 339.292 }}
                    animate={{ strokeDashoffset: 339.292 * (1 - (isResolved ? 1.0 : result.confidence)) }}
                    transition={{ duration: 1.5, ease: "easeOut" }}
                    strokeLinecap="round"
                  />
                </svg>
                <div style={{ position: "absolute", textAlign: "center" }}>
                  <div style={{ fontSize: "1.5rem", fontWeight: 800 }}>
                    {( (isResolved ? 1.0 : result.confidence) * 100).toFixed(0)}%
                  </div>
                  <div style={{ fontSize: "0.6rem", textTransform: "uppercase", color: "rgba(255,255,255,0.4)" }}>
                    Confidence
                  </div>
                </div>
              </div>
            </div>

            <div className="extraction-table-container">
              <table className="extraction-table">
                <thead>
                  <tr>
                    <th>Field Name</th>
                    <th>Extracted Value</th>
                  </tr>
                </thead>
                <tbody>
                  {getFilteredData().map(([key, value], idx) => (
                    <motion.tr 
                      key={key}
                      initial={{ opacity: 0, x: -10 }}
                      animate={{ opacity: 1, x: 0 }}
                      transition={{ delay: idx * 0.05 }}
                    >
                      <td className="field-name-cell">{key.replace(/_/g, " ")}</td>
                      <td className="field-value-cell">{renderValue(value)}</td>
                    </motion.tr>
                  ))}
                </tbody>
              </table>
            </div>

            {result.compliance_flags?.length > 0 && !isResolved && (
              <div style={{ marginTop: "3rem" }}>
                <h4 style={{ marginBottom: "1rem", display: "flex", alignItems: "center", gap: "0.5rem", color: "var(--warning)" }}>
                  <AlertCircle size={18} /> Compliance Flags
                </h4>
                <div style={{ display: "flex", flexDirection: "column", gap: "0.75rem" }}>
                  {result.compliance_flags.map((flag, idx) => (
                    <motion.div 
                      key={idx}
                      initial={{ x: -20, opacity: 0 }}
                      animate={{ x: 0, opacity: 1 }}
                      transition={{ delay: 0.3 + (idx * 0.1) }}
                      style={{ 
                        padding: "1rem", 
                        borderRadius: "1rem", 
                        background: "rgba(245, 158, 11, 0.05)", 
                        border: "1px solid rgba(245, 158, 11, 0.2)",
                        fontSize: "0.9rem"
                      }}
                    >
                      {flag}
                    </motion.div>
                  ))}
                </div>
              </div>
            )}

            <div style={{ marginTop: "3rem", display: "flex", justifyContent: "space-between", alignItems: "center" }}>
              <div style={{ display: "flex", gap: "1rem" }}>
                {!isResolved && result.status !== "completed" && (
                  <button className="btn btn-primary" onClick={() => setIsReviewOpen(true)}>
                    <Edit3 size={18} /> Review & Correct
                  </button>
                )}
                <button className="btn btn-secondary" onClick={downloadExcel}>
                  <Download size={18} /> Download Excel
                </button>
                <button className="btn btn-secondary" onClick={reset}>
                  <Trash2 size={18} /> Process Another
                </button>
              </div>

              <div style={{ display: "flex", gap: "2rem" }}>
                <div style={{ display: "flex", alignItems: "center", gap: "0.5rem", color: "rgba(255,255,255,0.4)", fontSize: "0.8rem" }}>
                  <Clock size={14} /> {(result.processing_time_ms || 0).toFixed(0)}ms
                </div>
                <div style={{ display: "flex", alignItems: "center", gap: "0.5rem", color: "rgba(255,255,255,0.4)", fontSize: "0.8rem" }}>
                  <FileSearch size={14} /> ID: {result.request_id.slice(0, 8)}
                </div>
              </div>
            </div>

            <ReviewModal 
              isOpen={isReviewOpen} 
              onClose={() => setIsReviewOpen(false)}
              data={result.extracted_data || result.partial_data}
              requestId={result.request_id}
              onResolved={() => setIsResolved(true)}
            />
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
};
