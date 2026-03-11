"use client";

import React, { useEffect, useState } from "react";
import { Navbar } from "@/components/Navbar";
import { motion } from "framer-motion";
import { FileText, Calendar, ShieldCheck, ArrowRight, Eye } from "lucide-react";
import { useAuth } from "@/components/AuthContext";
import axios from "axios";
import Link from "next/link";

export default function HistoryPage() {
  const { token, user, isLoading: authLoading } = useAuth();
  const [history, setHistory] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (token) fetchHistory();
  }, [token]);

  const fetchHistory = async () => {
    try {
      const res = await axios.get("http://localhost:8000/api/v1/auth/history", {
        headers: { Authorization: `Bearer ${token}` }
      });
      setHistory(res.data);
    } catch (err) {
      console.error("Failed to fetch history");
    } finally {
      setLoading(false);
    }
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
                {history.length > 0 ? history.map((item, idx) => (
                  <tr key={item.request_id}>
                    <td>
                      <div style={{ display: "flex", alignItems: "center", gap: "0.75rem" }}>
                        <FileText size={18} className="text-vibrant" />
                        <span style={{ fontWeight: 600 }}>{item.filename}</span>
                      </div>
                    </td>
                    <td style={{ opacity: 0.6 }}>{item.doc_type}</td>
                    <td style={{ opacity: 0.6 }}>{new Date(item.created_at).toLocaleDateString()}</td>
                    <td>
                      <span className={`status-badge ${item.status === 'completed' ? 'status-completed' : 'status-review'}`}>
                        {item.status}
                      </span>
                    </td>
                    <td style={{ fontWeight: 700 }}>{(item.confidence * 100).toFixed(0)}%</td>
                    <td>
                      <button className="btn-secondary" style={{ padding: "0.4rem 0.8rem", borderRadius: "0.5rem", fontSize: "0.8rem" }}>
                        <Eye size={14} /> View
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
    </main>
  );
}
