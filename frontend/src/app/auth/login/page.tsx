"use client";

import React, { useState, useEffect, Suspense } from "react";
import { motion } from "framer-motion";
import { Mail, Lock, ArrowRight, ShieldCheck, AlertCircle, CheckCircle } from "lucide-react";
import { useAuth } from "@/components/AuthContext";
import { useGoogleLogin } from "@react-oauth/google";
import axios from "axios";
import Link from "next/link";
import { useSearchParams, useRouter } from "next/navigation";

interface ApiError {
  response?: {
    data?: {
      detail?: string;
    };
  };
}

function LoginContent() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const { login, user } = useAuth();
  const searchParams = useSearchParams();
  const router = useRouter();

  useEffect(() => {
    if (user) router.push("/");
  }, [user, router]);

  useEffect(() => {
    const err = searchParams.get("error");
    if (err) setError(err);
    
    // Check for verification success
    if (searchParams.get("verified")) {
      setSuccess("Email verified! Please sign in to continue.");
    }
  }, [searchParams]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsLoading(true);
    setError("");
    setSuccess("");

    const formData = new FormData();
    formData.append("username", email);
    formData.append("password", password);

    try {
      const res = await axios.post("http://localhost:8000/api/v1/auth/login", formData);
      login(res.data.access_token);
    } catch (err: unknown) {
      const apiErr = err as ApiError;
      setError(apiErr.response?.data?.detail || "Login failed. Check your credentials.");
    } finally {
      setIsLoading(false);
    }
  };

  const googleLogin = useGoogleLogin({
    onSuccess: async (tokenResponse) => {
      setIsLoading(true);
      setError("");
      setSuccess("");
      try {
        const formData = new FormData();
        formData.append("token", tokenResponse.access_token);
        const res = await axios.post("http://localhost:8000/api/v1/auth/google", formData);
        login(res.data.access_token);
      } catch (_err) {
        setError("Google Login failed. Please try again.");
      } finally {
        setIsLoading(false);
      }
    },
    onError: () => setError("Google Sign-In was cancelled or failed.")
  });

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
            <ShieldCheck size={24} color="white" />
          </div>
          <h2 className="text-gradient" style={{ fontSize: "2rem", fontWeight: 800 }}>Welcome Back</h2>
          <p style={{ color: "rgba(255,255,255,0.5)", marginTop: "0.5rem" }}>Sign in to access your dashboard</p>
        </div>

        <form onSubmit={handleSubmit} style={{ display: "flex", flexDirection: "column", gap: "1.5rem" }}>
          {error && (
            <div style={{ 
              padding: "1rem", borderRadius: "0.75rem", background: "rgba(239, 68, 68, 0.1)", 
              border: "1px solid rgba(239, 68, 68, 0.2)", color: "var(--error)", 
              fontSize: "0.875rem", display: "flex", alignItems: "center", gap: "0.5rem" 
            }}>
              <AlertCircle size={16} /> {error}
            </div>
          )}

          {success && (
            <div style={{ 
              padding: "1rem", borderRadius: "0.75rem", background: "rgba(16, 185, 129, 0.1)", 
              border: "1px solid rgba(16, 185, 129, 0.2)", color: "var(--success)", 
              fontSize: "0.875rem", display: "flex", alignItems: "center", gap: "0.5rem" 
            }}>
              <CheckCircle size={16} /> {success}
            </div>
          )}

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
              type="password" placeholder="Password" required value={password}
              onChange={(e) => setPassword(e.target.value)}
              style={{ width: "100%", padding: "1rem 1rem 1rem 3rem", borderRadius: "1rem", background: "rgba(255,255,255,0.05)", border: "1px solid var(--glass-border)", color: "white", outline: "none" }} 
            />
          </div>

          <button className="btn btn-primary" type="submit" disabled={isLoading} style={{ width: "100%", justifyContent: "center" }}>
            {isLoading ? "Authenticating..." : "Sign In"} <ArrowRight size={18} />
          </button>
        </form>

        <div style={{ margin: "2rem 0", display: "flex", alignItems: "center", gap: "1rem" }}>
          <div style={{ flex: 1, height: "1px", background: "rgba(255,255,255,0.1)" }}></div>
          <span style={{ fontSize: "0.75rem", color: "rgba(255,255,255,0.3)", fontWeight: 700 }}>OR</span>
          <div style={{ flex: 1, height: "1px", background: "rgba(255,255,255,0.1)" }}></div>
        </div>

        <button 
          type="button"
          onClick={() => googleLogin()}
          disabled={isLoading}
          className="btn btn-secondary" 
          style={{ width: "100%", justifyContent: "center", gap: "1rem" }}
        >
          <svg width="18" height="18" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
            <path d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z" fill="#4285F4"/>
            <path d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-1 .67-2.26 1.07-3.71 1.07-2.87 0-5.3-1.94-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" fill="#34A853"/>
            <path d="M5.84 14.11c-.22-.67-.35-1.39-.35-2.11s.13-1.44.35-2.11V7.06H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.94l3.66-2.83z" fill="#FBBC05"/>
            <path d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.06l3.66 2.83c.86-2.59 3.3-4.53 6.16-4.53z" fill="#EA4335"/>
          </svg> 
          Continue with Google
        </button>

        <p style={{ textAlign: "center", marginTop: "2rem", fontSize: "0.875rem", color: "rgba(255,255,255,0.5)" }}>
          Don&apos;t have an account? <Link href="/auth/signup" style={{ color: "var(--primary)", fontWeight: 600 }}>Create Account</Link>
        </p>
      </motion.div>
    </main>
  );
}

export default function LoginPage() {
  return (
    <Suspense fallback={<div>Loading...</div>}>
      <LoginContent />
    </Suspense>
  );
}
