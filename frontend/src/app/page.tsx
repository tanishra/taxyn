"use client";

import React from "react";
import { Navbar } from "@/components/Navbar";
import { Uploader } from "@/components/Uploader";
import { motion } from "framer-motion";
import { ShieldCheck, Zap, Database, CheckCircle, ArrowRight } from "lucide-react";
import { useAuth } from "@/components/AuthContext";
import Link from "next/link";

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
          Extract, validate, and reconcile Indian tax documents with 99% accuracy using autonomous AI agents.
        </p>

        {!user && (
          <div className="cta-group">
            <Link href="/auth/signup" className="btn btn-primary">Start Auditing Now <ArrowRight size={18} /></Link>
          </div>
        )}
      </div>

      {/* ALWAYS SHOW UPLOADER (LOGIN GUARD HANDLED INSIDE) */}
      <div style={{ display: "flex", justifyContent: "center", paddingBottom: "8rem" }}>
        <Uploader />
      </div>

      {!user && (
        <div className="hero" style={{ minHeight: "auto", paddingBottom: "8rem" }}>
          <div style={{ display: "flex", gap: "3rem", opacity: 0.6 }}>
            <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}><CheckCircle size={18} /> GSTR-2A Matching</div>
            <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}><CheckCircle size={18} /> Bank Scrutiny</div>
            <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}><CheckCircle size={18} /> Vendor Memory</div>
          </div>
        </div>
      )}
    </main>
  );
}
