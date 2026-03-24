"use client";

import React, { useState, useEffect, useRef } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { 
  Upload,
  Loader2, ArrowRight,
  Trash2, Download, ChevronDown,
  Database, LogIn, CheckCircle, ShieldCheck
} from "lucide-react";
import axios from "axios";
import * as XLSX from "xlsx";
import { ReviewModal } from "./ReviewModal";
import { useAuth } from "./AuthContext";
import { useRouter } from "next/navigation";
import { apiUrl } from "@/lib/api";

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
  result?: ExtractionResult | ExtractionResult[];
}

interface ReconciliationResult {
  is_matched: boolean;
  status: string;
  diff: number;
}

interface BankStatementSummary {
  transaction_count?: number;
  categorized_transactions?: number;
  uncategorized_transactions?: number;
  category_coverage?: number;
  total_inflow?: number;
  total_outflow?: number;
  total_transfers?: number;
  total_unknown?: number;
  category_totals?: Record<string, number>;
  top_counterparties?: Array<{ name?: string; count?: number }>;
  duplicate_candidates?: number;
  high_value_transactions?: number;
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
  const [runInBackground, setRunInBackground] = useState(true);
  const [isUploading, setIsUploading] = useState(false);
  const [isPortalUploading, setIsPortalUploading] = useState(false);
  const [progress, setProgress] = useState(0);
  const [results, setResults] = useState<ExtractionResult[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [isReviewOpen, setIsReviewOpen] = useState(false);
  const [resolvedRequestIds, setResolvedRequestIds] = useState<string[]>([]);
  const [reviewTarget, setReviewTarget] = useState<ExtractionResult | null>(null);
  const [activeRequestId, setActiveRequestId] = useState<string | null>(null);
  const cancelRequestedRef = useRef(false);
  const clampProgress = (value: number) => Math.min(100, Math.max(0, value));
  const progressPercent = Math.round(clampProgress(progress));

  // Simulate progress
  useEffect(() => {
    let interval: NodeJS.Timeout;
    if (isUploading) {
      setProgress(0);
      interval = setInterval(() => {
        setProgress((prev) => {
          if (prev >= 95) return prev;
          return clampProgress(prev + Math.random() * 15);
        });
      }, 500);
    }
    return () => clearInterval(interval);
  }, [isUploading]);

  const onFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      setFile(e.target.files[0]);
      setError(null);
      setNotice(null);
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
    setNotice(null);
    cancelRequestedRef.current = false;
    setResults([]);
    setResolvedRequestIds([]);

    const formData = new FormData();
    formData.append("file", file);
    formData.append("tenant_id", user.id);
    formData.append("doc_type", docType);
    formData.append("async_mode", String(runInBackground));

    try {
      const response = await axios.post(apiUrl("/api/v1/extract"), formData, {
        headers: { Authorization: `Bearer ${token}` }
      });
      if (response.data?.status === "queued") {
        setActiveRequestId(response.data.request_id);
        await pollJobStatus(response.data.request_id);
      } else {
        setProgress(100);
        setTimeout(() => {
          setResults(Array.isArray(response.data) ? response.data : [response.data]);
          setIsUploading(false);
          setActiveRequestId(null);
        }, 500);
      }
    } catch (err: unknown) {
      const apiErr = err as ApiError;
      setError(apiErr.response?.data?.detail || "Server Error. Make sure backend is running on port 8000.");
      setIsUploading(false);
      setActiveRequestId(null);
    }
  };

  const pollJobStatus = async (requestId: string) => {
    if (!token) return;
    const startedAt = Date.now();
    while (Date.now() - startedAt < 15 * 60 * 1000 && !cancelRequestedRef.current) {
      const statusRes = await axios.get(apiUrl(`/api/v1/extract/${requestId}/status`), {
        headers: { Authorization: `Bearer ${token}` }
      });
      const payload = statusRes.data;
      if (payload?.status === "completed" && payload?.result) {
        const resultPayload = Array.isArray(payload.result) ? payload.result : [payload.result];
        setProgress(100);
        setResults(resultPayload);
        setIsUploading(false);
        setActiveRequestId(null);
        return;
      }
      if (payload?.status === "completed" || payload?.status === "needs_review") {
        setProgress(100);
        setResults([payload]);
        setIsUploading(false);
        setActiveRequestId(null);
        return;
      }
      if (payload?.status === "failed") {
        setError(payload?.error || "Background processing failed.");
        setIsUploading(false);
        setActiveRequestId(null);
        return;
      }
      if (payload?.status === "cancelled") {
        setNotice("Processing cancelled.");
        setIsUploading(false);
        setProgress(0);
        setActiveRequestId(null);
        return;
      }
      if (payload?.status === "queued" || payload?.status === "processing") {
        setProgress((prev) => (prev < 92 ? prev + 8 : prev));
      }
      await new Promise((resolve) => setTimeout(resolve, 1800));
    }
    if (cancelRequestedRef.current) {
      return;
    }
    setError("Background processing timed out. Please check history later.");
    setIsUploading(false);
    setActiveRequestId(null);
  };

  const cancelUpload = async () => {
    if (!token || !activeRequestId) return;
    cancelRequestedRef.current = true;
    try {
      await axios.post(apiUrl(`/api/v1/extract/${activeRequestId}/cancel`), {}, {
        headers: { Authorization: `Bearer ${token}` }
      });
      setNotice("Processing cancelled.");
      setIsUploading(false);
      setProgress(0);
      setActiveRequestId(null);
    } catch (err: unknown) {
      const apiErr = err as ApiError;
      setError(apiErr.response?.data?.detail || "Failed to cancel processing.");
    }
  };

  const handlePortalUpload = async () => {
    if (!token) return;
    if (!portalFile) return;
    setIsPortalUploading(true);
    const formData = new FormData();
    formData.append("file", portalFile);

    try {
      await axios.post(apiUrl("/api/v1/reconcile/upload-portal"), formData, {
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
    setResults([]);
    setError(null);
    setNotice(null);
    cancelRequestedRef.current = false;
    setProgress(0);
    setIsReviewOpen(false);
    setResolvedRequestIds([]);
    setReviewTarget(null);
    setActiveRequestId(null);
  };

  const getFilteredData = (resultItem: ExtractionResult) => {
    const data = resultItem?.extracted_data || resultItem?.partial_data || {};
    const hideKeys = ["raw_text", "char_count", "recon_results", "portal_data", "category_totals", "statement_summary", "transactions"];
    return Object.entries(data).filter(([key]) => !hideKeys.includes(key));
  };

  const formatFileSize = (sizeInBytes: number | undefined) => {
    if (!sizeInBytes || sizeInBytes < 0) return "0 KB";
    if (sizeInBytes < 1024) return `${sizeInBytes} B`;
    if (sizeInBytes < 1024 * 1024) return `${(sizeInBytes / 1024).toFixed(2)} KB`;
    return `${(sizeInBytes / (1024 * 1024)).toFixed(2)} MB`;
  };

  const isInvoiceDocType = (docType: string | undefined) => {
    return String(docType || "").replace("DocType.", "").toLowerCase() === "invoice";
  };

  const renderValue = (value: unknown, options?: { preserveTableLayout?: boolean }): React.ReactNode => {
    if (value === null || value === undefined) return <span style={{ opacity: 0.3 }}>null</span>;
    if (Array.isArray(value) && value.length > 0 && typeof value[0] === "object") {
      const firstRow = value[0] as Record<string, unknown>;
      const cols = Object.keys(firstRow);
      const preserveTableLayout = options?.preserveTableLayout === true;
      return (
        <div
          className={`extraction-table-container ${preserveTableLayout ? "transaction-table-container" : ""}`}
          style={{ margin: "0.5rem 0", background: "rgba(0,0,0,0.2)" }}
        >
          <table
            className={`extraction-table ${preserveTableLayout ? "transaction-table" : ""}`}
            style={{ fontSize: "0.75rem" }}
          >
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

  const formatCurrency = (value: unknown) => {
    const amount = typeof value === "number" ? value : Number(value || 0);
    return `₹${amount.toLocaleString("en-IN", { maximumFractionDigits: 2 })}`;
  };

  const renderKeyValueTable = (data: Record<string, unknown>) => (
    <div className="extraction-table-container" style={{ margin: "0.5rem 0", background: "rgba(0,0,0,0.12)" }}>
      <table className="extraction-table" style={{ fontSize: "0.75rem" }}>
        <tbody>
          {Object.entries(data).map(([key, value]) => (
            <tr key={key}>
              <td style={{ fontWeight: 700, width: "45%" }}>{key.replace(/_/g, " ")}</td>
              <td>{typeof value === "number" ? formatCurrency(value) : renderValue(value)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );

  const renderStatementSummary = (summary: BankStatementSummary) => (
    <div style={{ display: "grid", gap: "1rem" }}>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))", gap: "0.75rem" }}>
        {[
          ["Transaction Count", summary.transaction_count ?? 0],
          ["Categorized", summary.categorized_transactions ?? 0],
          ["Uncategorized", summary.uncategorized_transactions ?? 0],
          ["Coverage", `${Math.round((summary.category_coverage ?? 0) * 100)}%`],
          ["Total Inflow", formatCurrency(summary.total_inflow ?? 0)],
          ["Total Outflow", formatCurrency(summary.total_outflow ?? 0)],
          ["Transfers", formatCurrency(summary.total_transfers ?? 0)],
          ["Unknown", formatCurrency(summary.total_unknown ?? 0)],
          ["Duplicate Candidates", summary.duplicate_candidates ?? 0],
          ["High Value Transactions", summary.high_value_transactions ?? 0],
        ].map(([label, value]) => (
          <div key={label} style={{ padding: "0.75rem", borderRadius: "0.85rem", background: "rgba(255,255,255,0.04)", border: "1px solid rgba(255,255,255,0.06)" }}>
            <div style={{ fontSize: "0.72rem", opacity: 0.6, marginBottom: "0.25rem", textTransform: "uppercase" }}>{label}</div>
            <div style={{ fontWeight: 700 }}>{String(value)}</div>
          </div>
        ))}
      </div>

      {!!summary.category_totals && Object.keys(summary.category_totals).length > 0 && (
        <div>
          <div style={{ fontSize: "0.78rem", fontWeight: 700, marginBottom: "0.45rem" }}>Category Totals</div>
          {renderKeyValueTable(summary.category_totals)}
        </div>
      )}

      {!!summary.top_counterparties?.length && (
        <div>
          <div style={{ fontSize: "0.78rem", fontWeight: 700, marginBottom: "0.45rem" }}>Top Counterparties</div>
          <div className="extraction-table-container" style={{ background: "rgba(0,0,0,0.12)" }}>
            <table className="extraction-table" style={{ fontSize: "0.75rem" }}>
              <thead><tr><th>Name</th><th>Count</th></tr></thead>
              <tbody>
                {summary.top_counterparties.map((item, index) => (
                  <tr key={`${item.name || "counterparty"}-${index}`}>
                    <td>{item.name || "Unknown"}</td>
                    <td>{item.count ?? 0}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );

  const renderFieldValue = (field: string, value: unknown): React.ReactNode => {
    if (field === "transactions" && Array.isArray(value)) {
      return renderValue(value, { preserveTableLayout: true });
    }
    if (field === "statement_summary" && value && typeof value === "object" && !Array.isArray(value)) {
      return renderStatementSummary(value as BankStatementSummary);
    }
    if (field === "category_totals" && value && typeof value === "object" && !Array.isArray(value)) {
      return renderKeyValueTable(value as Record<string, unknown>);
    }
    return renderValue(value);
  };

  const downloadExcel = (resultItem: ExtractionResult) => {
    if (!resultItem) return;
    const wb = XLSX.utils.book_new();
    const hideKeys = ["raw_text", "char_count", "recon_results", "portal_data"];
    const filteredEntries = Object.entries(resultItem.extracted_data || {}).filter(([key]) => !hideKeys.includes(key));

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
        if (value.length > 0 && typeof value[0] === "object" && value[0] !== null) {
          const rows = value as Record<string, unknown>[];
          const keys = Array.from(new Set(rows.flatMap((row) => Object.keys(row))));
          for (let i = 0; i < rows.length; i += 1) {
            const row = rows[i];
            const overviewRow: Record<string, string | number | boolean> = {
              Field: field,
              Entry: i + 1,
            };
            for (const key of keys) {
              overviewRow[key] = toDisplayValue(row[key]);
            }
            overviewRows.push(overviewRow);
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

    XLSX.writeFile(wb, `${resultItem.filename}_extraction.xlsx`);
  };

  const downloadERPExport = async (resultItem: ExtractionResult, format: "tally_xml" | "zoho_csv" | "quickbooks_csv") => {
    if (!token || !resultItem.request_id) return;
    try {
      const response = await axios.get(apiUrl(`/api/v1/export/${resultItem.request_id}?export_format=${format}`), {
        headers: { Authorization: `Bearer ${token}` },
        responseType: "blob",
      });
      const blob = new Blob([response.data], { type: response.headers["content-type"] || "application/octet-stream" });
      const downloadUrl = URL.createObjectURL(blob);
      const anchor = document.createElement("a");
      const extension = format === "tally_xml" ? "xml" : "csv";
      anchor.href = downloadUrl;
      anchor.download = `${resultItem.filename.replace(/\.pdf$/i, "")}_${format}.${extension}`;
      document.body.appendChild(anchor);
      anchor.click();
      anchor.remove();
      URL.revokeObjectURL(downloadUrl);
    } catch (err: unknown) {
      const apiErr = err as ApiError;
      setError(apiErr.response?.data?.detail || "Failed to generate export file.");
    }
  };

  return (
    <div className="uploader-container">
      <AnimatePresence mode="wait">
        {results.length === 0 ? (
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
                <label style={{ display: "flex", alignItems: "center", gap: "0.45rem", fontSize: "0.82rem", color: "rgba(255,255,255,0.75)" }}>
                  <input
                    type="checkbox"
                    checked={runInBackground}
                    onChange={(e) => setRunInBackground(e.target.checked)}
                  />
                  Background processing
                </label>
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
                  <div style={{ display: "flex", alignItems: "center", justifyContent: "center", marginBottom: "1rem" }}>
                    <h3>Processing...</h3>
                  </div>
                  <div className="progress-track"><motion.div className="progress-bar" animate={{ width: `${progressPercent}%` }} transition={{ type: "spring", stiffness: 50 }} /></div>
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "0.4rem" }}>
                    <p style={{ color: "rgba(255,255,255,0.5)", fontSize: "0.875rem" }}>{progressPercent < 40 ? "Extracting..." : progressPercent < 80 ? "Analyzing..." : "Finalizing..."}</p>
                    <p style={{ color: "#fff", fontSize: "0.85rem", fontWeight: 700 }}>{progressPercent}%</p>
                  </div>
                  {file && (
                    <p style={{ color: "rgba(255,255,255,0.38)", fontSize: "0.78rem" }}>
                      {file.name} • {formatFileSize(file.size)}
                    </p>
                  )}
                  {runInBackground && (
                    <div style={{ display: "flex", justifyContent: "center", marginTop: "1rem" }}>
                      <button
                        className="btn btn-secondary"
                        type="button"
                        onClick={cancelUpload}
                        disabled={!activeRequestId}
                      >
                        {activeRequestId ? "Cancel Processing" : "Preparing Cancellation..."}
                      </button>
                    </div>
                  )}
                </div>
              ) : (
                <div style={{ textAlign: "center" }}>
                  <h3 style={{ marginBottom: "0.5rem" }}>{file ? file.name : "Upload Document"}</h3>
                  <p style={{ color: "rgba(255,255,255,0.5)" }}>{file ? `${formatFileSize(file.size)} • PDF` : "Drag and drop or click to browse"}</p>
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
            {error && (
              <div style={{ marginTop: "1rem", padding: "0.9rem 1rem", borderRadius: "0.85rem", border: "1px solid rgba(239,68,68,0.35)", background: "rgba(239,68,68,0.12)", color: "#fca5a5" }}>
                {error}
              </div>
            )}
            {notice && (
              <div style={{ marginTop: "1rem", padding: "0.9rem 1rem", borderRadius: "0.85rem", border: "1px solid rgba(129,140,248,0.35)", background: "rgba(99,102,241,0.12)", color: "#c7d2fe" }}>
                {notice}
              </div>
            )}
          </motion.div>
        ) : (
          <motion.div key="resultsDisplay" initial={{ opacity: 0, scale: 0.9 }} animate={{ opacity: 1, scale: 1 }} className="flex flex-col gap-8">
            {results.map((resultItem, index) => {
              const itemRawReconData = resultItem?.extracted_data?.recon_results;
              const itemReconData = (
                itemRawReconData &&
                typeof itemRawReconData === "object" &&
                "is_matched" in itemRawReconData &&
                "status" in itemRawReconData &&
                "diff" in itemRawReconData
              ) ? (itemRawReconData as ReconciliationResult) : null;
              const itemResolved = resolvedRequestIds.includes(resultItem.request_id);
              const itemConfidencePercent = (itemResolved ? 1.0 : resultItem?.confidence || 0) * 100;
              const itemConfidenceRingStyle = { "--confidence": itemConfidencePercent } as React.CSSProperties;
              const statementSummary = (
                resultItem?.extracted_data?.statement_summary &&
                typeof resultItem.extracted_data.statement_summary === "object" &&
                !Array.isArray(resultItem.extracted_data.statement_summary)
              ) ? (resultItem.extracted_data.statement_summary as BankStatementSummary) : null;
              const transactions = Array.isArray(resultItem?.extracted_data?.transactions)
                ? (resultItem.extracted_data.transactions as unknown[])
                : null;

              return (
                <motion.div key={resultItem.request_id || index} className="result-card glass">
                  <div className="result-header">
                    <div>
                      <div style={{ display: "flex", alignItems: "center", gap: "1rem", marginBottom: "0.5rem" }}>
                        <h2 className="text-gradient" style={{ fontSize: "2rem" }}>Result {results.length > 1 ? `#${index + 1}` : ''}</h2>
                        <span className={`status-badge ${itemResolved || resultItem.status === "completed" ? "status-completed" : "status-review"}`}>{itemResolved ? "resolved" : resultItem.status.replace("_", " ")}</span>
                        {!!resultItem.extracted_data?.qr_data && (
                          <span className="status-badge" style={{ background: "rgba(34, 197, 94, 0.2)", color: "#4ade80", border: "1px solid rgba(74, 222, 128, 0.3)" }}>
                            <CheckCircle size={14} style={{ display: "inline", marginRight: "0.25rem", verticalAlign: "text-bottom" }}/>
                            QR Verified
                          </span>
                        )}
                         {resultItem.compliance_flags?.some(f => f.includes("TAMPER_ALERT")) && (
                          <span className="status-badge" style={{ background: "rgba(239, 68, 68, 0.2)", color: "#ef4444", border: "1px solid rgba(239, 68, 68, 0.3)" }}>
                            <ShieldCheck size={14} style={{ display: "inline", marginRight: "0.25rem", verticalAlign: "text-bottom" }}/>
                            TAMPER ALERT
                          </span>
                        )}
                      </div>
                      <p style={{ color: "rgba(255,255,255,0.5)" }}>{resultItem.filename}</p>
                    </div>
                    <div
                      className="confidence-ring"
                      style={itemConfidenceRingStyle}
                    >
                      <div style={{ fontSize: "1.5rem", fontWeight: 800 }}>{itemConfidencePercent.toFixed(0)}%</div>
                    </div>
                  </div>

                  {/* If tampering detected, show massive red warning */}
                  {resultItem.compliance_flags?.some(f => f.includes("TAMPER_ALERT")) && (
                    <div style={{ padding: "1.5rem", borderRadius: "1rem", marginBottom: "2rem", border: "1px solid #ef4444", background: "rgba(239, 68, 68, 0.1)" }}>
                      <div style={{ display: "flex", alignItems: "center", gap: "1rem" }}>
                        <ShieldCheck size={32} color="#ef4444" />
                        <div>
                          <h3 style={{ color: "#ef4444", fontWeight: 800, margin: 0, marginBottom: "0.25rem" }}>TAMPER ALERT: DIGITAL INTEGRITY FAILED</h3>
                          <p style={{ margin: 0, fontSize: "0.875rem", opacity: 0.8 }}>
                            The government QR code data does not match the printed text on this invoice. This document may be fraudulent.
                          </p>
                        </div>
                      </div>
                    </div>
                  )}

                  {itemReconData && (
                    <div style={{ padding: "1.5rem", borderRadius: "1rem", marginBottom: "2rem", border: "1px solid var(--primary)", background: "rgba(99, 102, 241, 0.05)" }}>
                      <h3 style={{ fontWeight: 700, marginBottom: "1rem" }}>Portal Reconciliation</h3>
                      <div style={{ display: "flex", gap: "2rem" }}>
                        <div style={{ flex: 1 }}>
                          <div style={{ fontSize: "0.7rem", opacity: 0.5 }}>STATUS</div>
                          <div style={{ fontWeight: 800, color: itemReconData.is_matched ? "var(--success)" : "var(--warning)" }}>{itemReconData.status}</div>
                        </div>
                        <div style={{ flex: 1 }}>
                          <div style={{ fontSize: "0.7rem", opacity: 0.5 }}>DIFFERENCE</div>
                          <div style={{ fontWeight: 800 }}>₹{itemReconData.diff.toLocaleString()}</div>
                        </div>
                      </div>
                    </div>
                  )}

                  {statementSummary && (
                    <div style={{ padding: "1.25rem", borderRadius: "1rem", marginBottom: "1.5rem", border: "1px solid rgba(99, 102, 241, 0.18)", background: "rgba(99, 102, 241, 0.05)" }}>
                      <h3 style={{ fontWeight: 700, marginBottom: "0.9rem" }}>Statement Summary</h3>
                      {renderStatementSummary(statementSummary)}
                    </div>
                  )}

                  {transactions && transactions.length > 0 && (
                    <div style={{ padding: "1.25rem", borderRadius: "1rem", marginBottom: "1.5rem", border: "1px solid rgba(255, 255, 255, 0.08)", background: "rgba(255,255,255,0.03)" }}>
                      <h3 style={{ fontWeight: 700, marginBottom: "0.9rem" }}>Transactions</h3>
                      {renderValue(transactions, { preserveTableLayout: true })}
                    </div>
                  )}

                  <div className="extraction-table-container">
                    <table className="extraction-table">
                      <thead><tr><th>Field</th><th>Value</th></tr></thead>
                      <tbody>{getFilteredData(resultItem).map(([k, v]) => <tr key={k}><td className="field-name-cell">{k.replace(/_/g, " ")}</td><td className="field-value-cell">{renderFieldValue(k, v)}</td></tr>)}</tbody>
                    </table>
                  </div>

                  <div style={{ marginTop: "3rem", display: "flex", gap: "1rem" }}>
                    {resultItem.status === "needs_review" && !itemResolved && (
                      <button
                        className="btn btn-primary"
                        onClick={() => {
                          setReviewTarget(resultItem);
                          setIsReviewOpen(true);
                        }}
                      >
                        Manual Review
                      </button>
                    )}
                    <button className="btn btn-secondary" onClick={() => downloadExcel(resultItem)}><Download size={18} /> Excel</button>
                    {isInvoiceDocType(resultItem.doc_type) && (
                      <>
                        <button className="btn btn-secondary" onClick={() => downloadERPExport(resultItem, "tally_xml")}><Download size={18} /> Tally XML</button>
                        <button className="btn btn-secondary" onClick={() => downloadERPExport(resultItem, "zoho_csv")}><Download size={18} /> Zoho CSV</button>
                        <button className="btn btn-secondary" onClick={() => downloadERPExport(resultItem, "quickbooks_csv")}><Download size={18} /> QuickBooks CSV</button>
                      </>
                    )}
                    <button className="btn btn-secondary" onClick={reset}><Trash2 size={18} /> New</button>
                  </div>
                </motion.div>
              );
            })}
          </motion.div>
        )}
      </AnimatePresence>

      {reviewTarget && (
        <ReviewModal
          isOpen={isReviewOpen}
          onClose={() => setIsReviewOpen(false)}
          data={(reviewTarget.partial_data || reviewTarget.extracted_data || {}) as Record<string, unknown>}
          requestId={reviewTarget.request_id}
          onResolved={() => {
            setResolvedRequestIds((current) => [...current, reviewTarget.request_id]);
            setIsReviewOpen(false);
            setReviewTarget(null);
          }}
        />
      )}
    </div>
  );
};
