import React from "react";
import {
  useCurrentFrame,
  interpolate,
  spring,
  useVideoConfig,
  Easing,
} from "remotion";
import { SpaceBackground } from "./SpaceBackground";
import { PALETTE, TYPE, AccentBar } from "./theme";

// —— 立体柱状图 ——
// 主题示例：全球 Top 5 国家 GDP 2023
// 中/美/日/德/印   单位：万亿美元

const W = 900;
const H = 580;
const PAD = { top: 80, right: 60, bottom: 88, left: 96 };
const DEPTH = 28; // 柱体 3D 厚度

export interface BarChart3DProps {
  title: string;
  subtitle: string;
  captionHi: string;
  captionSub: string;
  categories: string[];
  values: number[];                // 与 categories 同长
  unit?: string;                   // Y 轴单位（写入副标题）
  maxValue?: number;
  yTicks?: number;                 // Y 轴几段（默认 5）
  accent?: string;                 // 柱顶到柱底的渐变起点（默认蓝）
  accent2?: string;                // 渐变终点（默认青）
  timeOffset?: number;
}

export const BarChart3D: React.FC<BarChart3DProps> = ({
  title,
  subtitle,
  captionHi,
  captionSub,
  categories,
  values,
  unit = "",
  maxValue,
  yTicks = 5,
  accent = "#4f7ff0",
  accent2 = "#36b8c4",
  timeOffset = 0,
}) => {
  const frame = useCurrentFrame() - timeOffset;
  const { fps } = useVideoConfig();

  const computedMax = maxValue ?? Math.ceil(Math.max(...values) / 10) * 10;
  const plotW = W - PAD.left - PAD.right;
  const slot = plotW / categories.length;
  const barW = Math.min(96, slot * 0.55);
  const plotTop = PAD.top;
  const plotBottom = H - PAD.bottom;
  const plotH = plotBottom - plotTop;

  const yFor = (v: number) => plotTop + plotH * (1 - v / computedMax);
  const ticks = Array.from({ length: yTicks + 1 }, (_, i) => (computedMax / yTicks) * i);

  // 整体纸面进入
  const tiltIn = spring({ frame, fps, config: { damping: 16, stiffness: 120, mass: 0.9 } });
  const rotateX = interpolate(tiltIn, [0, 1], [70, 56]);
  const rotateY = interpolate(tiltIn, [0, 1], [-12, -3]);
  const scale = interpolate(tiltIn, [0, 1], [1.2, 1.02]);
  const planeOpacity = interpolate(frame, [0, 18], [0, 1], { extrapolateRight: "clamp" });
  const float = Math.sin(frame / 46) * 7;

  // 标题/字幕
  const titleY = interpolate(frame, [8, 28], [-26, 0], { extrapolateRight: "clamp" });
  const titleOp = interpolate(frame, [8, 24], [0, 1], { extrapolateRight: "clamp" });
  const captionY = interpolate(frame, [148, 178], [46, 0], { extrapolateRight: "clamp" });
  const captionOp = interpolate(frame, [148, 174], [0, 1], { extrapolateRight: "clamp" });

  return (
    <SpaceBackground>
      {/* 标题 */}
      <div
        style={{
          position: "absolute",
          top: 178,
          left: 0,
          right: 0,
          textAlign: "center",
          color: PALETTE.ink,
          fontSize: TYPE.titleHi,
          fontWeight: 800,
          letterSpacing: 3,
          opacity: titleOp,
          transform: `translateY(${titleY}px)`,
          textShadow:
            "0 0 28px rgba(90,120,255,0.55), 0 4px 20px rgba(0,0,0,0.6)",
        }}
      >
        {title}
      </div>
      <div
        style={{
          position: "absolute",
          top: 258,
          left: 0,
          right: 0,
          textAlign: "center",
          color: PALETTE.inkMuted,
          fontSize: TYPE.titleSub,
          letterSpacing: 2,
          opacity: interpolate(frame, [16, 36], [0, 1], { extrapolateRight: "clamp" }),
        }}
      >
        {unit} · {subtitle}
      </div>

      {/* 3D 舞台 */}
      <div
        style={{
          position: "absolute",
          top: 540,
          left: 0,
          width: "100%",
          display: "flex",
          justifyContent: "center",
          alignItems: "center",
          perspective: 900,
        }}
      >
        <div
          style={{
            width: W,
            height: H,
            transform: `rotateX(${rotateX}deg) rotateY(${rotateY}deg) scale(${scale}) translateY(${float}px)`,
            transformStyle: "preserve-3d",
            opacity: planeOpacity,
            background: PALETTE.paperBg,
            borderRadius: 18,
            boxShadow:
              "0 90px 150px rgba(0,0,0,0.75), 0 30px 60px rgba(0,0,0,0.5), inset 0 1px 0 rgba(255,255,255,0.9)",
            padding: 22,
          }}
        >
          <svg width={W} height={H} viewBox={`0 0 ${W} ${H}`}>
            <defs>
              <linearGradient id="barFront" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor={accent} />
                <stop offset="100%" stopColor={accent2} />
              </linearGradient>
              <linearGradient id="barSide" x1="0" y1="0" x2="1" y2="0">
                <stop offset="0%" stopColor={accent2} stopOpacity={0.7} />
                <stop offset="100%" stopColor={accent2} stopOpacity={0.35} />
              </linearGradient>
              <linearGradient id="barTop" x1="0" y1="0" x2="1" y2="0">
                <stop offset="0%" stopColor="#ffffff" stopOpacity={0.85} />
                <stop offset="100%" stopColor="#ffffff" stopOpacity={0.5} />
              </linearGradient>
            </defs>

            {/* 水平网格 + Y 刻度 */}
            {ticks.map((v) => {
              const y = yFor(v);
              return (
                <g key={`yt-${v}`}>
                  <line
                    x1={PAD.left}
                    y1={y}
                    x2={W - PAD.right}
                    y2={y}
                    stroke={PALETTE.paperGrid}
                    strokeWidth={1}
                  />
                  <text
                    x={PAD.left - 14}
                    y={y + 4}
                    textAnchor="end"
                    fill={PALETTE.paperInkMuted}
                    fontSize={TYPE.paperAxis}
                  >
                    {Math.round(v)}
                  </text>
                </g>
              );
            })}

            {/* X 轴底线 */}
            <line
              x1={PAD.left}
              y1={plotBottom}
              x2={W - PAD.right}
              y2={plotBottom}
              stroke={PALETTE.paperAxis}
              strokeWidth={2}
            />

            {/* 柱子 */}
            {categories.map((cat, i) => {
              const v = values[i];
              const cx = PAD.left + slot * (i + 0.5);
              const x0 = cx - barW / 2;
              const x1 = cx + barW / 2;
              const fullH = (v / computedMax) * plotH;
              const baseY = plotBottom;
              // 错峰上升：每根柱子在前一根弹出后开始
              const startFrame = 36 + i * 8;
              const inSpring = spring({
                frame: frame - startFrame,
                fps,
                config: { damping: 14, stiffness: 130, mass: 0.7 },
              });
              const h = Math.max(0, fullH * inSpring);
              const top = baseY - h;
              // 立体偏移
              const dx = DEPTH * 0.55;
              const dy = -DEPTH * 0.45;
              // 数值
              const valLabelY = top - 16;
              const valOp = interpolate(frame - startFrame, [10, 22], [0, 1], {
                extrapolateRight: "clamp",
              });

              return (
                <g key={`bar-${cat}`}>
                  {/* 侧面（深色，3D 厚度） */}
                  <polygon
                    points={`${x1},${baseY} ${x1 + dx},${baseY + dy} ${x1 + dx},${top + dy} ${x1},${top}`}
                    fill="url(#barSide)"
                  />
                  {/* 顶面（高光） */}
                  <polygon
                    points={`${x0},${top} ${x1},${top} ${x1 + dx},${top + dy} ${x0 + dx},${top + dy}`}
                    fill="url(#barTop)"
                  />
                  {/* 正面（渐变） */}
                  <rect
                    x={x0}
                    y={top}
                    width={barW}
                    height={h}
                    fill="url(#barFront)"
                    rx={6}
                  />
                  {/* 柱顶高光横线（强化"立体上沿"） */}
                  <line
                    x1={x0}
                    y1={top + 2}
                    x2={x1}
                    y2={top + 2}
                    stroke="rgba(255,255,255,0.6)"
                    strokeWidth={2}
                  />
                  {/* 数值 */}
                  <text
                    x={cx + dx / 2}
                    y={valLabelY + dy}
                    textAnchor="middle"
                    fill={PALETTE.paperInk}
                    fontSize={22}
                    fontWeight={700}
                    opacity={valOp}
                  >
                    {v}
                  </text>
                  {/* 类别 */}
                  <text
                    x={cx}
                    y={plotBottom + 32}
                    textAnchor="middle"
                    fill={PALETTE.paperInk}
                    fontSize={20}
                    fontWeight={600}
                  >
                    {cat}
                  </text>
                </g>
              );
            })}
          </svg>
        </div>
      </div>

      {/* 底部字幕 */}
      <div
        style={{
          position: "absolute",
          bottom: 230,
          left: 0,
          right: 0,
          textAlign: "center",
          opacity: captionOp,
          transform: `translateY(${captionY}px)`,
        }}
      >
        <div
          style={{
            fontWeight: 800,
            fontSize: TYPE.captionHi,
            color: PALETTE.ink,
            textShadow: "0 0 24px rgba(120,160,255,0.6)",
          }}
        >
          {captionHi}
        </div>
        <div
          style={{
            marginTop: 12,
            fontSize: TYPE.captionSub,
            color: "rgba(255,255,255,0.66)",
            letterSpacing: 1,
          }}
        >
          {captionSub}
        </div>
        <AccentBar />
      </div>
    </SpaceBackground>
  );
};
