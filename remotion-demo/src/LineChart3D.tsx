import React from "react";
import {
  useCurrentFrame,
  interpolate,
  spring,
  useVideoConfig,
} from "remotion";
import { SpaceBackground } from "./SpaceBackground";
import { PALETTE, TYPE, SHADOW, smoothPath, AccentBar } from "./theme";

export type LineSeries = { name: string; color: string; values: number[] };

export interface LineChart3DProps {
  title: string;
  subtitle: string;        // 副标题：单位 + 区间描述
  unit: string;
  captionHi: string;       // 底部电影感中文标语
  captionSub: string;      // 底部小字英文
  years: (string | number)[];
  series: LineSeries[];
  maxValue?: number;       // 0–maxValue 区间；不传则按数据自动推断
  timeOffset?: number;     // 给 ChartGallery 用，可整体延后时间线
}

// 图表坐标空间（白色纸面上）
const W = 880;
const H = 520;
const PAD = { top: 48, right: 150, bottom: 54, left: 66 };

export const LineChart3D: React.FC<LineChart3DProps> = ({
  title,
  subtitle,
  unit,
  captionHi,
  captionSub,
  years,
  series,
  maxValue,
  timeOffset = 0,
}) => {
  const frame = useCurrentFrame() - timeOffset;
  const { fps } = useVideoConfig();

  const computedMax =
    maxValue ??
    Math.ceil(Math.max(...series.flatMap((s) => s.values)) / 5) * 5;
  const yTicks = Array.from({ length: 6 }, (_, i) => (computedMax / 5) * i);

  // 纸面旋转进入
  const tiltIn = spring({ frame, fps, config: { damping: 16, stiffness: 120, mass: 0.9 } });
  const rotateX = interpolate(tiltIn, [0, 1], [70, 52]);
  const rotateY = interpolate(tiltIn, [0, 1], [-12, -5]);
  const scale = interpolate(tiltIn, [0, 1], [1.22, 1.03]);
  const planeOpacity = interpolate(frame, [0, 18], [0, 1], { extrapolateRight: "clamp" });
  const float = Math.sin(frame / 46) * 7;
  const reveal = interpolate(frame, [42, 138], [0, W], { extrapolateRight: "clamp" });

  const titleY = interpolate(frame, [8, 28], [-26, 0], { extrapolateRight: "clamp" });
  const titleOp = interpolate(frame, [8, 24], [0, 1], { extrapolateRight: "clamp" });
  const labelOp = interpolate(frame, [120, 150], [0, 1], { extrapolateRight: "clamp" });
  const captionY = interpolate(frame, [136, 166], [46, 0], { extrapolateRight: "clamp" });
  const captionOp = interpolate(frame, [136, 162], [0, 1], { extrapolateRight: "clamp" });

  const xFor = (i: number) => PAD.left + (i * (W - PAD.left - PAD.right)) / (years.length - 1);
  const yFor = (v: number) => PAD.top + (H - PAD.top - PAD.bottom) * (1 - v / computedMax);

  return (
    <SpaceBackground>
      {/* 顶部标题 */}
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
          top: 560,
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
            boxShadow: SHADOW.dropStrong,
            padding: 22,
          }}
        >
          <svg width={W} height={H} viewBox={`0 0 ${W} ${H}`}>
            <defs>
              <clipPath id="lineReveal">
                <rect x={0} y={0} width={reveal} height={H} />
              </clipPath>
            </defs>

            {/* 水平网格 + Y 轴刻度 */}
            {yTicks.map((v) => {
              const y = yFor(v);
              return (
                <g key={`y-${v}`}>
                  <line
                    x1={PAD.left}
                    y1={y}
                    x2={W - PAD.right}
                    y2={y}
                    stroke={PALETTE.paperGrid}
                    strokeWidth={1}
                  />
                  <text
                    x={PAD.left - 12}
                    y={y + 4}
                    textAnchor="end"
                    fill={PALETTE.paperInkMuted}
                    fontSize={TYPE.paperAxis}
                  >
                    {v}
                  </text>
                </g>
              );
            })}

            {/* 垂直网格 + X 轴年份 */}
            {years.map((year, i) => {
              const x = xFor(i);
              return (
                <g key={`x-${year}`}>
                  <line
                    x1={x}
                    y1={PAD.top}
                    x2={x}
                    y2={H - PAD.bottom}
                    stroke={PALETTE.paperGrid}
                    strokeWidth={1}
                  />
                  <text
                    x={x}
                    y={H - PAD.bottom + 26}
                    textAnchor="middle"
                    fill={PALETTE.paperInk}
                    fontSize={TYPE.paperAxisYear}
                  >
                    {year}
                  </text>
                </g>
              );
            })}

            {/* 坐标轴 */}
            <line
              x1={PAD.left}
              y1={H - PAD.bottom}
              x2={W - PAD.right}
              y2={H - PAD.bottom}
              stroke={PALETTE.paperAxis}
              strokeWidth={2}
            />
            <line
              x1={PAD.left}
              y1={PAD.top}
              x2={PAD.left}
              y2={H - PAD.bottom}
              stroke={PALETTE.paperAxis}
              strokeWidth={2}
            />

            {/* 平滑折线 + 数据点 */}
            <g clipPath="url(#lineReveal)">
              {series.map((s) => {
                const xs = s.values.map((_, i) => xFor(i));
                const ys = s.values.map((v) => yFor(v));
                const d = smoothPath(xs, ys);
                return (
                  <path
                    key={`line-${s.name}`}
                    d={d}
                    fill="none"
                    stroke={s.color}
                    strokeWidth={3.5}
                    strokeLinecap="round"
                    strokeLinejoin="round"
                  />
                );
              })}
              {series.map((s) =>
                s.values.map((v, i) => (
                  <circle
                    key={`dot-${s.name}-${i}`}
                    cx={xFor(i)}
                    cy={yFor(v)}
                    r={4.5}
                    fill={s.color}
                    stroke="#fff"
                    strokeWidth={1.5}
                  />
                ))
              )}
            </g>

            {/* 右侧图例 */}
            <g style={{ opacity: labelOp }}>
              {series.map((s, i) => (
                <g
                  key={`legend-${s.name}`}
                  transform={`translate(${W - PAD.right + 26}, ${PAD.top + 30 + i * 32})`}
                >
                  <rect width={15} height={15} fill={s.color} rx={4} />
                  <text
                    x={24}
                    y={13}
                    fill={PALETTE.paperInk}
                    fontSize={TYPE.legend}
                    fontWeight={600}
                  >
                    {s.name}
                  </text>
                </g>
              ))}
            </g>
          </svg>
        </div>
      </div>

      {/* 底部字幕块 */}
      <div
        style={{
          position: "absolute",
          bottom: 250,
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
