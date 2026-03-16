"use client";

import React, { useCallback, useEffect, useMemo, useState } from "react";
import axios from "axios";
import { Navbar } from "@/components/Navbar";
import { useAuth } from "@/components/AuthContext";
import { apiUrl } from "@/lib/api";
import { ShieldAlert, Users, FileText, MessageSquareMore, Eye, Save, Trash2, Ban, CheckCircle2 } from "lucide-react";

type AdminOverview = {
  total_users: number;
  active_users: number;
  total_documents: number;
  total_processed: number;
  open_feedback: number;
};

type AdminUser = {
  id: string;
  email: string;
  full_name: string;
  company_name?: string;
  gstin?: string;
  contact_phone?: string;
  designation?: string;
  company_pan?: string;
  address_line1?: string;
  city?: string;
  state?: string;
  pincode?: string;
  is_active: boolean;
  is_admin: boolean;
  created_at?: string;
  documents_processed?: number;
};

type Feedback = {
  feedback_id: string;
  name: string;
  email: string;
  subject: string;
  message: string;
  status: string;
  created_at?: string;
};

type HistoryItem = {
  request_id: string;
  filename?: string;
  doc_type?: string;
  created_at?: string;
  confidence?: number;
  extracted_data?: Record<string, unknown>;
  compliance_flags?: string[];
};

export default function AdminPage() {
  const { token, user, isLoading } = useAuth();
  const [overview, setOverview] = useState<AdminOverview | null>(null);
  const [users, setUsers] = useState<AdminUser[]>([]);
  const [feedback, setFeedback] = useState<Feedback[]>([]);
  const [selectedUser, setSelectedUser] = useState<AdminUser | null>(null);
  const [history, setHistory] = useState<HistoryItem[]>([]);
  const [selectedHistory, setSelectedHistory] = useState<HistoryItem | null>(null);
  const [statusMsg, setStatusMsg] = useState("");

  const headers = useMemo(() => (token ? { Authorization: `Bearer ${token}` } : undefined), [token]);

  const loadAll = useCallback(async () => {
    if (!headers) return;
    const [overviewRes, usersRes, feedbackRes] = await Promise.all([
      axios.get(apiUrl("/api/v1/admin/overview"), { headers }),
      axios.get(apiUrl("/api/v1/admin/users"), { headers }),
      axios.get(apiUrl("/api/v1/admin/feedback"), { headers }),
    ]);
    setOverview(overviewRes.data);
    setUsers(Array.isArray(usersRes.data) ? usersRes.data : []);
    setFeedback(Array.isArray(feedbackRes.data) ? feedbackRes.data : []);
  }, [headers]);

  useEffect(() => {
    if (!token || !user?.is_admin) return;
    queueMicrotask(() => {
      void loadAll();
    });
  }, [loadAll, token, user?.is_admin]);

  const loadUserHistory = async (u: AdminUser) => {
    if (!headers) return;
    setSelectedUser(u);
    const res = await axios.get(apiUrl(`/api/v1/admin/users/${u.id}/history`), { headers });
    setHistory(Array.isArray(res.data) ? res.data : []);
  };

  const saveUser = async () => {
    if (!headers || !selectedUser) return;
    await axios.put(apiUrl(`/api/v1/admin/users/${selectedUser.id}`), selectedUser, { headers });
    setStatusMsg("User profile updated");
    await loadAll();
  };

  const blockToggleUser = async (target: AdminUser) => {
    if (!headers) return;
    await axios.put(
      apiUrl(`/api/v1/admin/users/${target.id}`),
      { is_active: !target.is_active },
      { headers }
    );
    await loadAll();
    if (selectedUser?.id === target.id) {
      setSelectedUser({ ...selectedUser, is_active: !selectedUser.is_active });
    }
  };

  const deleteUser = async (target: AdminUser) => {
    if (!headers) return;
    if (!confirm(`Delete user ${target.email}?`)) return;
    await axios.delete(apiUrl(`/api/v1/admin/users/${target.id}`), { headers });
    setUsers((prev) => prev.filter((u) => u.id !== target.id));
    if (selectedUser?.id === target.id) {
      setSelectedUser(null);
      setHistory([]);
    }
  };

  const resolveFeedback = async (item: Feedback) => {
    if (!headers) return;
    const form = new FormData();
    form.append("status", item.status === "resolved" ? "open" : "resolved");
    await axios.put(apiUrl(`/api/v1/admin/feedback/${item.feedback_id}/status`), form, { headers });
    await loadAll();
  };

  const viewHistoryDetails = async (item: HistoryItem) => {
    if (!headers || !selectedUser) return;
    const res = await axios.get(apiUrl(`/api/v1/admin/users/${selectedUser.id}/history/${item.request_id}`), { headers });
    const payload = res.data || {};
    setSelectedHistory({
      request_id: payload.request_id || item.request_id,
      filename: payload.filename || item.filename,
      doc_type: payload.doc_type || item.doc_type,
      created_at: payload.created_at || item.created_at,
      confidence: payload.confidence ?? item.confidence ?? 0,
      extracted_data: payload.extracted_data || {},
      compliance_flags: Array.isArray(payload.compliance_flags) ? payload.compliance_flags : [],
    });
  };

  const renderAdminValue = (value: unknown): React.ReactNode => {
    if (value === null || value === undefined) return <span style={{ opacity: 0.3 }}>null</span>;
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
                  {cols.map((c) => <td key={c}>{renderAdminValue((item as Record<string, unknown>)[c])}</td>)}
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
                  <td>{renderAdminValue(v)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      );
    }
    return String(value);
  };

  if (isLoading) return null;
  if (!user?.is_admin) {
    return (
      <main>
        <Navbar />
        <div className="hero" style={{ paddingTop: "9rem" }}>
          <div className="glass" style={{ padding: "1.5rem", borderRadius: "1rem", maxWidth: "760px", width: "100%" }}>
            <h2 style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}><ShieldAlert size={18} /> Admin Access Required</h2>
            <p style={{ color: "var(--muted)", marginTop: "0.6rem" }}>This page is only available to admin users.</p>
          </div>
        </div>
      </main>
    );
  }

  return (
    <main>
      <Navbar />
      <div className="hero" style={{ justifyContent: "flex-start", paddingTop: "8.6rem", minHeight: "auto" }}>
        <div style={{ width: "min(1200px, 94vw)", display: "grid", gap: "1rem" }}>
          <div className="glass" style={{ borderRadius: "1rem", padding: "1rem" }}>
            <h2 style={{ display: "flex", alignItems: "center", gap: "0.5rem", marginBottom: "0.7rem" }}>
              <ShieldAlert size={18} /> Admin Panel
            </h2>
            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit,minmax(170px,1fr))", gap: "0.8rem" }}>
              <StatCard icon={<Users size={15} />} label="Total Users" value={overview?.total_users ?? 0} />
              <StatCard icon={<CheckCircle2 size={15} />} label="Active Users" value={overview?.active_users ?? 0} />
              <StatCard icon={<FileText size={15} />} label="Documents" value={overview?.total_documents ?? 0} />
              <StatCard icon={<FileText size={15} />} label="Processed" value={overview?.total_processed ?? 0} />
              <StatCard icon={<MessageSquareMore size={15} />} label="Open Feedback" value={overview?.open_feedback ?? 0} />
            </div>
          </div>

          <div style={{ display: "grid", gridTemplateColumns: "1.2fr 1fr", gap: "1rem" }}>
            <div className="glass" style={{ borderRadius: "1rem", padding: "1rem", overflow: "auto" }}>
              <h3 style={{ marginBottom: "0.8rem" }}>Users</h3>
              <table className="extraction-table">
                <thead>
                  <tr>
                    <th>User</th>
                    <th>Status</th>
                    <th>Docs</th>
                    <th>Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {users.map((u) => (
                    <tr key={u.id}>
                      <td>
                        <div style={{ fontWeight: 700 }}>{u.full_name || "Unnamed"}</div>
                        <div style={{ opacity: 0.7, fontSize: "0.8rem" }}>{u.email}</div>
                      </td>
                      <td>{u.is_active ? "active" : "blocked"}</td>
                      <td>{u.documents_processed || 0}</td>
                      <td>
                        <div style={{ display: "flex", gap: "0.4rem", flexWrap: "wrap" }}>
                          <button className="btn-secondary" style={miniBtn} onClick={() => loadUserHistory(u)}><Eye size={13} /> View</button>
                          <button className="btn-secondary" style={miniBtn} onClick={() => blockToggleUser(u)}>
                            {u.is_active ? <Ban size={13} /> : <CheckCircle2 size={13} />} {u.is_active ? "Block" : "Unblock"}
                          </button>
                          <button className="btn-secondary" style={miniBtn} onClick={() => deleteUser(u)}><Trash2 size={13} /> Delete</button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            <div className="glass" style={{ borderRadius: "1rem", padding: "1rem" }}>
              <h3 style={{ marginBottom: "0.7rem" }}>User Profile Edit</h3>
              {selectedUser ? (
                <div style={{ display: "grid", gap: "0.55rem" }}>
                  <input value={selectedUser.full_name || ""} onChange={(e) => setSelectedUser({ ...selectedUser, full_name: e.target.value })} placeholder="Full Name" style={inputStyle} />
                  <input value={selectedUser.company_name || ""} onChange={(e) => setSelectedUser({ ...selectedUser, company_name: e.target.value })} placeholder="Company" style={inputStyle} />
                  <input value={selectedUser.gstin || ""} onChange={(e) => setSelectedUser({ ...selectedUser, gstin: e.target.value })} placeholder="GSTIN" style={inputStyle} />
                  <input value={selectedUser.company_pan || ""} onChange={(e) => setSelectedUser({ ...selectedUser, company_pan: e.target.value })} placeholder="Company PAN" style={inputStyle} />
                  <input value={selectedUser.contact_phone || ""} onChange={(e) => setSelectedUser({ ...selectedUser, contact_phone: e.target.value })} placeholder="Phone" style={inputStyle} />
                  <button className="btn btn-primary" style={{ justifyContent: "center" }} onClick={saveUser}>
                    <Save size={16} /> Save
                  </button>
                  {statusMsg && <p style={{ color: "var(--success)", fontSize: "0.85rem" }}>{statusMsg}</p>}
                </div>
              ) : (
                <p style={{ color: "var(--muted)" }}>Select a user from left panel.</p>
              )}
            </div>
          </div>

          <div style={{ display: "grid", gridTemplateColumns: "1.2fr 1fr", gap: "1rem", marginBottom: "2rem" }}>
            <div className="glass" style={{ borderRadius: "1rem", padding: "1rem", overflow: "auto" }}>
              <h3 style={{ marginBottom: "0.7rem" }}>Processed Documents ({selectedUser?.email || "No user selected"})</h3>
              <table className="extraction-table">
                <thead>
                  <tr>
                    <th>Request</th>
                    <th>File</th>
                    <th>Type</th>
                    <th>Action</th>
                  </tr>
                </thead>
                <tbody>
                  {history.length > 0 ? history.map((h) => (
                    <tr key={h.request_id}>
                      <td>{h.request_id}</td>
                      <td>{h.filename || "document.pdf"}</td>
                      <td>{h.doc_type || "unknown"}</td>
                      <td>
                        <button className="btn-secondary" style={miniBtn} onClick={() => viewHistoryDetails(h)}>
                          <Eye size={13} /> Open
                        </button>
                      </td>
                    </tr>
                  )) : (
                    <tr><td colSpan={4} style={{ opacity: 0.7 }}>No processed documents</td></tr>
                  )}
                </tbody>
              </table>
            </div>

            <div className="glass" style={{ borderRadius: "1rem", padding: "1rem", overflow: "auto" }}>
              <h3 style={{ marginBottom: "0.7rem" }}>Feedback</h3>
              <div style={{ display: "grid", gap: "0.6rem" }}>
                {feedback.map((f) => (
                  <div key={f.feedback_id} style={{ border: "1px solid var(--glass-border)", borderRadius: "0.8rem", padding: "0.65rem" }}>
                    <div style={{ fontWeight: 700 }}>{f.subject || "No subject"}</div>
                    <div style={{ fontSize: "0.8rem", opacity: 0.7 }}>{f.email}</div>
                    <div style={{ marginTop: "0.45rem", fontSize: "0.88rem", opacity: 0.9 }}>{f.message}</div>
                    <button className="btn-secondary" style={{ ...miniBtn, marginTop: "0.5rem" }} onClick={() => resolveFeedback(f)}>
                      {f.status === "resolved" ? "Reopen" : "Mark Resolved"}
                    </button>
                  </div>
                ))}
                {feedback.length === 0 && <p style={{ color: "var(--muted)" }}>No feedback items.</p>}
              </div>
            </div>
          </div>
        </div>
      </div>

      {selectedHistory && (
        <div style={{ position: "fixed", inset: 0, zIndex: 2000, background: "rgba(0,0,0,0.75)", display: "flex", alignItems: "center", justifyContent: "center", padding: "1rem" }}>
          <div className="glass" style={{ width: "min(1200px, 97vw)", height: "85vh", borderRadius: "1rem", overflow: "hidden", display: "grid", gridTemplateColumns: "1fr 1fr" }}>
            <iframe
              src={apiUrl(`/api/v1/document/${selectedHistory.request_id}${token ? `?token=${encodeURIComponent(token)}` : ""}`)}
              style={{ width: "100%", height: "100%", border: "none" }}
            />
            <div style={{ padding: "1rem", overflow: "auto" }}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "0.7rem" }}>
                <h3>Extracted Data</h3>
                <button className="btn btn-secondary" onClick={() => setSelectedHistory(null)}>Close</button>
              </div>
              <div className="extraction-table-container">
                <table className="extraction-table">
                  <thead><tr><th>Field</th><th>Value</th></tr></thead>
                  <tbody>
                    {Object.entries(selectedHistory.extracted_data || {})
                      .filter(([k]) => !["raw_text", "char_count"].includes(k))
                      .map(([k, v]) => (
                        <tr key={k}>
                          <td className="field-name-cell">{k.replace(/_/g, " ")}</td>
                          <td className="field-value-cell">{renderAdminValue(v)}</td>
                        </tr>
                      ))}
                  </tbody>
                </table>
              </div>
              {(selectedHistory.compliance_flags || []).length > 0 && (
                <div style={{ marginTop: "0.85rem" }}>
                  <h4 style={{ marginBottom: "0.45rem" }}>Compliance Flags</h4>
                  {(selectedHistory.compliance_flags || []).map((flag) => (
                    <div key={flag} style={{ marginBottom: "0.4rem", padding: "0.45rem", borderRadius: "0.45rem", border: "1px solid rgba(251,191,36,0.3)", background: "rgba(251,191,36,0.08)", color: "var(--warning)" }}>
                      {flag}
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </main>
  );
}

function StatCard({ icon, label, value }: { icon: React.ReactNode; label: string; value: number }) {
  return (
    <div style={{ border: "1px solid var(--glass-border)", borderRadius: "0.8rem", padding: "0.75rem", background: "rgba(255,255,255,0.02)" }}>
      <div style={{ display: "flex", alignItems: "center", gap: "0.4rem", opacity: 0.85 }}>{icon}<span style={{ fontSize: "0.78rem" }}>{label}</span></div>
      <div style={{ marginTop: "0.3rem", fontSize: "1.3rem", fontWeight: 800 }}>{value}</div>
    </div>
  );
}

const miniBtn: React.CSSProperties = {
  padding: "0.35rem 0.55rem",
  borderRadius: "0.5rem",
  fontSize: "0.78rem",
  display: "inline-flex",
  gap: "0.25rem",
  alignItems: "center",
};

const inputStyle: React.CSSProperties = {
  width: "100%",
  borderRadius: "0.6rem",
  border: "1px solid var(--glass-border)",
  background: "rgba(255,255,255,0.03)",
  color: "#fff",
  padding: "0.6rem 0.72rem",
  outline: "none",
};
