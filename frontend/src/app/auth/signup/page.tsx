"use client";

import React, { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { UserPlus, Mail, Lock, User, ArrowRight, ShieldCheck, KeyRound } from "lucide-react";
import axios from "axios";
import { useRouter } from "next/navigation";
import Link from "next/link";

export default function SignupPage() {
  const [step, setStep] = useState(1); // 1: Info, 2: OTP
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [fullName, setFullName] = useState("");
  const [otp, setOtp] = useState("");
  const [error, setError] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const router = useRouter();

  const handleInitiate = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsLoading(true);
    setError("");

    const formData = new FormData();
    formData.append("email", email);

    try {
      await axios.post("http://localhost:8000/api/v1/auth/signup/initiate", formData);
      setStep(2);
    } catch (err: any) {
      setError(err.response?.data?.detail || "Failed to start signup. Check your email.");
    } finally {
      setIsLoading(false);
    }
  };

  const handleVerify = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsLoading(true);
    setError("");

    const formData = new FormData();
    formData.append("email", email);
    formData.append("otp", otp);
    formData.append("password", password);
    formData.append("full_name", fullName);

    try {
      await axios.post("http://localhost:8000/api/v1/auth/signup/verify", formData);
      router.push("/auth/login?verified=true");
    } catch (err: any) {
      setError(err.response?.data?.detail || "Invalid OTP. Please check again.");
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <main className="hero">
      <motion.div 
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        className="glass"
        style={{ width: "100%", maxWidth: "450px", padding: "3rem", borderRadius: "2rem" }}
      >
        <div style={{ textAlign: "center", marginBottom: "3rem" }}>
          <div className="logo-icon" style={{ margin: "0 auto 1.5rem" }}>
            <UserPlus size={24} color="white" />
          </div>
          <h2 className="text-gradient" style={{ fontSize: "2rem", fontWeight: 800 }}>
            {step === 1 ? "Create Account" : "Verify Email"}
          </h2>
          <p style={{ color: "rgba(255,255,255,0.5)", marginTop: "0.5rem" }}>
            {step === 1 ? "Join the AI compliance platform" : `Enter the code sent to ${email}`}
          </p>
        </div>

        <AnimatePresence mode="wait">
          {step === 1 ? (
            <motion.form 
              key="step1"
              initial={{ opacity: 0, x: -20 }}
              animate={{ opacity: 1, x: 0 }}
              exit={{ opacity: 0, x: 20 }}
              onSubmit={handleInitiate} 
              style={{ display: "flex", flexDirection: "column", gap: "1.5rem" }}
            >
              <div style={{ position: "relative" }}>
                <User size={18} style={{ position: "absolute", left: "1rem", top: "50%", transform: "translateY(-50%)", opacity: 0.4 }} />
                <input 
                  type="text" placeholder="Full Name" required value={fullName}
                  onChange={(e) => setFullName(e.target.value)}
                  style={{ width: "100%", padding: "1rem 1rem 1rem 3rem", borderRadius: "1rem", background: "rgba(255,255,255,0.05)", border: "1px solid var(--glass-border)", color: "white", outline: "none" }} 
                />
              </div>
              <div style={{ position: "relative" }}>
                <Mail size={18} style={{ position: "absolute", left: "1rem", top: "50%", transform: "translateY(-50%)", opacity: 0.4 }} />
                <input 
                  type="email" placeholder="Email Address" required value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  style={{ width: "100%", padding: "1rem 1rem 1rem 3rem", borderRadius: "1rem", background: "rgba(255,255,255,0.05)", border: "1px solid var(--glass-border)", color: "white", outline: "none" }} 
                />
              </div>
              <div style={{ position: "relative" }}>
                <Lock size={18} style={{ position: "absolute", left: "1rem", top: "50%", transform: "translateY(-50%)", opacity: 0.4 }} />
                <input 
                  type="password" placeholder="Choose Password" required value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  style={{ width: "100%", padding: "1rem 1rem 1rem 3rem", borderRadius: "1rem", background: "rgba(255,255,255,0.05)", border: "1px solid var(--glass-border)", color: "white", outline: "none" }} 
                />
              </div>
              {error && <p style={{ color: "var(--error)", fontSize: "0.875rem", textAlign: "center" }}>{error}</p>}
              <button className="btn btn-primary" type="submit" disabled={isLoading} style={{ width: "100%", justifyContent: "center" }}>
                {isLoading ? "Sending OTP..." : "Continue"} <ArrowRight size={18} />
              </button>
            </motion.form>
          ) : (
            <motion.form 
              key="step2"
              initial={{ opacity: 0, x: 20 }}
              animate={{ opacity: 1, x: 0 }}
              exit={{ opacity: 0, x: -20 }}
              onSubmit={handleVerify} 
              style={{ display: "flex", flexDirection: "column", gap: "1.5rem" }}
            >
              <div style={{ position: "relative" }}>
                <KeyRound size={18} style={{ position: "absolute", left: "1rem", top: "50%", transform: "translateY(-50%)", opacity: 0.4 }} />
                <input 
                  type="text" placeholder="6-Digit OTP" required value={otp} maxLength={6}
                  onChange={(e) => setOtp(e.target.value)}
                  style={{ width: "100%", padding: "1rem 1rem 1rem 3rem", borderRadius: "1rem", background: "rgba(255,255,255,0.05)", border: "1px solid var(--glass-border)", color: "white", outline: "none", letterSpacing: "4px", fontWeight: "bold" }} 
                />
              </div>
              {error && <p style={{ color: "var(--error)", fontSize: "0.875rem", textAlign: "center" }}>{error}</p>}
              <button className="btn btn-primary" type="submit" disabled={isLoading} style={{ width: "100%", justifyContent: "center" }}>
                {isLoading ? "Verifying..." : "Verify & Sign Up"} <ShieldCheck size={18} />
              </button>
              <button type="button" onClick={() => setStep(1)} style={{ color: "var(--muted)", fontSize: "0.875rem", background: "none", border: "none", cursor: "pointer" }}>
                Edit Details
              </button>
            </motion.form>
          )}
        </AnimatePresence>

        <p style={{ textAlign: "center", marginTop: "2rem", fontSize: "0.875rem", color: "rgba(255,255,255,0.5)" }}>
          Already have an account? <Link href="/auth/login" style={{ color: "var(--primary)", fontWeight: 600 }}>Sign In</Link>
        </p>
      </motion.div>
    </main>
  );
}
