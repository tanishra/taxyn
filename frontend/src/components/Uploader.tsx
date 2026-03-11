"use client";

import React, { useState, useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { 
  Upload,
  Loader2, ArrowRight,
  Trash2, Download, ChevronDown,
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
  extracted_data: Record<string, unknown>;
  confidence: number;
  compliance_flags: string[];
  processing_time_ms: number;
  message?: string;
  partial_data?: Record<string, unknown>;
}

interface ReconciliationResult {
  is_matched: boolean;
  status: string;
  diff: number;
}

interface ApiError {
  response?: {
    data?: {
      detail?: string;
    };
  };
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
    } catch (_err: unknown) {
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
    } catch (err: unknown) {
      const apiErr = err as ApiError;
      setError(apiErr.response?.data?.detail || "Failed to upload portal data.");
    } finally {
      setIsPortalUploading(false);
    }
  };

  const reset = () => {
    setFile(null);
    setResult(null);
    setError(null);
    setProgress(0);
    setIsReviewOpen(false);
    setIsResolved(false);
  };

  const getFilteredData = () => {
    const data = result?.extracted_data || result?.partial_data || {};
    const hideKeys = ["raw_text", "char_count", "recon_results", "portal_data"];
    return Object.entries(data).filter(([key]) => !hideKeys.includes(key));
  };

  const renderValue = (value: unknown): React.ReactNode => {
    if (value === null || value === undefined) return <span style={{ opacity: 0.3 }}>null</span>;
    if (Array.isArray(value) && value.length > 0 && typeof value[0] === "object") {
      const firstRow = value[0] as Record<string, unknown>;
      const cols = Object.keys(firstRow);
      return (
        <div className="extraction-table-container" style={{ margin: "0.5rem 0", background: "rgba(0,0,0,0.2)" }}>
          <table className="extraction-table" style={{ fontSize: "0.75rem" }}>
            <thead><tr>{cols.map(c => <th key={c}>{c.replace(/_/g, " ")}</th>)}</tr></thead>
            <tbody>{value.map((item, i) => <tr key={i}>{cols.map(c => <td key={c}>{renderValue((item as Record<string, unknown>)[c])}</td>)}</tr>)}</tbody>
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
    const wb = XLSX.utils.book_new();
    const hideKeys = ["raw_text", "char_count", "recon_results", "portal_data"];
    const filteredEntries = Object.entries(result.extracted_data || {}).filter(([key]) => !hideKeys.includes(key));

    const toDisplayValue = (value: unknown): string | number | boolean => {
      if (value === null || value === undefined) return "";
      if (typeof value === "string" || typeof value === "number" || typeof value === "boolean") return value;
      return JSON.stringify(value);
    };

    const safeSheetName = (name: string): string =>
      name.replace(/[\\/*?:[\]]/g, "_").slice(0, 31) || "Sheet";

    const overviewRows: Array<Record<string, string | number | boolean>> = [];
    for (const [field, value] of filteredEntries) {
      const sheetName = safeSheetName(field);
      if (Array.isArray(value)) {
        if (field === "transactions" && value.length > 0 && typeof value[0] === "object" && value[0] !== null) {
          for (const tx of value as Record<string, unknown>[]) {
            overviewRows.push({
              Field: "transactions",
              Value: "",
              Details: "",
              Date: toDisplayValue(tx.date),
              Description: toDisplayValue(tx.description),
              Debit: toDisplayValue(tx.debit),
              Credit: toDisplayValue(tx.credit),
              Balance: toDisplayValue(tx.balance),
            });
          }
          continue;
        }

        const rowCount = value.length;
        overviewRows.push({ Field: field, Value: `See sheet: ${sheetName}`, Details: `${rowCount} rows` });
        for (let i = 0; i < value.length; i += 1) {
          const rowValue = value[i];
          overviewRows.push({
            Field: `${field}[${i + 1}]`,
            Value: toDisplayValue(rowValue),
            Details: "",
          });
        }
        continue;
      }

      if (typeof value === "object" && value !== null) {
        const keyCount = Object.keys(value as Record<string, unknown>).length;
        overviewRows.push({ Field: field, Value: `See sheet: ${sheetName}`, Details: `${keyCount} fields` });
        for (const [k, v] of Object.entries(value as Record<string, unknown>)) {
          overviewRows.push({
            Field: `${field}.${k}`,
            Value: toDisplayValue(v),
            Details: "",
          });
        }
        continue;
      }

      overviewRows.push({ Field: field, Value: toDisplayValue(value), Details: "" });
    }
    const overviewWs = XLSX.utils.json_to_sheet(overviewRows);
    XLSX.utils.book_append_sheet(wb, overviewWs, "Overview");

    for (const [field, value] of filteredEntries) {
      const sheetName = safeSheetName(field);

      if (Array.isArray(value)) {
        if (value.length === 0) continue;
        if (typeof value[0] === "object" && value[0] !== null) {
          const normalizedRows = (value as Record<string, unknown>[]).map((row) => {
            const normalized: Record<string, string | number | boolean> = {};
            for (const [k, v] of Object.entries(row)) {
              normalized[k] = toDisplayValue(v);
            }
            return normalized;
          });
          const ws = XLSX.utils.json_to_sheet(normalizedRows);
          XLSX.utils.book_append_sheet(wb, ws, sheetName);
          continue;
        }

        const ws = XLSX.utils.json_to_sheet(
          (value as unknown[]).map((v) => ({ value: toDisplayValue(v) }))
        );
        XLSX.utils.book_append_sheet(wb, ws, sheetName);
        continue;
      }

      if (typeof value === "object" && value !== null) {
        const ws = XLSX.utils.json_to_sheet(
          Object.entries(value as Record<string, unknown>).map(([k, v]) => ({
            field: k,
            value: toDisplayValue(v),
          }))
        );
        XLSX.utils.book_append_sheet(wb, ws, sheetName);
      }
    }

    XLSX.writeFile(wb, `${result.filename}_extraction.xlsx`);
  };

  const rawReconData = result?.extracted_data?.recon_results;
  const reconData = (
    rawReconData &&
    typeof rawReconData === "object" &&
    "is_matched" in rawReconData &&
    "status" in rawReconData &&
    "diff" in rawReconData
  ) ? (rawReconData as ReconciliationResult) : null;
  const confidencePercent = (isResolved ? 1.0 : result?.confidence || 0) * 100;
  const confidenceRingStyle = { "--confidence": confidencePercent } as React.CSSProperties;

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
              <div
                className="confidence-ring"
                style={confidenceRingStyle}
              >
                <div style={{ fontSize: "1.5rem", fontWeight: 800 }}>{confidencePercent.toFixed(0)}%</div>
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
              {result.status === "needs_review" && !isResolved && (
                <button className="btn btn-primary" onClick={() => setIsReviewOpen(true)}>
                  Manual Review
                </button>
              )}
              <button className="btn btn-secondary" onClick={downloadExcel}><Download size={18} /> Excel</button>
              <button className="btn btn-secondary" onClick={reset}><Trash2 size={18} /> New</button>
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      {result && (
        <ReviewModal
          isOpen={isReviewOpen}
          onClose={() => setIsReviewOpen(false)}
          data={(result.partial_data || result.extracted_data || {}) as Record<string, unknown>}
          requestId={result.request_id}
          onResolved={() => {
            setIsResolved(true);
            setIsReviewOpen(false);
          }}
        />
      )}
    </div>
  );
};
