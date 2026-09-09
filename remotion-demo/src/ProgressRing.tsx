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

// —— 同心环 / KPI 进度环 ——
// 主题示例：中国一次能源消费结构（4 类: 煤炭/石油/天然气/可再生能源）

export interface ProgressRingItem {
  label: string;
  value: number;       // 0–1 占比（自动归一）
  color: string;
}

export interface ProgressRingProps {
  title: string;
  subtitle: string;
  captionHi: string;
  captionSub: string;
  items: ProgressRingItem[];   // 4–6 段
  centerLabel: string;
  centerValue: string;
  timeOffset?: number;
}

const PAPER_W = 980;
const PAPER_H = 540;
const CX = 360;
const CY = 270;
const R_OUTER = 200;

// 弧线 path（圆环）
function ringPath(
  cx: number,
  cy: number,
  r: number,
  start: number,
  end: number,
): string {
  const a0 = start - Math.PI / 2;
  const a1 = end - Math.PI / 2;
  const x0 = cx + r * Math.cos(a0);
  const y0 = cy + r * Math.sin(a0);
  const x1 = cx + r * Math.cos(a1);
  const y1 = cy + r * Math.sin(a1);
  const largeArc = end - start <= Math.PI ? 0 : 1;
  return `M ${x0.toFixed(1)} ${y0.toFixed(1)} A ${r} ${r} 0 ${largeArc} 1 ${x1.toFixed(1)} ${y1.toFixed(1)}`;
}

export const ProgressRing: React.FC<ProgressRingProps> = ({
  title,
  subtitle,
  captionHi,
  captionSub,
  items,
  centerLabel,
  centerValue,
  timeOffset = 0,
}) => {
  const frame = useCurrentFrame() - timeOffset;
  const { fps } = useVideoConfig();

  const tiltIn = spring({ frame, fps, config: { damping: 16, stiffness: 120, mass: 0.9 } });
  const rotateX = interpolate(tiltIn, [0, 1], [70, 60]);
  const rotateY = interpolate(tiltIn, [0, 1], [-12, -5]);
  const scale = interpolate(tiltIn, [0, 1], [1.18, 1.02]);
  const planeOpacity = interpolate(frame, [0, 18], [0, 1], { extrapolateRight: "clamp" });
  const float = Math.sin(frame / 46) * 7;

  const titleY = interpolate(frame, [8, 28], [-26, 0], { extrapolateRight: "clamp" });
  const titleOp = interpolate(frame, [8, 24], [0, 1], { extrapolateRight: "clamp" });
  const captionY = interpolate(frame, [180, 210], [46, 0], { extrapolateRight: "clamp" });
  const captionOp = interpolate(frame, [180, 206], [0, 1], { extrapolateRight: "clamp" });

  const total = items.reduce((s, x) => s + x.value, 0);
  const ratios = items.map((s) => s.value / total);

  // 中心大数字滚动
  const centerValNum = parseFloat(centerValue);
  const numDisplay = Number.isFinite(centerValNum)
    ? interpolate(frame, [60, 130], [0, centerValNum], {
        extrapolateRight: "clamp",
        easing: Easing.out(Easing.cubic),
      }).toFixed(0)
    : centerValue;

  // 段错峰 + 段内扫
  let cursor = 0;
  const segStartBase = 36;
  const segGap = 8;

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
        {subtitle}
      </div>

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
            width: PAPER_W,
            height: PAPER_H,
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
          <svg width={PAPER_W} height={PAPER_H} viewBox={`0 0 ${PAPER_W} ${PAPER_H}`}>
            {/* 背景轨道（全灰） */}
            <circle
              cx={CX}
              cy={CY}
              r={R_OUTER}
              fill="none"
              stroke="rgba(0,0,0,0.06)"
              strokeWidth={52}
            />
            {/* 各段 */}
            {items.map((it, i) => {
              const startA = cursor;
              const endA = cursor + ratios[i] * Math.PI * 2 - 0.04;
              cursor += ratios[i] * Math.PI * 2;
              const begin = segStartBase + i * segGap;
              const sw = spring({
                frame: frame - begin,
                fps,
                config: { damping: 14, stiffness: 100, mass: 0.8 },
              });
              const sweepLen = (endA - startA) * Math.max(0, sw);
              return (
                <path
                  key={`seg-${it.label}`}
                  d={ringPath(CX, CY, R_OUTER, startA, startA + sweepLen)}
                  stroke={it.color}
                  strokeWidth={52}
                  strokeLinecap="butt"
                  fill="none"
                  style={{
                    filter: "drop-shadow(0 0 16px rgba(255,255,255,0.5))",
                  }}
                />
              );
            })}
            {/* 内圈描边 */}
            <circle
              cx={CX}
              cy={CY}
              r={R_OUTER - 26}
              fill="none"
              stroke="rgba(0,0,0,0.04)"
              strokeWidth={1}
            />
            {/* 中心数字 */}
            <text
              x={CX}
              y={CY - 6}
              textAnchor="middle"
              fill="rgba(0,0,0,0.5)"
              fontSize={20}
              fontWeight={500}
              letterSpacing={2}
            >
              {centerLabel}
            </text>
            <text
              x={CX}
              y={CY + 56}
              textAnchor="middle"
              fill={PALETTE.paperInk}
              fontSize={56}
              fontWeight={800}
            >
              {numDisplay}
            </text>

            {/* 右侧图例 */}
            <g
              style={{
                opacity: interpolate(frame, [60, 90], [0, 1], {
                  extrapolateRight: "clamp",
                }),
              }}
            >
              {items.map((it, i) => {
                const x = 660;
                const y = 110 + i * 64;
                return (
                  <g key={`pl-${it.label}`}>
                    <rect width={20} height={20} x={x} y={y} rx={5} fill={it.color} />
                    <text
                      x={x + 32}
                      y={y + 16}
                      fill={PALETTE.paperInk}
                      fontSize={22}
                      fontWeight={600}
                    >
                      {it.label}
                    </text>
                    <text
                      x={x + 260}
                      y={y + 16}
                      fill={PALETTE.paperInkMuted}
                      fontSize={22}
                      fontWeight={700}
                      textAnchor="end"
                    >
                      {(ratios[i] * 100).toFixed(0)}%
                    </text>
                  </g>
                );
              })}
            </g>
          </svg>
        </div>
      </div>

      {/* 字幕 */}
      <div
        style={{
          position: "absolute",
          bottom: 220,
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
