"use client";

import { useEffect } from "react";

export function CursorGlow() {
  useEffect(() => {
    const root = document.documentElement;

    const onMove = (e: MouseEvent) => {
      root.style.setProperty("--cursor-x", `${e.clientX}px`);
      root.style.setProperty("--cursor-y", `${e.clientY}px`);
      root.style.setProperty("--cursor-glow-opacity", "1");
    };

    const onLeave = () => {
      root.style.setProperty("--cursor-glow-opacity", "0");
    };

    window.addEventListener("mousemove", onMove, { passive: true });
    window.addEventListener("mouseout", onLeave, { passive: true });

    return () => {
      window.removeEventListener("mousemove", onMove);
      window.removeEventListener("mouseout", onLeave);
    };
  }, []);

  return <div className="cursor-glow" aria-hidden="true" />;
}
