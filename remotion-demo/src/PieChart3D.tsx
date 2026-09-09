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

// —— 3D 饼图 + 中央数字 + 图例 ——
// 主题示例：全球电商市场份额（亚马逊/淘宝/京东/拼多多/其他）

export interface PieSlice {
  label: string;
  value: number;            // 0–1 占比（或 %，自动归一）
  color: string;
}

export interface PieChart3DProps {
  title: string;
  subtitle: string;
  captionHi: string;
  captionSub: string;
  slices: PieSlice[];
  centerLabel: string;      // 中间大数字上方小字
  centerValue: string;      // 中间大数字
  timeOffset?: number;
}

const PAPER_W = 980;
const PAPER_H = 540;
const CX = 300;             // 饼图中心 X（纸面内）
const CY = 290;             // 饼图中心 Y
const R = 200;              // 半径
const DEPTH = 22;           // 厚度

// SVG 弧形 path（从起点角度到终点角度，顺时针）
function arc(cx: number, cy: number, r: number, a0: number, a1: number) {
  const start = polar(cx, cy, r, a0);
  const end = polar(cx, cy, r, a1);
  const largeArc = a1 - a0 <= Math.PI ? 0 : 1;
  return `M ${start.x.toFixed(1)} ${start.y.toFixed(1)} A ${r} ${r} 0 ${largeArc} 1 ${end.x.toFixed(1)} ${end.y.toFixed(1)}`;
}
function polar(cx: number, cy: number, r: number, a: number) {
  return { x: cx + r * Math.cos(a), y: cy + r * Math.sin(a) };
}

export const PieChart3D: React.FC<PieChart3DProps> = ({
  title,
  subtitle,
  captionHi,
  captionSub,
  slices,
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
  const captionY = interpolate(frame, [160, 190], [46, 0], { extrapolateRight: "clamp" });
  const captionOp = interpolate(frame, [160, 186], [0, 1], { extrapolateRight: "clamp" });

  // 归一化
  const total = slices.reduce((s, x) => s + x.value, 0);
  const ratios = slices.map((s) => s.value / total);
  // 起始角度 -PI/2，从 12 点钟方向起
  let cursor = -Math.PI / 2;

  // 每片弧度"扫"动画
  const sliceSwpBase = 36;
  const sliceGap = 6;

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
            <defs>
              <radialGradient id="pieShine" cx="0.4" cy="0.3" r="0.6">
                <stop offset="0%" stopColor="rgba(255,255,255,0.6)" />
                <stop offset="60%" stopColor="rgba(255,255,255,0.0)" />
              </radialGradient>
            </defs>

            {/* 各扇形 + 厚度侧面 */}
            {slices.map((s, i) => {
              const ang0 = cursor;
              const ang1 = cursor + ratios[i] * Math.PI * 2;
              cursor = ang1;
              const sweepStart = sliceSwpBase + i * sliceGap;
              const sw = spring({
                frame: frame - sweepStart,
                fps,
                config: { damping: 14, stiffness: 90, mass: 0.8 },
              });
              const cur = ang0 + (ang1 - ang0) * Math.max(0, sw);
              if (cur <= ang0) return null;
              const d = arc(CX, CY, R, ang0, cur);
              // 厚度面：整体下移
              const sidePath = `M ${CX} ${CY} L ${polar(CX, CY, R, ang0).x.toFixed(1)} ${polar(CX, CY, R, ang0).y.toFixed(1)} A ${R} ${R} 0 ${cur - ang0 <= Math.PI ? 0 : 1} 1 ${polar(CX, CY, R, cur).x.toFixed(1)} ${polar(CX, CY, R, cur).y.toFixed(1)} Z`;
              const darken = 0.55;
              const darkColor = mixDark(s.color, darken);
              return (
                <g key={`s-${s.label}`}>
                  {/* 厚度（向下偏移） */}
                  <g transform={`translate(0 ${DEPTH})`} opacity={0.85}>
                    <path d={sidePath} fill={darkColor} />
                  </g>
                  {/* 正面 */}
                  <path d={d} fill={s.color} />
                </g>
              );
            })}

            {/* 中央白圆 + 高光 */}
            <circle cx={CX} cy={CY} r={R * 0.42} fill="#ffffff" />
            <circle cx={CX} cy={CY} r={R * 0.42} fill="url(#pieShine)" />
            <text
              x={CX}
              y={CY - 14}
              textAnchor="middle"
              fill="rgba(0,0,0,0.5)"
              fontSize={18}
              fontWeight={500}
              letterSpacing={2}
            >
              {centerLabel}
            </text>
            <text
              x={CX}
              y={CY + 36}
              textAnchor="middle"
              fill={PALETTE.paperInk}
              fontSize={56}
              fontWeight={800}
              opacity={interpolate(frame, [60, 110], [0, 1], {
                extrapolateRight: "clamp",
                easing: Easing.out(Easing.cubic),
              })}
            >
              {centerValue}
            </text>

            {/* 右侧图例 */}
            <g
              style={{
                opacity: interpolate(frame, [80, 110], [0, 1], {
                  extrapolateRight: "clamp",
                }),
              }}
            >
              {slices.map((s, i) => {
                const x = 620;
                const y = 90 + i * 56;
                return (
                  <g key={`lg-${s.label}`}>
                    <rect width={22} height={22} x={x} y={y} rx={6} fill={s.color} />
                    <text
                      x={x + 34}
                      y={y + 17}
                      fill={PALETTE.paperInk}
                      fontSize={22}
                      fontWeight={600}
                    >
                      {s.label}
                    </text>
                    <text
                      x={x + 280}
                      y={y + 17}
                      fill={PALETTE.paperInkMuted}
                      fontSize={22}
                      fontWeight={700}
                      textAnchor="end"
                    >
                      {(ratios[i] * 100).toFixed(1)}%
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

// 简易颜色调暗（依赖字符串 -> rgb -> 混合）
function mixDark(hex: string, k: number) {
  const m = hex.replace("#", "");
  const r = parseInt(m.slice(0, 2), 16);
  const g = parseInt(m.slice(2, 4), 16);
  const b = parseInt(m.slice(4, 6), 16);
  const rk = Math.round(r * k);
  const gk = Math.round(g * k);
  const bk = Math.round(b * k);
  return `rgb(${rk},${gk},${bk})`;
}
