"use client";

import React, { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { 
  X, Check, AlertCircle, Eye, 
  ChevronRight, Save, History, FileText, Loader2
} from "lucide-react";
import axios from "axios";

interface ReviewModalProps {
  isOpen: boolean;
  onClose: () => void;
  data: any;
  requestId: string;
  onResolved: () => void;
}

export const ReviewModal = ({ isOpen, onClose, data, requestId, onResolved }: ReviewModalProps) => {
  const [formData, setFormData] = useState(data || {});
  const [isSubmitting, setIsSubmitting] = useState(false);

  if (!isOpen) return null;

  const handleSave = async () => {
    setIsSubmitting(true);
    try {
      await axios.post(`http://localhost:8000/api/v1/review/${requestId}/resolve`, formData);
      onResolved();
      onClose();
    } catch (err) {
      console.error("Failed to save correction", err);
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div style={{
      position: "fixed", inset: 0, zIndex: 2000, 
      background: "rgba(0,0,0,0.8)", backdropFilter: "blur(8px)",
      display: "flex", alignItems: "center", justifyContent: "center", padding: "2rem"
    }}>
      <motion.div 
        initial={{ opacity: 0, scale: 0.95, y: 20 }}
        animate={{ opacity: 1, scale: 1, y: 0 }}
        className="glass"
        style={{ 
          width: "100%", maxWidth: "1200px", height: "90vh", 
          borderRadius: "2rem", overflow: "hidden", display: "flex", flexDirection: "column"
        }}
      >
        {/* Header */}
        <div style={{ 
          padding: "1.5rem 2rem", borderBottom: "1px solid var(--glass-border)",
          display: "flex", justifyContent: "space-between", alignItems: "center"
        }}>
          <div>
            <h2 style={{ fontSize: "1.25rem", fontWeight: 700 }}>Review Required</h2>
            <p style={{ fontSize: "0.8rem", color: "var(--muted)" }}>Request ID: {requestId}</p>
          </div>
          <button className="btn btn-secondary" onClick={onClose} style={{ padding: "0.5rem" }}>
            <X size={20} />
          </button>
        </div>

        {/* Content Side-by-Side */}
        <div style={{ flex: 1, display: "flex", overflow: "hidden" }}>
          
          {/* Left: Real Document Rendering */}
          <div style={{ 
            flex: 1, background: "rgba(0,0,0,0.4)", padding: "1.5rem", 
            borderRight: "1px solid var(--glass-border)", display: "flex", flexDirection: "column"
          }}>
            <div className="badge glass" style={{ marginBottom: "1rem", alignSelf: "flex-start" }}>
              <Eye size={14} /> Source Document
            </div>
            <div style={{ flex: 1, borderRadius: "1rem", overflow: "hidden", background: "#333", position: "relative" }}>
              <iframe 
                src={`http://localhost:8000/api/v1/document/${requestId}`}
                style={{ width: "100%", height: "100%", border: "none" }}
                title="Document Preview"
              />
            </div>
          </div>

          {/* Right: Editable Form */}
          <div style={{ flex: 1, padding: "2rem", overflowY: "auto", background: "rgba(255,255,255,0.01)" }}>
            <div className="badge glass" style={{ marginBottom: "1.5rem", color: "var(--warning)" }}>
              <AlertCircle size={14} /> High-Accuracy Manual Verification
            </div>

            <div style={{ display: "flex", flexDirection: "column", gap: "1.5rem" }}>
              {Object.entries(formData).filter(([k]) => !["raw_text", "char_count"].includes(k)).map(([key, value]) => (
                <div key={key}>
                  <label style={{ 
                    display: "block", fontSize: "0.75rem", fontWeight: 700, 
                    textTransform: "uppercase", color: "var(--muted)", marginBottom: "0.5rem" 
                  }}>
                    {key.replace(/_/g, " ")}
                  </label>
                  <input 
                    type="text"
                    defaultValue={String(value)}
                    onBlur={(e) => setFormData({ ...formData, [key]: e.target.value })}
                    style={{ 
                      width: "100%", padding: "1rem", background: "rgba(255,255,255,0.05)",
                      border: "1px solid var(--glass-border)", borderRadius: "0.75rem",
                      color: "#fff", fontWeight: 600, outline: "none",
                      transition: "all 0.2s ease"
                    }}
                  />
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* Footer */}
        <div style={{ 
          padding: "1.5rem 2rem", borderTop: "1px solid var(--glass-border)",
          display: "flex", justifyContent: "flex-end", gap: "1rem", background: "rgba(0,0,0,0.2)"
        }}>
          <button className="btn btn-secondary" onClick={onClose}>Discard Changes</button>
          <button className="btn btn-primary" onClick={handleSave} disabled={isSubmitting}>
            {isSubmitting ? <Loader2 className="animate-spin" /> : <Check size={18} />}
            {isSubmitting ? "Saving..." : "Verify & Resolve"}
          </button>
        </div>
      </motion.div>
    </div>
  );
};
