import React from "react";
import { AbsoluteFill } from "remotion";
import { Starfield } from "./Starfield";

// 深色宇宙底：径向渐变 + 多团星云光斑(blur) + 三层星空 + 暗角 + film grain
export const SpaceBackground: React.FC<{ children?: React.ReactNode }> = ({ children }) => {
  return (
    <AbsoluteFill
      style={{
        background:
          "radial-gradient(ellipse at 50% 28%, #1f1f48 0%, #10102a 45%, #05050e 100%)",
      }}
    >
      {/* Nebula clouds — 更厚、更多，逼近参考图的紫色弥散 */}
      <div
        style={{
          position: "absolute",
          left: "6%",
          top: "4%",
          width: "88%",
          height: "58%",
          borderRadius: "50%",
          filter: "blur(150px)",
          background: "radial-gradient(circle, rgba(124,90,225,0.34), transparent 70%)",
        }}
      />
      <div
        style={{
          position: "absolute",
          left: "-6%",
          bottom: "6%",
          width: "74%",
          height: "52%",
          borderRadius: "50%",
          filter: "blur(150px)",
          background: "radial-gradient(circle, rgba(42,134,232,0.24), transparent 70%)",
        }}
      />
      <div
        style={{
          position: "absolute",
          right: "8%",
          top: "38%",
          width: "44%",
          height: "32%",
          borderRadius: "50%",
          filter: "blur(120px)",
          background: "radial-gradient(circle, rgba(186,96,206,0.18), transparent 70%)",
        }}
      />
      <Starfield seed="space" />
      {/* 暗角 */}
      <div
        style={{
          position: "absolute",
          left: 0,
          top: 0,
          right: 0,
          bottom: 0,
          background:
            "radial-gradient(circle at 50% 50%, transparent 45%, rgba(0,0,0,0.65) 100%)",
        }}
      />
      {/* Film grain — 极淡的噪点贴一层，"电影颗粒" */}
      <div
        style={{
          position: "absolute",
          left: 0,
          top: 0,
          right: 0,
          bottom: 0,
          opacity: 0.055,
          pointerEvents: "none",
          mixBlendMode: "overlay",
        }}
      >
        <svg width="100%" height="100%">
          <filter id="space-grain">
            <feTurbulence type="fractalNoise" baseFrequency="0.85" numOctaves="2" stitchTiles="stitch" />
          </filter>
          <rect width="100%" height="100%" filter="url(#space-grain)" />
        </svg>
      </div>
      {children}
    </AbsoluteFill>
  );
};
