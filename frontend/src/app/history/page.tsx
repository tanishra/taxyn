"use client";

import React, { useEffect, useState } from "react";
import { Navbar } from "@/components/Navbar";
import { motion } from "framer-motion";
import { FileText, Eye } from "lucide-react";
import { useAuth } from "@/components/AuthContext";
import axios from "axios";
import * as XLSX from "xlsx";
import { apiUrl } from "@/lib/api";

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

export default function HistoryPage() {
  const { token, isLoading: authLoading } = useAuth();
  const [history, setHistory] = useState<HistoryItem[]>([]);
  const [selected, setSelected] = useState<HistoryDetail | null>(null);
  const [openingRequestId, setOpeningRequestId] = useState<string | null>(null);

  const isInvoiceDocType = (docType: string | undefined) => {
    return String(docType || "").replace("DocType.", "").toLowerCase() === "invoice";
  };

  useEffect(() => {
    if (!token) return;
    let cancelled = false;

    const load = async () => {
      try {
        const res = await axios.get(apiUrl("/api/v1/auth/history"), {
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
      } catch {
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
      const res = await axios.get(apiUrl(`/api/v1/auth/history/${item.request_id}`), {
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
    } catch {
      console.error("Failed to load history details");
    } finally {
      setOpeningRequestId(null);
    }
  };

  const downloadHistoryExcel = () => {
    if (!selected) return;
    const hideKeys = ["raw_text", "char_count", "recon_results", "portal_data", "category_totals"];
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

  const downloadERPExport = async (format: "tally_xml" | "zoho_csv" | "quickbooks_csv") => {
    if (!token || !selected?.request_id) return;
    try {
      const response = await axios.get(apiUrl(`/api/v1/export/${selected.request_id}?export_format=${format}`), {
        headers: { Authorization: `Bearer ${token}` },
        responseType: "blob",
      });
      const blob = new Blob([response.data], { type: response.headers["content-type"] || "application/octet-stream" });
      const downloadUrl = URL.createObjectURL(blob);
      const anchor = document.createElement("a");
      const extension = format === "tally_xml" ? "xml" : "csv";
      anchor.href = downloadUrl;
      anchor.download = `${(selected.filename || selected.request_id).replace(/\.pdf$/i, "")}_${format}.${extension}`;
      document.body.appendChild(anchor);
      anchor.click();
      anchor.remove();
      URL.revokeObjectURL(downloadUrl);
    } catch {
      console.error("Failed to download ERP export");
    }
  };

  const renderHistoryValue = (value: unknown, options?: { preserveTableLayout?: boolean }): React.ReactNode => {
    if (value === null || value === undefined) {
      return <span style={{ opacity: 0.3 }}>null</span>;
    }

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
              <td>{typeof value === "number" ? formatCurrency(value) : renderHistoryValue(value)}</td>
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
      return renderHistoryValue(value, { preserveTableLayout: true });
    }
    if (field === "statement_summary" && value && typeof value === "object" && !Array.isArray(value)) {
      return renderStatementSummary(value as BankStatementSummary);
    }
    if (field === "category_totals" && value && typeof value === "object" && !Array.isArray(value)) {
      return renderKeyValueTable(value as Record<string, unknown>);
    }
    return renderHistoryValue(value);
  };

  if (authLoading) return null;

  const selectedStatementSummary = (
    selected?.extracted_data?.statement_summary &&
    typeof selected.extracted_data.statement_summary === "object" &&
    !Array.isArray(selected.extracted_data.statement_summary)
  ) ? (selected.extracted_data.statement_summary as BankStatementSummary) : null;
  const selectedTransactions = Array.isArray(selected?.extracted_data?.transactions)
    ? (selected.extracted_data.transactions as unknown[])
    : null;

  return (
    <main>
      <Navbar />
      <div className="hero" style={{ justifyContent: "flex-start", paddingTop: "10rem", width: "100%", paddingInline: "0.5rem" }}>
        <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} className="history-main-container">
          <div style={{ marginBottom: "2rem" }}>
            <h2 style={{ fontSize: "2rem", fontWeight: 800 }}>Audit History</h2>
            <p style={{ color: "var(--muted)" }}>View and re-download your past extraction results</p>
          </div>

          <div className="extraction-table-container history-table-container">
            <table className="extraction-table history-table">
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
                    <td title={item.filename}>
                      <div style={{ display: "flex", alignItems: "center", gap: "0.75rem", minWidth: 0 }}>
                        <FileText size={18} className="text-vibrant" />
                        <span className="history-cell-ellipsis" style={{ fontWeight: 600 }}>{item.filename}</span>
                      </div>
                    </td>
                    <td title={item.doc_type} style={{ opacity: 0.6 }}>
                      <span className="history-cell-ellipsis">{item.doc_type}</span>
                    </td>
                    <td style={{ opacity: 0.6 }}>
                      <span className="history-cell-ellipsis">{item.created_at ? new Date(item.created_at).toLocaleDateString() : "—"}</span>
                    </td>
                    <td>
                      <span className={`status-badge ${item.status === 'completed' ? 'status-completed' : 'status-review'}`}>
                        {item.status}
                      </span>
                    </td>
                    <td style={{ fontWeight: 700 }}>
                      <span className="history-cell-ellipsis">{((item.confidence || 0) * 100).toFixed(0)}%</span>
                    </td>
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
            maxWidth: "1920px",
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
                {isInvoiceDocType(selected.doc_type) && (
                  <>
                    <button className="btn btn-secondary" onClick={() => downloadERPExport("tally_xml")}>Tally XML</button>
                    <button className="btn btn-secondary" onClick={() => downloadERPExport("zoho_csv")}>Zoho CSV</button>
                    <button className="btn btn-secondary" onClick={() => downloadERPExport("quickbooks_csv")}>QuickBooks CSV</button>
                  </>
                )}
                <button className="btn btn-secondary" onClick={() => setSelected(null)}>Close</button>
              </div>
            </div>

            <div style={{ flex: 1, display: "grid", gridTemplateColumns: "1fr 1fr", overflow: "hidden" }}>
              <div style={{ borderRight: "1px solid var(--glass-border)", background: "rgba(0,0,0,0.3)" }}>
                <iframe
                  src={apiUrl(`/api/v1/document/${selected.request_id}${token ? `?token=${encodeURIComponent(token)}` : ""}`)}
                  style={{ width: "100%", height: "100%", border: "none" }}
                  title="History Document"
                />
              </div>
              <div style={{ padding: "1rem", overflowY: "auto" }}>
                <h3 style={{ marginBottom: "0.75rem" }}>Extracted Results</h3>

                {selectedStatementSummary && (
                  <div style={{ padding: "1.25rem", borderRadius: "1rem", marginBottom: "1rem", border: "1px solid rgba(99, 102, 241, 0.18)", background: "rgba(99, 102, 241, 0.05)" }}>
                    <h4 style={{ marginBottom: "0.85rem" }}>Statement Summary</h4>
                    {renderStatementSummary(selectedStatementSummary)}
                  </div>
                )}

                {selectedTransactions && selectedTransactions.length > 0 && (
                  <div style={{ padding: "1.25rem", borderRadius: "1rem", marginBottom: "1rem", border: "1px solid rgba(255, 255, 255, 0.08)", background: "rgba(255,255,255,0.03)" }}>
                    <h4 style={{ marginBottom: "0.85rem" }}>Transactions</h4>
                    {renderHistoryValue(selectedTransactions, { preserveTableLayout: true })}
                  </div>
                )}

                <div className="extraction-table-container">
                  <table className="extraction-table">
                    <thead><tr><th>Field</th><th>Value</th></tr></thead>
                    <tbody>
                      {Object.entries(selected.extracted_data || {}).filter(([k]) => !["raw_text", "char_count", "category_totals", "statement_summary", "transactions"].includes(k)).map(([k, v]) => (
                        <tr key={k}>
                          <td className="field-name-cell">{k.replace(/_/g, " ")}</td>
                          <td className="field-value-cell">{renderFieldValue(k, v)}</td>
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
