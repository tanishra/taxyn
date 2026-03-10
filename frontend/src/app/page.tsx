"use client";

import { motion } from "framer-motion";
import { Navbar } from "@/components/Navbar";
import { Uploader } from "@/components/Uploader";
import { Sparkles, Shield, Zap, CheckCircle } from "lucide-react";
import "./ui.css";

export default function Home() {
  return (
    <main>
      <Navbar />
      
      <section className="hero">
        <motion.div 
          initial={{ opacity: 0, scale: 0.9 }}
          animate={{ opacity: 1, scale: 1 }}
          className="badge glass"
        >
          <Sparkles size={14} color="var(--primary)" />
          <span>AI-Powered Indian Compliance</span>
        </motion.div>

        <motion.h1 
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.1 }}
          className="hero-title"
        >
          Automate Your <span className="text-gradient">Tax Compliance</span> Workflow
        </motion.h1>

        <motion.p 
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.2 }}
          className="hero-subtitle"
        >
          Extract structured data from Invoices, GST Returns, and Bank Statements with 99% accuracy and built-in Indian compliance validation.
        </motion.p>

        <motion.div 
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.3 }}
          className="cta-group"
        >
          <button className="btn btn-primary">
            Start Free Trial
          </button>
          <button className="btn btn-secondary">
            View Documentation
          </button>
        </motion.div>

        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ delay: 0.5 }}
          style={{ display: "flex", gap: "3rem", marginBottom: "4rem" }}
        >
          <div style={{ display: "flex", alignItems: "center", gap: "0.5rem", color: "rgba(255,255,255,0.4)" }}>
            <Shield size={18} /> Secure & Encrypted
          </div>
          <div style={{ display: "flex", alignItems: "center", gap: "0.5rem", color: "rgba(255,255,255,0.4)" }}>
            <Zap size={18} /> 30x Faster than OCR
          </div>
          <div style={{ display: "flex", alignItems: "center", gap: "0.5rem", color: "rgba(255,255,255,0.4)" }}>
            <CheckCircle size={18} /> 99.9% Extraction Accuracy
          </div>
        </motion.div>

        <Uploader />
      </section>

      {/* Decorative background elements */}
      <div style={{
        position: "fixed",
        top: "10%",
        right: "5%",
        width: "300px",
        height: "300px",
        background: "var(--primary)",
        filter: "blur(150px)",
        opacity: 0.1,
        zIndex: -1,
        borderRadius: "50%"
      }} />
      <div style={{
        position: "fixed",
        bottom: "10%",
        left: "5%",
        width: "400px",
        height: "400px",
        background: "var(--secondary)",
        filter: "blur(180px)",
        opacity: 0.08,
        zIndex: -1,
        borderRadius: "50%"
      }} />
    </main>
  );
}
