"use client";

import React, { createContext, useContext, useState, useEffect, useCallback } from "react";
import axios from "axios";
import { useRouter } from "next/navigation";
import { apiUrl } from "@/lib/api";

interface User {
  id: string;
  email: string;
  full_name: string;
  company_name?: string;
  gstin?: string;
  contact_phone?: string;
  designation?: string;
  company_pan?: string;
  address_line1?: string;
  city?: string;
  state?: string;
  pincode?: string;
  is_admin?: boolean;
}

interface AuthContextType {
  user: User | null;
  token: string | null;
  login: (token: string) => void;
  logout: () => void;
  refreshProfile: () => Promise<void>;
  isLoading: boolean;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export const AuthProvider = ({ children }: { children: React.ReactNode }) => {
  const [user, setUser] = useState<User | null>(null);
  const [token, setToken] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const router = useRouter();

  const logout = useCallback(() => {
    localStorage.removeItem("taxyn_token");
    setToken(null);
    setUser(null);
    router.push("/auth/login");
  }, [router]);

  const fetchProfile = useCallback(async (t: string) => {
    try {
      const res = await axios.get(apiUrl("/api/v1/auth/me"), {
        headers: { Authorization: `Bearer ${t}` }
      });
      setUser(res.data);
    } catch {
      logout();
    } finally {
      setIsLoading(false);
    }
  }, [logout]);

  useEffect(() => {
    const savedToken = localStorage.getItem("taxyn_token");
    if (savedToken) {
      setToken(savedToken);
      void fetchProfile(savedToken);
    } else {
      setIsLoading(false);
    }
  }, [fetchProfile]);

  const login = useCallback((newToken: string) => {
    localStorage.setItem("taxyn_token", newToken);
    setToken(newToken);
    void fetchProfile(newToken);
    router.push("/");
  }, [fetchProfile, router]);

  const refreshProfile = useCallback(async () => {
    if (!token) return;
    await fetchProfile(token);
  }, [fetchProfile, token]);

  return (
    <AuthContext.Provider value={{ user, token, login, logout, refreshProfile, isLoading }}>
      {children}
    </AuthContext.Provider>
  );
};

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (!context) throw new Error("useAuth must be used within AuthProvider");
  return context;
};
