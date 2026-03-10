"use client";

import { motion } from "framer-motion";
import { Shield, LayoutDashboard, History, Settings } from "lucide-react";
import Link from "next/link";

export const Navbar = () => {
  return (
    <motion.nav 
      initial={{ y: -100, x: "-50%" }}
      animate={{ y: 0, x: "-50%" }}
      className="navbar glass"
    >
      <div className="logo">
        <div className="logo-icon">
          <Shield size={24} color="#fff" />
        </div>
        <span className="text-gradient">Taxyn</span>
      </div>

      <div className="nav-links">
        <Link href="#" className="nav-link">Features</Link>
        <Link href="#" className="nav-link">Docs</Link>
        <Link href="#" className="nav-link">Pricing</Link>
        <button className="btn btn-primary" style={{ padding: "0.5rem 1.25rem", borderRadius: "0.75rem" }}>
          Get Started
        </button>
      </div>
    </motion.nav>
  );
};
