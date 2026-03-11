"use client";

import React from "react";
import { ShieldCheck, User as UserIcon, LogOut, History, LayoutDashboard } from "lucide-react";
import { useAuth } from "./AuthContext";
import Link from "next/link";

export const Navbar = () => {
  const { user, logout } = useAuth();

  return (
    <nav className="navbar glass">
      <Link href="/" className="logo">
        <div className="logo-icon">
          <ShieldCheck size={20} color="white" />
        </div>
        <span className="text-gradient">Taxyn</span>
      </Link>

      <div className="nav-links">
        {user ? (
          <>
            <Link href="/" className="nav-link"><LayoutDashboard size={18} /> Dashboard</Link>
            <Link href="/history" className="nav-link"><History size={18} /> History</Link>
            <div style={{ width: "1px", height: "20px", background: "rgba(255,255,255,0.1)" }}></div>
            <Link href="/profile" style={{ display: "flex", alignItems: "center", gap: "0.75rem", color: "#fff", cursor: "pointer" }}>
              <UserIcon size={18} />
              <span style={{ fontSize: "0.9rem", fontWeight: 600 }}>{user.full_name}</span>
            </Link>
            <button onClick={logout} className="nav-link" style={{ color: "var(--error)" }}>
              <LogOut size={18} />
            </button>
          </>
        ) : (
          <>
            <Link href="/auth/login" className="nav-link">Login</Link>
            <Link href="/auth/signup" className="btn btn-primary" style={{ padding: "0.5rem 1.25rem" }}>Get Started</Link>
          </>
        )}
      </div>
    </nav>
  );
};
