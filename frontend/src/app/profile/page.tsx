"use client";

import React, { useState, useEffect } from "react";
import { motion } from "framer-motion";
import {
  User,
  Building2,
  Fingerprint,
  Save,
  Mail,
  CheckCircle2,
  AlertCircle,
  Phone,
  BriefcaseBusiness,
  MapPin,
  Landmark,
} from "lucide-react";
import { Navbar } from "@/components/Navbar";
import { useAuth } from "@/components/AuthContext";
import axios from "axios";
import { apiUrl } from "@/lib/api";

export default function ProfilePage() {
  const { user, token, refreshProfile, isLoading: authLoading } = useAuth();

  const [fullName, setFullName] = useState("");
  const [companyName, setCompanyName] = useState("");
  const [gstin, setGstin] = useState("");
  const [contactPhone, setContactPhone] = useState("");
  const [designation, setDesignation] = useState("");
  const [companyPan, setCompanyPan] = useState("");
  const [addressLine1, setAddressLine1] = useState("");
  const [city, setCity] = useState("");
  const [state, setState] = useState("");
  const [pincode, setPincode] = useState("");

  const [isSaving, setIsSaving] = useState(false);
  const [message, setMessage] = useState("");

  useEffect(() => {
    if (!user) return;
    setFullName(user.full_name || "");
    setCompanyName(user.company_name || "");
    setGstin(user.gstin || "");
    setContactPhone(user.contact_phone || "");
    setDesignation(user.designation || "");
    setCompanyPan(user.company_pan || "");
    setAddressLine1(user.address_line1 || "");
    setCity(user.city || "");
    setState(user.state || "");
    setPincode(user.pincode || "");
  }, [user]);

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsSaving(true);
    setMessage("");

    const formData = new FormData();
    formData.append("full_name", fullName);
    formData.append("company_name", companyName);
    formData.append("gstin", gstin);
    formData.append("contact_phone", contactPhone);
    formData.append("designation", designation);
    formData.append("company_pan", companyPan);
    formData.append("address_line1", addressLine1);
    formData.append("city", city);
    formData.append("state", state);
    formData.append("pincode", pincode);

    try {
      await axios.put(apiUrl("/api/v1/auth/profile"), formData, {
        headers: { Authorization: `Bearer ${token}` },
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

  const inputStyle: React.CSSProperties = {
    width: "100%",
    padding: "0.95rem 1rem 0.95rem 2.9rem",
    borderRadius: "0.9rem",
    background: "rgba(255,255,255,0.04)",
    border: "1px solid var(--glass-border)",
    color: "white",
    outline: "none",
    fontSize: "0.95rem",
  };

  const sectionStyle: React.CSSProperties = {
    border: "1px solid var(--glass-border)",
    borderRadius: "1rem",
    background: "rgba(255,255,255,0.02)",
    padding: "1rem",
  };

  return (
    <main>
      <Navbar />
      <div className="hero" style={{ justifyContent: "flex-start", paddingTop: "10rem", paddingBottom: "4rem" }}>
        <motion.div
          initial={{ opacity: 0, y: 14 }}
          animate={{ opacity: 1, y: 0 }}
          className="glass"
          style={{ width: "100%", maxWidth: "980px", padding: "2rem", borderRadius: "1.5rem" }}
        >
          <div style={{ marginBottom: "1.6rem", display: "flex", justifyContent: "space-between", alignItems: "end", gap: "1rem", flexWrap: "wrap" }}>
            <div>
              <h2 className="text-gradient" style={{ fontSize: "2rem", fontWeight: 800 }}>Account Profile</h2>
              <p style={{ color: "var(--muted)", marginTop: "0.35rem" }}>
                Manage your identity, organization, and filing details.
              </p>
            </div>
          </div>

          <form onSubmit={handleSave} style={{ display: "grid", gap: "1rem" }}>
            <div style={sectionStyle}>
              <p style={{ marginBottom: "0.75rem", color: "#d8d9ff", fontWeight: 700 }}>Personal</p>
              <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(240px, 1fr))", gap: "0.9rem" }}>
                <div style={{ position: "relative" }}>
                  <User size={17} style={{ position: "absolute", left: "0.95rem", top: "50%", transform: "translateY(-50%)", opacity: 0.45 }} />
                  <input type="text" value={fullName} onChange={(e) => setFullName(e.target.value)} placeholder="Full Name" style={inputStyle} />
                </div>
                <div style={{ position: "relative" }}>
                  <BriefcaseBusiness size={17} style={{ position: "absolute", left: "0.95rem", top: "50%", transform: "translateY(-50%)", opacity: 0.45 }} />
                  <input type="text" value={designation} onChange={(e) => setDesignation(e.target.value)} placeholder="Designation (e.g. Tax Manager)" style={inputStyle} />
                </div>
                <div style={{ position: "relative" }}>
                  <Mail size={17} style={{ position: "absolute", left: "0.95rem", top: "50%", transform: "translateY(-50%)", opacity: 0.45 }} />
                  <input type="text" value={user?.email || ""} disabled style={{ ...inputStyle, background: "rgba(255,255,255,0.02)", color: "rgba(255,255,255,0.45)" }} />
                </div>
                <div style={{ position: "relative" }}>
                  <Phone size={17} style={{ position: "absolute", left: "0.95rem", top: "50%", transform: "translateY(-50%)", opacity: 0.45 }} />
                  <input type="text" value={contactPhone} onChange={(e) => setContactPhone(e.target.value)} placeholder="Contact Phone" style={inputStyle} />
                </div>
              </div>
            </div>

            <div style={sectionStyle}>
              <p style={{ marginBottom: "0.75rem", color: "#d8d9ff", fontWeight: 700 }}>Organization & Tax</p>
              <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(240px, 1fr))", gap: "0.9rem" }}>
                <div style={{ position: "relative" }}>
                  <Building2 size={17} style={{ position: "absolute", left: "0.95rem", top: "50%", transform: "translateY(-50%)", opacity: 0.45 }} />
                  <input type="text" value={companyName} onChange={(e) => setCompanyName(e.target.value)} placeholder="Company/Firm Name" style={inputStyle} />
                </div>
                <div style={{ position: "relative" }}>
                  <Landmark size={17} style={{ position: "absolute", left: "0.95rem", top: "50%", transform: "translateY(-50%)", opacity: 0.45 }} />
                  <input type="text" value={companyPan} onChange={(e) => setCompanyPan(e.target.value)} placeholder="Company PAN" style={inputStyle} />
                </div>
                <div style={{ position: "relative" }}>
                  <Fingerprint size={17} style={{ position: "absolute", left: "0.95rem", top: "50%", transform: "translateY(-50%)", opacity: 0.45 }} />
                  <input type="text" value={gstin} onChange={(e) => setGstin(e.target.value)} placeholder="Business GSTIN" style={inputStyle} />
                </div>
              </div>
            </div>

            <div style={sectionStyle}>
              <p style={{ marginBottom: "0.75rem", color: "#d8d9ff", fontWeight: 700 }}>Address</p>
              <div style={{ display: "grid", gridTemplateColumns: "1fr", gap: "0.9rem" }}>
                <div style={{ position: "relative" }}>
                  <MapPin size={17} style={{ position: "absolute", left: "0.95rem", top: "50%", transform: "translateY(-50%)", opacity: 0.45 }} />
                  <input type="text" value={addressLine1} onChange={(e) => setAddressLine1(e.target.value)} placeholder="Address Line" style={inputStyle} />
                </div>
                <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))", gap: "0.9rem" }}>
                  <div style={{ position: "relative" }}>
                    <MapPin size={17} style={{ position: "absolute", left: "0.95rem", top: "50%", transform: "translateY(-50%)", opacity: 0.45 }} />
                    <input type="text" value={city} onChange={(e) => setCity(e.target.value)} placeholder="City" style={inputStyle} />
                  </div>
                  <div style={{ position: "relative" }}>
                    <MapPin size={17} style={{ position: "absolute", left: "0.95rem", top: "50%", transform: "translateY(-50%)", opacity: 0.45 }} />
                    <input type="text" value={state} onChange={(e) => setState(e.target.value)} placeholder="State" style={inputStyle} />
                  </div>
                  <div style={{ position: "relative" }}>
                    <MapPin size={17} style={{ position: "absolute", left: "0.95rem", top: "50%", transform: "translateY(-50%)", opacity: 0.45 }} />
                    <input type="text" value={pincode} onChange={(e) => setPincode(e.target.value)} placeholder="Pincode" style={inputStyle} />
                  </div>
                </div>
              </div>
            </div>

            {message && (
              <div style={{
                padding: "0.9rem 1rem",
                borderRadius: "0.75rem",
                background: message.includes("success") ? "rgba(16, 185, 129, 0.12)" : "rgba(239, 68, 68, 0.12)",
                border: `1px solid ${message.includes("success") ? "rgba(16, 185, 129, 0.35)" : "rgba(239, 68, 68, 0.35)"}`,
                color: message.includes("success") ? "var(--success)" : "var(--error)",
                display: "flex",
                alignItems: "center",
                gap: "0.5rem",
                fontSize: "0.9rem",
              }}>
                {message.includes("success") ? <CheckCircle2 size={16} /> : <AlertCircle size={16} />}
                {message}
              </div>
            )}

            <button className="btn btn-primary" type="submit" disabled={isSaving} style={{ width: "100%", justifyContent: "center", marginTop: "0.2rem" }}>
              {isSaving ? "Saving Profile..." : "Save Profile"} <Save size={18} />
            </button>
          </form>
        </motion.div>
      </div>
    </main>
  );
}
