"use client";

import React from "react";
import { Navbar } from "@/components/Navbar";
import { Uploader } from "@/components/Uploader";
import { motion } from "framer-motion";
import { ShieldCheck, Zap, Database, CheckCircle, ArrowRight, Building2, Landmark, Briefcase, FileCheck2 } from "lucide-react";
import { useAuth } from "@/components/AuthContext";
import Link from "next/link";

import { ContactSupportButton } from "@/components/ContactSupportButton";

export default function Home() {
  const { user, isLoading } = useAuth();

  if (isLoading) return null;

  return (
    <main>
      <Navbar />
      
      {/* ALWAYS SHOW HERO SECTION */}
      <div className="hero" style={{ minHeight: "auto", paddingTop: "10rem", paddingBottom: "2rem" }}>
        <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} className="badge glass">
          <Zap size={14} /> AI-Powered Compliance Automation
        </motion.div>
        
        <h1 className="hero-title">
          Your Digital <span className="text-gradient">Financial Auditor</span>
        </h1>
        <p className="hero-subtitle">
          Extract, validate, and reconcile Indian tax documents with AI-assisted workflows built for real compliance operations.
        </p>

        <div className="cta-group">
          <Link href={user ? "#uploader" : "/auth/signup"} className="btn btn-primary">Start Auditing Now <ArrowRight size={18} /></Link>
        </div>
      </div>

      <section className="info-shell">
        <motion.div
          className="info-block glass info-animated"
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5 }}
        >
          <p className="info-eyebrow">What Taxyn Does</p>
          <h2 className="info-title">From Documents to Decision-Ready Data</h2>
          <p className="info-copy">
            Taxyn reads compliance documents, extracts structured fields, validates core tax rules, and flags uncertain outputs for human review.
            It also stores history and corrections so teams can audit decisions and improve extraction quality over time.
          </p>
          <div className="info-grid">
            <div className="info-card">
              <FileCheck2 size={18} />
              <h3>Structured Extraction</h3>
              <p>Invoice, GST, bank, TDS, and reconciliation-specific fields.</p>
            </div>
            <div className="info-card">
              <ShieldCheck size={18} />
              <h3>Digital Integrity Audit</h3>
              <p>Cryptographic QR decoding to verify IRN and prevent invoice tampering.</p>
            </div>
            <div className="info-card">
              <Database size={18} />
              <h3>Audit + Learning</h3>
              <p>Request trace history and correction memory for repeat accuracy.</p>
            </div>
          </div>
        </motion.div>

        <motion.div
          className="info-block glass info-animated"
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.55, delay: 0.05 }}
        >
          <p className="info-eyebrow">Who It’s For</p>
          <h2 className="info-title">Built for Compliance and Finance Operations</h2>
          <div className="persona-grid">
            <div className="persona-pill"><Briefcase size={16} /> CA & Tax Firms</div>
            <div className="persona-pill"><Building2 size={16} /> Finance Teams</div>
            <div className="persona-pill"><Landmark size={16} /> Audit & Internal Control</div>
            <div className="persona-pill"><CheckCircle size={16} /> Shared Service Centers</div>
          </div>
        </motion.div>

        <motion.div
          className="info-block glass info-animated"
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6, delay: 0.1 }}
        >
          <p className="info-eyebrow">How It Works</p>
          <h2 className="info-title">5-Step Processing Flow</h2>
          <div className="flow-grid">
            <div className="flow-step"><span>01</span>Upload PDF/Excel</div>
            <div className="flow-step"><span>02</span>Extract + Parse Fields</div>
            <div className="flow-step"><span>03</span>Run Rule Validation</div>
            <div className="flow-step"><span>04</span>Score Confidence</div>
            <div className="flow-step"><span>05</span>Complete or Send to Review</div>
          </div>
        </motion.div>

        <div className="hero" style={{ minHeight: "auto", paddingTop: "1rem", paddingBottom: "8rem" }}>
          <div style={{ display: "flex", gap: "3rem", opacity: 0.7, flexWrap: "wrap", justifyContent: "center" }}>
            <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}><CheckCircle size={18} /> GSTR-2A Matching</div>
            <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}><CheckCircle size={18} /> Bank Scrutiny</div>
            <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}><CheckCircle size={18} /> Vendor Memory</div>
          </div>
        </div>
      </section>

      {/* ALWAYS SHOW UPLOADER (LOGIN GUARD HANDLED INSIDE) */}
      <div id="uploader" style={{ display: "flex", justifyContent: "center", paddingBottom: "3rem" }}>
        <Uploader />
      </div>

      <footer className="marketing-footer">
        <div className="footer-grid">
          <div className="footer-cell">
            <h4>Use Cases</h4>
            <p>Invoice audit, GST checks, bank scrutiny, TDS verification, and portal reconciliation.</p>
          </div>
          <div className="footer-cell">
            <h4>Core Capabilities</h4>
            <p>Structured extraction, deterministic validation, confidence routing, and review workflows.</p>
          </div>
          <div className="footer-cell">
            <h4>Who Uses Taxyn</h4>
            <p>CA firms, finance operations, internal audit teams, and compliance-focused organizations.</p>
          </div>
        </div>
        <div className="footer-bottom">
          <div style={{ display: "flex", gap: "1.5rem", alignItems: "center" }}>
            {!user && <Link href="/auth/signup" className="footer-link">Start Free</Link>}
            {user && <span className="footer-link">Secure AI Workflow</span>}
            <ContactSupportButton className="footer-link">Contact Support</ContactSupportButton>
          </div>
          <p className="footer-meta">Built for Indian financial documentation</p>
        </div>
      </footer>
    </main>
  );
}
