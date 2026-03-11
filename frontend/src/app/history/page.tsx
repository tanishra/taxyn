"use client";

import React, { useEffect, useState } from "react";
import { Navbar } from "@/components/Navbar";
import { motion } from "framer-motion";
import { FileText, Eye } from "lucide-react";
import { useAuth } from "@/components/AuthContext";
import axios from "axios";
import * as XLSX from "xlsx";

interface HistoryItem {
  request_id: string;
  filename: string;
  doc_type: string;
  created_at?: string;
  status: string;
  confidence?: number;
}

interface HistoryDetail {
  request_id: string;
  filename: string;
  doc_type: string;
  status: string;
  confidence: number;
  extracted_data: Record<string, unknown>;
  compliance_flags: string[];
}

interface RawHistoryItem {
  request_id?: string;
  filename?: string;
  doc_type?: string;
  created_at?: string;
  updated_at?: string;
  status?: string;
  confidence?: number;
  overall_confidence?: number;
}

export default function HistoryPage() {
  const { token, isLoading: authLoading } = useAuth();
  const [history, setHistory] = useState<HistoryItem[]>([]);
  const [selected, setSelected] = useState<HistoryDetail | null>(null);
  const [openingRequestId, setOpeningRequestId] = useState<string | null>(null);

  useEffect(() => {
    if (!token) return;
    let cancelled = false;

    const load = async () => {
      try {
        const res = await axios.get("http://localhost:8000/api/v1/auth/history", {
          headers: { Authorization: `Bearer ${token}` }
        });
        const rows: HistoryItem[] = (Array.isArray(res.data) ? res.data : []).map((row: RawHistoryItem) => ({
          request_id: row.request_id || "",
          filename: row.filename || "Untitled Document",
          doc_type: String(row.doc_type || "unknown").replace("DocType.", "").toLowerCase(),
          created_at: row.created_at || row.updated_at,
          status: row.status || "completed",
          confidence: row.confidence ?? row.overall_confidence ?? 0,
        }));
        if (!cancelled) setHistory(rows);
      } catch (_err) {
        console.error("Failed to fetch history");
      }
    };

    void load();
    return () => { cancelled = true; };
  }, [token]);

  const handleView = async (item: HistoryItem) => {
    if (!token || !item.request_id) return;
    setOpeningRequestId(item.request_id);
    try {
      const res = await axios.get(`http://localhost:8000/api/v1/auth/history/${item.request_id}`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      const payload = res.data || {};
      setSelected({
        request_id: payload.request_id || item.request_id,
        filename: payload.filename || item.filename,
        doc_type: payload.doc_type || item.doc_type,
        status: payload.status || item.status,
        confidence: payload.confidence ?? item.confidence ?? 0,
        extracted_data: payload.extracted_data || {},
        compliance_flags: Array.isArray(payload.compliance_flags) ? payload.compliance_flags : [],
      });
    } catch (_err) {
      console.error("Failed to load history details");
    } finally {
      setOpeningRequestId(null);
    }
  };

  const downloadHistoryExcel = () => {
    if (!selected) return;
    const hideKeys = ["raw_text", "char_count", "recon_results", "portal_data"];
    const wb = XLSX.utils.book_new();
    const filteredEntries = Object.entries(selected.extracted_data || {}).filter(([key]) => !hideKeys.includes(key));

    const toDisplayValue = (value: unknown): string | number | boolean => {
      if (value === null || value === undefined) return "";
      if (typeof value === "string" || typeof value === "number" || typeof value === "boolean") return value;
      return JSON.stringify(value);
    };

    const safeSheetName = (name: string): string =>
      name.replace(/[\\/*?:[\]]/g, "_").slice(0, 31) || "Sheet";

    // Overview sheet: quick summary for all fields
    const overviewRows: Array<Record<string, string | number | boolean>> = [];
    for (const [field, value] of filteredEntries) {
      const sheetName = safeSheetName(field);
      if (Array.isArray(value)) {
        // Render transactions as one clean row per transaction in overview.
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

        // For non-transaction arrays, keep compact readability in overview.
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

    // Complex fields get dedicated sheets for better readability
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

    XLSX.writeFile(wb, `${selected.filename || selected.request_id}_history.xlsx`);
  };

  const renderHistoryValue = (value: unknown): React.ReactNode => {
    if (value === null || value === undefined) {
      return <span style={{ opacity: 0.3 }}>null</span>;
    }

    if (Array.isArray(value) && value.length > 0 && typeof value[0] === "object") {
      const firstRow = value[0] as Record<string, unknown>;
      const cols = Object.keys(firstRow);
      return (
        <div className="extraction-table-container" style={{ margin: "0.5rem 0", background: "rgba(0,0,0,0.2)" }}>
          <table className="extraction-table" style={{ fontSize: "0.75rem" }}>
            <thead><tr>{cols.map((c) => <th key={c}>{c.replace(/_/g, " ")}</th>)}</tr></thead>
            <tbody>
              {value.map((item, i) => (
                <tr key={i}>
                  {cols.map((c) => <td key={c}>{renderHistoryValue((item as Record<string, unknown>)[c])}</td>)}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      );
    }

    if (typeof value === "object" && !Array.isArray(value)) {
      return (
        <div className="extraction-table-container" style={{ margin: "0.5rem 0", background: "rgba(0,0,0,0.1)", border: "1px solid rgba(255,255,255,0.05)" }}>
          <table className="extraction-table" style={{ fontSize: "0.75rem" }}>
            <tbody>
              {Object.entries(value).map(([k, v]) => (
                <tr key={k}>
                  <td style={{ fontWeight: 700, width: "30%" }}>{k.replace(/_/g, " ")}</td>
                  <td>{renderHistoryValue(v)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      );
    }

    return String(value);
  };

  if (authLoading) return null;

  return (
    <main>
      <Navbar />
      <div className="hero" style={{ justifyContent: "flex-start", paddingTop: "10rem" }}>
        <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} className="uploader-container" style={{ maxWidth: "1000px" }}>
          <div style={{ marginBottom: "2rem" }}>
            <h2 style={{ fontSize: "2rem", fontWeight: 800 }}>Audit History</h2>
            <p style={{ color: "var(--muted)" }}>View and re-download your past extraction results</p>
          </div>

          <div className="extraction-table-container">
            <table className="extraction-table">
              <thead>
                <tr>
                  <th>Document</th>
                  <th>Type</th>
                  <th>Date</th>
                  <th>Status</th>
                  <th>Confidence</th>
                  <th>Action</th>
                </tr>
              </thead>
              <tbody>
                {history.length > 0 ? history.map((item) => (
                  <tr key={item.request_id}>
                    <td>
                      <div style={{ display: "flex", alignItems: "center", gap: "0.75rem" }}>
                        <FileText size={18} className="text-vibrant" />
                        <span style={{ fontWeight: 600 }}>{item.filename}</span>
                      </div>
                    </td>
                    <td style={{ opacity: 0.6 }}>{item.doc_type}</td>
                    <td style={{ opacity: 0.6 }}>{item.created_at ? new Date(item.created_at).toLocaleDateString() : "—"}</td>
                    <td>
                      <span className={`status-badge ${item.status === 'completed' ? 'status-completed' : 'status-review'}`}>
                        {item.status}
                      </span>
                    </td>
                    <td style={{ fontWeight: 700 }}>{((item.confidence || 0) * 100).toFixed(0)}%</td>
                    <td>
                      <button
                        className="btn-secondary"
                        style={{ padding: "0.4rem 0.8rem", borderRadius: "0.5rem", fontSize: "0.8rem" }}
                        onClick={() => handleView(item)}
                        disabled={!item.request_id || openingRequestId === item.request_id}
                      >
                        <Eye size={14} /> {openingRequestId === item.request_id ? "Opening..." : "View"}
                      </button>
                    </td>
                  </tr>
                )) : (
                  <tr>
                    <td colSpan={6} style={{ textAlign: "center", padding: "4rem", color: "var(--muted)" }}>
                      No audit records found. Start by uploading a document.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </motion.div>
      </div>

      {selected && (
        <div style={{
          position: "fixed",
          inset: 0,
          zIndex: 2000,
          background: "rgba(0,0,0,0.75)",
          backdropFilter: "blur(6px)",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          padding: "2rem",
        }}>
          <div className="glass" style={{
            width: "100%",
            maxWidth: "1200px",
            height: "85vh",
            borderRadius: "1.25rem",
            overflow: "hidden",
            display: "flex",
            flexDirection: "column",
          }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", padding: "1rem 1.25rem", borderBottom: "1px solid var(--glass-border)" }}>
              <div>
                <div style={{ fontWeight: 700 }}>{selected.filename}</div>
                <div style={{ color: "var(--muted)", fontSize: "0.85rem" }}>
                  {(selected.confidence * 100).toFixed(0)}% confidence
                </div>
              </div>
              <div style={{ display: "flex", gap: "0.75rem" }}>
                <button className="btn btn-secondary" onClick={downloadHistoryExcel}>Download Excel</button>
                <button className="btn btn-secondary" onClick={() => setSelected(null)}>Close</button>
              </div>
            </div>

            <div style={{ flex: 1, display: "grid", gridTemplateColumns: "1fr 1fr", overflow: "hidden" }}>
              <div style={{ borderRight: "1px solid var(--glass-border)", background: "rgba(0,0,0,0.3)" }}>
                <iframe
                  src={`http://localhost:8000/api/v1/document/${selected.request_id}`}
                  style={{ width: "100%", height: "100%", border: "none" }}
                  title="History Document"
                />
              </div>
              <div style={{ padding: "1rem", overflowY: "auto" }}>
                <h3 style={{ marginBottom: "0.75rem" }}>Extracted Results</h3>
                <div className="extraction-table-container">
                  <table className="extraction-table">
                    <thead><tr><th>Field</th><th>Value</th></tr></thead>
                    <tbody>
                      {Object.entries(selected.extracted_data || {}).filter(([k]) => !["raw_text", "char_count"].includes(k)).map(([k, v]) => (
                        <tr key={k}>
                          <td className="field-name-cell">{k.replace(/_/g, " ")}</td>
                          <td className="field-value-cell">{renderHistoryValue(v)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>

                {selected.compliance_flags.length > 0 && (
                  <div style={{ marginTop: "1rem" }}>
                    <h4 style={{ marginBottom: "0.5rem" }}>Compliance Flags</h4>
                    {selected.compliance_flags.map((flag) => (
                      <div key={flag} style={{ marginBottom: "0.5rem", padding: "0.5rem", borderRadius: "0.5rem", border: "1px solid rgba(251, 191, 36, 0.3)", background: "rgba(251, 191, 36, 0.08)", color: "var(--warning)" }}>
                        {flag}
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>
          </div>
        </div>
      )}
    </main>
  );
}
