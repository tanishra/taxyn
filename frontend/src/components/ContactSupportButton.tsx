"use client";

import React, { useEffect, useMemo, useState } from "react";
import axios from "axios";
import { MessageSquareWarning, Send, X, Mail, Globe, Clock, ArrowRight } from "lucide-react";
import { useAuth } from "@/components/AuthContext";
import { createPortal } from "react-dom";
import { motion, AnimatePresence } from "framer-motion";
import { apiUrl } from "@/lib/api";

type ContactSupportButtonProps = {
  className?: string;
  children?: React.ReactNode;
};

export function ContactSupportButton({ className = "footer-contact-btn", children }: ContactSupportButtonProps) {
  const { user } = useAuth();
  const [mounted, setMounted] = useState(false);
  const [open, setOpen] = useState(false);
  const [subject, setSubject] = useState("");
  const [message, setMessage] = useState("");
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [sending, setSending] = useState(false);
  const [notice, setNotice] = useState("");

  const resolvedName = useMemo(() => (name || user?.full_name || "").trim(), [name, user?.full_name]);
  const resolvedEmail = useMemo(() => (email || user?.email || "").trim(), [email, user?.email]);

  useEffect(() => {
    setMounted(true);
  }, []);

  const resetForm = () => {
    setSubject("");
    setMessage("");
    setName("");
    setEmail("");
    setNotice("");
  };

  const handleClose = () => {
    setOpen(false);
    resetForm();
  };

  const handleSend = async () => {
    if (!subject.trim() || !message.trim()) {
      setNotice("Please add both subject and message.");
      return;
    }
    if (!resolvedEmail) {
      setNotice("Please add your email.");
      return;
    }

    setSending(true);
    setNotice("");
    try {
      const formData = new FormData();
      formData.append("subject", subject.trim());
      formData.append("message", message.trim());
      formData.append("name", resolvedName);
      formData.append("email", resolvedEmail);

      const token = localStorage.getItem("token");
      await axios.post(apiUrl("/api/v1/contact"), formData, {
        headers: token ? { Authorization: `Bearer ${token}` } : undefined,
      });

      setNotice("Message sent successfully.");
      setTimeout(() => {
        handleClose();
      }, 1500);
    } catch {
      setNotice("Failed to send. Please try again.");
    } finally {
      setSending(false);
    }
  };

  const toggleModal = (e: React.MouseEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setOpen(true);
  };

  return (
    <>
      <button 
        type="button" 
        className={className} 
        onClick={toggleModal}
        style={{ 
          cursor: "pointer", 
          pointerEvents: "auto", 
          position: "relative",
          zIndex: 10 
        }}
      >
        {children ? children : (
          <>
            <MessageSquareWarning size={18} />
            Contact
          </>
        )}
      </button>

      {mounted && typeof document !== "undefined" && createPortal(
        <AnimatePresence>
          {open && (
            <div className="contact-modal-backdrop" style={{ zIndex: 99999 }} onClick={handleClose}>
              <motion.div 
                className="contact-modal-card glass" 
                onClick={(e) => e.stopPropagation()}
                initial={{ opacity: 0, y: 30, scale: 0.98 }}
                animate={{ opacity: 1, y: 0, scale: 1 }}
                exit={{ opacity: 0, y: 20, scale: 0.98 }}
                transition={{ type: "spring", damping: 25, stiffness: 300 }}
              >
                <button type="button" className="contact-close-btn" onClick={handleClose} aria-label="Close">
                  <X size={18} />
                </button>
                
                <div className="contact-modal-layout">
                  <aside className="contact-panel">
                    <div className="contact-header">
                      <span className="contact-kicker">Get in touch</span>
                      <h2 className="text-gradient">How can we help?</h2>
                      <p>Have questions about Taxyn or need technical assistance? Our team is here to support your compliance journey.</p>
                    </div>

                    <div className="contact-info-list">
                      <div className="contact-info-item">
                        <div className="contact-info-icon"><Mail size={16} /></div>
                        <div>
                          <label>Email Support</label>
                          <p>tanishrajput9@gmail.com</p>
                        </div>
                      </div>
                      <div className="contact-info-item">
                        <div className="contact-info-icon"><Clock size={16} /></div>
                        <div>
                          <label>Average Response</label>
                          <p>Under 24 hours</p>
                        </div>
                      </div>
                      <div className="contact-info-item">
                        <div className="contact-info-icon"><Globe size={16} /></div>
                        <div>
                          <label>Availability</label>
                          <p>Mon - Fri, 9AM - 6PM IST</p>
                        </div>
                      </div>
                    </div>
                  </aside>

                  <div className="contact-main">
                    <div className="contact-form-container">
                      <div className="contact-form-grid">
                        <div className="input-group">
                          <label>Name</label>
                          <input
                            type="text"
                            placeholder="John Doe"
                            value={name || user?.full_name || ""}
                            onChange={(e) => setName(e.target.value)}
                          />
                        </div>
                        <div className="input-group">
                          <label>Email</label>
                          <input
                            type="email"
                            placeholder="john@example.com"
                            value={email || user?.email || ""}
                            onChange={(e) => setEmail(e.target.value)}
                          />
                        </div>
                        <div className="input-group full-width">
                          <label>Subject</label>
                          <input
                            type="text"
                            placeholder="How can we help?"
                            value={subject}
                            onChange={(e) => setSubject(e.target.value)}
                          />
                        </div>
                        <div className="input-group full-width">
                          <label>Message</label>
                          <textarea
                            placeholder="Tell us more about your inquiry..."
                            value={message}
                            onChange={(e) => setMessage(e.target.value)}
                          />
                        </div>
                      </div>

                      <div className="contact-actions">
                        {notice && <span className={`contact-notice ${notice.includes("successfully") ? "success" : "error"}`}>{notice}</span>}
                        <button 
                          type="button" 
                          className="btn-primary contact-send-btn" 
                          onClick={handleSend} 
                          disabled={sending}
                        >
                          {sending ? "Sending..." : "Send Message"}
                          <ArrowRight size={18} />
                        </button>
                      </div>
                    </div>
                  </div>
                </div>
              </motion.div>
            </div>
          )}
        </AnimatePresence>,
        document.body
      )}
    </>
  );
}
