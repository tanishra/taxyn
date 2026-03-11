"use client";

import React, { useState, useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { 
  Upload, FileText, CheckCircle2, AlertCircle, 
  Loader2, ArrowRight, ShieldCheck, PieChart, 
  Clock, FileSearch, Trash2, Download, Edit3, 
  RefreshCcw, AlertTriangle, CheckCircle, ChevronDown,
  Database, LogIn
} from "lucide-react";
import axios from "axios";
import * as XLSX from "xlsx";
import { ReviewModal } from "./ReviewModal";
import { useAuth } from "./AuthContext";
import { useRouter } from "next/navigation";

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
  const { token, user } = useAuth();
  const router = useRouter();
  const [file, setFile] = useState<File | null>(null);
  const [portalFile, setPortalFile] = useState<File | null>(null);
  const [docType, setDocType] = useState("unknown");
  const [isUploading, setIsUploading] = useState(false);
  const [isPortalUploading, setIsPortalUploading] = useState(false);
  const [progress, setProgress] = useState(0);
  const [result, setResult] = useState<ExtractionResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isReviewOpen, setIsReviewOpen] = useState(false);
  const [isResolved, setIsResolved] = useState(false);

  // Simulate progress
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
    if (!token || !user) {
      router.push("/auth/login?error=Please login to process documents");
      return;
    }

    if (!file) return;
    setIsUploading(true);
    setError(null);
    setResult(null);
    setIsResolved(false);

    const formData = new FormData();
    formData.append("file", file);
    formData.append("tenant_id", user.id);
    formData.append("doc_type", docType);

    try {
      const response = await axios.post("http://localhost:8000/api/v1/extract", formData, {
        headers: { Authorization: `Bearer ${token}` }
      });
      setProgress(100);
      setTimeout(() => {
        setResult(response.data);
        setIsUploading(false);
      }, 500);
    } catch (err: any) {
      setError("Server Error. Make sure backend is running on port 8000.");
      setIsUploading(false);
    }
  };

  const handlePortalUpload = async () => {
    if (!token) return;
    if (!portalFile) return;
    setIsPortalUploading(true);
    const formData = new FormData();
    formData.append("file", portalFile);

    try {
      await axios.post("http://localhost:8000/api/v1/reconcile/upload-portal", formData, {
        headers: { Authorization: `Bearer ${token}` }
      });
      setPortalFile(null);
      alert("Successfully uploaded Government Portal data!");
    } catch (err: any) {
      setError("Failed to upload portal data.");
    } finally {
      setIsPortalUploading(false);
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
    const hideKeys = ["raw_text", "char_count", "recon_results", "portal_data"];
    return Object.entries(data).filter(([key]) => !hideKeys.includes(key));
  };

  const renderValue = (value: any): React.ReactNode => {
    if (value === null || value === undefined) return <span style={{ opacity: 0.3 }}>null</span>;
    if (Array.isArray(value) && value.length > 0 && typeof value[0] === "object") {
      const cols = Object.keys(value[0]);
      return (
        <div className="extraction-table-container" style={{ margin: "0.5rem 0", background: "rgba(0,0,0,0.2)" }}>
          <table className="extraction-table" style={{ fontSize: "0.75rem" }}>
            <thead><tr>{cols.map(c => <th key={c}>{c.replace(/_/g, " ")}</th>)}</tr></thead>
            <tbody>{value.map((item, i) => <tr key={i}>{cols.map(c => <td key={c}>{renderValue(item[c])}</td>)}</tr>)}</tbody>
          </table>
        </div>
      );
    }
    if (typeof value === "object" && !Array.isArray(value)) {
      return (
        <div className="extraction-table-container" style={{ margin: "0.5rem 0", background: "rgba(0,0,0,0.1)", border: "1px solid rgba(255,255,255,0.05)" }}>
          <table className="extraction-table" style={{ fontSize: "0.75rem" }}>
            <tbody>{Object.entries(value).map(([k, v]) => <tr key={k}><td style={{ fontWeight: 700, width: "30%" }}>{k.replace(/_/g, " ")}</td><td>{renderValue(v)}</td></tr>)}</tbody>
          </table>
        </div>
      );
    }
    return String(value);
  };

  const downloadExcel = () => {
    if (!result) return;
    const ws = XLSX.utils.json_to_sheet(getFilteredData());
    const wb = XLSX.utils.book_new();
    XLSX.utils.book_append_sheet(wb, ws, "Results");
    XLSX.writeFile(wb, `${result.filename}_extraction.xlsx`);
  };

  const reconData = result?.extracted_data?.recon_results;

  return (
    <div className="uploader-container">
      <AnimatePresence mode="wait">
        {!result ? (
          <motion.div key="upload" initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, scale: 0.95 }}>
            
            <div style={{ display: "flex", justifyContent: "space-between", marginBottom: "1.5rem", gap: "1rem", alignItems: "center" }}>
              <div style={{ display: "flex", gap: "1rem", alignItems: "center" }}>
                <span style={{ fontSize: "0.8rem", fontWeight: 700, color: "var(--muted)", textTransform: "uppercase" }}>Select Mode:</span>
                <div style={{ position: "relative" }}>
                  <select 
                    value={docType} 
                    onChange={(e) => setDocType(e.target.value)}
                    style={{ 
                      appearance: "none", padding: "0.5rem 2.5rem 0.5rem 1rem", 
                      background: "var(--glass)", border: "1px solid var(--glass-border)",
                      borderRadius: "0.75rem", color: "#fff", fontWeight: 600, outline: "none", cursor: "pointer"
                    }}
                  >
                    <option value="unknown">Auto-Detect</option>
                    <option value="invoice">Invoice</option>
                    <option value="bank_statement">Bank Statement</option>
                    <option value="reconciliation">GSTR-2A Reconciliation</option>
                  </select>
                  <ChevronDown size={14} style={{ position: "absolute", right: "1rem", top: "50%", transform: "translateY(-50%)", pointerEvents: "none", opacity: 0.5 }} />
                </div>
              </div>

              {docType === "reconciliation" && user && (
                <div style={{ display: "flex", gap: "0.5rem", alignItems: "center" }}>
                  <input type="file" id="portalInput" hidden accept=".xlsx,.xls" onChange={(e) => e.target.files && setPortalFile(e.target.files[0])} />
                  <button 
                    className="btn btn-secondary" 
                    style={{ padding: "0.5rem 1rem", fontSize: "0.8rem" }}
                    onClick={() => portalFile ? handlePortalUpload() : document.getElementById("portalInput")?.click()}
                    disabled={isPortalUploading}
                  >
                    {isPortalUploading ? <Loader2 size={14} className="animate-spin" /> : <Database size={14} />}
                    {portalFile ? `Upload ${portalFile.name}` : "Sync Portal Excel"}
                  </button>
                </div>
              )}
            </div>

            <div className="dropzone glass glass-hover" onClick={() => !isUploading && document.getElementById("fileInput")?.click()} style={{ cursor: isUploading ? "default" : "pointer" }}>
              <input type="file" id="fileInput" hidden accept=".pdf" onChange={onFileChange} disabled={isUploading} />
              <div className="dropzone-icon">{isUploading ? <Loader2 className="animate-spin" size={64} /> : <Upload size={64} />}</div>

              {isUploading ? (
                <div className="progress-container">
                  <h3 style={{ marginBottom: "1rem" }}>Processing...</h3>
                  <div className="progress-track"><motion.div className="progress-bar" animate={{ width: `${progress}%` }} transition={{ type: "spring", stiffness: 50 }} /></div>
                  <p style={{ color: "rgba(255,255,255,0.5)", fontSize: "0.875rem" }}>{progress < 40 ? "Extracting..." : progress < 80 ? "Analyzing..." : "Finalizing..."}</p>
                </div>
              ) : (
                <div style={{ textAlign: "center" }}>
                  <h3 style={{ marginBottom: "0.5rem" }}>{file ? file.name : "Upload Document"}</h3>
                  <p style={{ color: "rgba(255,255,255,0.5)" }}>{file ? `${(file.size / 1024 / 1024).toFixed(2)} MB • PDF` : "Drag and drop or click to browse"}</p>
                </div>
              )}

              {file && !isUploading && (
                <motion.button 
                  initial={{ opacity: 0, y: 10 }} 
                  animate={{ opacity: 1, y: 0 }} 
                  className={`btn ${user ? 'btn-primary' : 'btn-secondary'}`}
                  style={{ marginTop: "2rem" }} 
                  onClick={(e) => { e.stopPropagation(); handleUpload(); }}
                >
                  {!user && <LogIn size={18} />}
                  {user ? "Analyze Now" : "Sign In to Analyze"} 
                  <ArrowRight size={18} />
                </motion.button>
              )}
            </div>
          </motion.div>
        ) : (
          <motion.div key="result" initial={{ opacity: 0, scale: 0.9 }} animate={{ opacity: 1, scale: 1 }} className="result-card glass">
            
            <div className="result-header">
              <div>
                <div style={{ display: "flex", alignItems: "center", gap: "1rem", marginBottom: "0.5rem" }}>
                  <h2 className="text-gradient" style={{ fontSize: "2rem" }}>Result</h2>
                  <span className={`status-badge ${isResolved || result.status === "completed" ? "status-completed" : "status-review"}`}>{isResolved ? "resolved" : result.status.replace("_", " ")}</span>
                </div>
                <p style={{ color: "rgba(255,255,255,0.5)" }}>{result.filename}</p>
              </div>
              <div className="confidence-ring">
                <div style={{ fontSize: "1.5rem", fontWeight: 800 }}>{( (isResolved ? 1.0 : result.confidence) * 100).toFixed(0)}%</div>
              </div>
            </div>

            {reconData && (
              <div style={{ padding: "1.5rem", borderRadius: "1rem", marginBottom: "2rem", border: "1px solid var(--primary)", background: "rgba(99, 102, 241, 0.05)" }}>
                <h3 style={{ fontWeight: 700, marginBottom: "1rem" }}>Portal Reconciliation</h3>
                <div style={{ display: "flex", gap: "2rem" }}>
                  <div style={{ flex: 1 }}>
                    <div style={{ fontSize: "0.7rem", opacity: 0.5 }}>STATUS</div>
                    <div style={{ fontWeight: 800, color: reconData.is_matched ? "var(--success)" : "var(--warning)" }}>{reconData.status}</div>
                  </div>
                  <div style={{ flex: 1 }}>
                    <div style={{ fontSize: "0.7rem", opacity: 0.5 }}>DIFFERENCE</div>
                    <div style={{ fontWeight: 800 }}>₹{reconData.diff.toLocaleString()}</div>
                  </div>
                </div>
              </div>
            )}

            <div className="extraction-table-container">
              <table className="extraction-table">
                <thead><tr><th>Field</th><th>Value</th></tr></thead>
                <tbody>{getFilteredData().map(([k, v]) => <tr key={k}><td className="field-name-cell">{k.replace(/_/g, " ")}</td><td className="field-value-cell">{renderValue(v)}</td></tr>)}</tbody>
              </table>
            </div>

            <div style={{ marginTop: "3rem", display: "flex", gap: "1rem" }}>
              <button className="btn btn-secondary" onClick={downloadExcel}><Download size={18} /> Excel</button>
              <button className="btn btn-secondary" onClick={reset}><Trash2 size={18} /> New</button>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
};
