"use client";

import React, { useState, useEffect } from "react";
import { motion } from "framer-motion";
import { User, Building2, Fingerprint, Save, Mail, CheckCircle2, AlertCircle } from "lucide-react";
import { Navbar } from "@/components/Navbar";
import { useAuth } from "@/components/AuthContext";
import axios from "axios";

export default function ProfilePage() {
  const { user, token, refreshProfile, isLoading: authLoading } = useAuth();
  const [fullName, setFullName] = useState("");
  const [companyName, setCompanyName] = useState("");
  const [gstin, setGstin] = useState("");
  const [isSaving, setIsSaving] = useState(false);
  const [message, setMessage] = useState("");

  useEffect(() => {
    if (user) {
      setFullName(user.full_name || "");
      setCompanyName(user.company_name || "");
      setGstin(user.gstin || "");
    }
  }, [user]);

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsSaving(true);
    setMessage("");

    const formData = new FormData();
    formData.append("full_name", fullName);
    formData.append("company_name", companyName);
    formData.append("gstin", gstin);

    try {
      await axios.put("http://localhost:8000/api/v1/auth/profile", formData, {
        headers: { Authorization: `Bearer ${token}` }
      });
      await refreshProfile();
      setMessage("Profile updated successfully!");
    } catch (_err) {
      setMessage("Failed to update profile.");
    } finally {
      setIsSaving(false);
    }
  };

  if (authLoading) return null;

  return (
    <main>
      <Navbar />
      <div className="hero" style={{ justifyContent: "flex-start", paddingTop: "10rem" }}>
        <motion.div 
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          className="glass"
          style={{ width: "100%", maxWidth: "600px", padding: "3rem", borderRadius: "2rem" }}
        >
          <div style={{ marginBottom: "3rem" }}>
            <h2 className="text-gradient" style={{ fontSize: "2.25rem", fontWeight: 800 }}>Account Profile</h2>
            <p style={{ color: "var(--muted)", marginTop: "0.5rem" }}>Manage your personal and business details</p>
          </div>

          <form onSubmit={handleSave} style={{ display: "flex", flexDirection: "column", gap: "2rem" }}>
            
            <div style={{ display: "grid", gap: "1.5rem" }}>
              <div style={{ position: "relative" }}>
                <label style={{ fontSize: "0.75rem", fontWeight: 700, color: "var(--muted)", textTransform: "uppercase", marginBottom: "0.5rem", display: "block" }}>Full Name</label>
                <div style={{ position: "relative" }}>
                  <User size={18} style={{ position: "absolute", left: "1rem", top: "50%", transform: "translateY(-50%)", opacity: 0.4 }} />
                  <input 
                    type="text" value={fullName} onChange={(e) => setFullName(e.target.value)}
                    style={{ width: "100%", padding: "1rem 1rem 1rem 3rem", borderRadius: "1rem", background: "rgba(255,255,255,0.05)", border: "1px solid var(--glass-border)", color: "white", outline: "none" }} 
                  />
                </div>
              </div>

              <div style={{ position: "relative" }}>
                <label style={{ fontSize: "0.75rem", fontWeight: 700, color: "var(--muted)", textTransform: "uppercase", marginBottom: "0.5rem", display: "block" }}>Email Address (Verified)</label>
                <div style={{ position: "relative" }}>
                  <Mail size={18} style={{ position: "absolute", left: "1rem", top: "50%", transform: "translateY(-50%)", opacity: 0.4 }} />
                  <input 
                    type="text" value={user?.email || ""} disabled
                    style={{ width: "100%", padding: "1rem 1rem 1rem 3rem", borderRadius: "1rem", background: "rgba(255,255,255,0.02)", border: "1px solid var(--glass-border)", color: "rgba(255,255,255,0.4)", outline: "none", cursor: "not-allowed" }} 
                  />
                </div>
              </div>

              <div style={{ position: "relative" }}>
                <label style={{ fontSize: "0.75rem", fontWeight: 700, color: "var(--muted)", textTransform: "uppercase", marginBottom: "0.5rem", display: "block" }}>Company Name</label>
                <div style={{ position: "relative" }}>
                  <Building2 size={18} style={{ position: "absolute", left: "1rem", top: "50%", transform: "translateY(-50%)", opacity: 0.4 }} />
                  <input 
                    type="text" value={companyName} onChange={(e) => setCompanyName(e.target.value)} placeholder="e.g. Acme Corp"
                    style={{ width: "100%", padding: "1rem 1rem 1rem 3rem", borderRadius: "1rem", background: "rgba(255,255,255,0.05)", border: "1px solid var(--glass-border)", color: "white", outline: "none" }} 
                  />
                </div>
              </div>

              <div style={{ position: "relative" }}>
                <label style={{ fontSize: "0.75rem", fontWeight: 700, color: "var(--muted)", textTransform: "uppercase", marginBottom: "0.5rem", display: "block" }}>Business GSTIN</label>
                <div style={{ position: "relative" }}>
                  <Fingerprint size={18} style={{ position: "absolute", left: "1rem", top: "50%", transform: "translateY(-50%)", opacity: 0.4 }} />
                  <input 
                    type="text" value={gstin} onChange={(e) => setGstin(e.target.value)} placeholder="15-digit GST Number"
                    style={{ width: "100%", padding: "1rem 1rem 1rem 3rem", borderRadius: "1rem", background: "rgba(255,255,255,0.05)", border: "1px solid var(--glass-border)", color: "white", outline: "none" }} 
                  />
                </div>
              </div>
            </div>

            {message && (
              <div style={{ padding: "1rem", borderRadius: "0.75rem", background: message.includes("success") ? "rgba(16, 185, 129, 0.1)" : "rgba(239, 68, 68, 0.1)", border: `1px solid ${message.includes("success") ? "var(--success)" : "var(--error)"}`, color: message.includes("success") ? "var(--success)" : "var(--error)", display: "flex", alignItems: "center", gap: "0.5rem", fontSize: "0.875rem" }}>
                {message.includes("success") ? <CheckCircle2 size={16} /> : <AlertCircle size={16} />}
                {message}
              </div>
            )}

            <button className="btn btn-primary" type="submit" disabled={isSaving} style={{ width: "100%", justifyContent: "center" }}>
              {isSaving ? "Saving..." : "Update Profile"} <Save size={18} />
            </button>
          </form>
        </motion.div>
      </div>
    </main>
  );
}
