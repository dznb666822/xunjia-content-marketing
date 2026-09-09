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

// —— Top N 排行（横条）——
// 主题示例：2024 最受欢迎编程语言 Top 5

export interface RankItem {
  rank: number;
  label: string;            // 主名
  sub?: string;             // 副名/简介
  icon: string;             // emoji 或字母
  color: string;            // 色
  score: number;            // 数值（自动按 max 归一）
  badge?: string;           // 右侧小红徽章（可选）
}

export interface RankBarsProps {
  title: string;
  subtitle: string;
  captionHi: string;
  captionSub: string;
  items: RankItem[];
  timeOffset?: number;
}

const PAPER_W = 980;
const PAPER_H = 600;
const PAD = { top: 50, right: 36, bottom: 50, left: 36 };
const ROW_H = 78;

export const RankBars: React.FC<RankBarsProps> = ({
  title,
  subtitle,
  captionHi,
  captionSub,
  items,
  timeOffset = 0,
}) => {
  const frame = useCurrentFrame() - timeOffset;
  const { fps } = useVideoConfig();

  const tiltIn = spring({ frame, fps, config: { damping: 16, stiffness: 120, mass: 0.9 } });
  const rotateX = interpolate(tiltIn, [0, 1], [70, 56]);
  const rotateY = interpolate(tiltIn, [0, 1], [-12, -3]);
  const scale = interpolate(tiltIn, [0, 1], [1.18, 1.02]);
  const planeOpacity = interpolate(frame, [0, 18], [0, 1], { extrapolateRight: "clamp" });
  const float = Math.sin(frame / 46) * 7;

  const titleY = interpolate(frame, [8, 28], [-26, 0], { extrapolateRight: "clamp" });
  const titleOp = interpolate(frame, [8, 24], [0, 1], { extrapolateRight: "clamp" });
  const captionY = interpolate(frame, [170, 200], [46, 0], { extrapolateRight: "clamp" });
  const captionOp = interpolate(frame, [170, 196], [0, 1], { extrapolateRight: "clamp" });

  const maxScore = Math.max(...items.map((x) => x.score));
  const innerW = PAPER_W - PAD.left - PAD.right - 220; // 减 rank+icon+label 占的空间

  // 行错峰
  const rowStartBase = 30;
  const rowGap = 6;

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
          top: 530,
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
            {items.map((it, i) => {
              const startFrame = rowStartBase + i * rowGap + i * 6;
              const entered = spring({
                frame: frame - startFrame,
                fps,
                config: { damping: 14, stiffness: 140, mass: 0.7 },
              });
              const ty = interpolate(entered, [0, 1], [20, 0]);
              const op = interpolate(entered, [0, 1], [0, 1]);
              const y = PAD.top + i * ROW_H + ty;
              const barLen = (it.score / maxScore) * innerW * entered;
              const labelX = PAD.left + 200;
              const barX = labelX;
              const valueX = barX + innerW + 24;
              const maxValW = 90;

              return (
                <g key={`row-${it.rank}`} style={{ opacity: op }}>
                  {/* 排名徽章 */}
                  <circle
                    cx={PAD.left + 30}
                    cy={y + ROW_H / 2 - 18}
                    r={26}
                    fill={it.color}
                  />
                  <text
                    x={PAD.left + 30}
                    y={y + ROW_H / 2 - 8}
                    textAnchor="middle"
                    fontSize={26}
                    fontWeight={800}
                    fill="#fff"
                  >
                    {it.rank}
                  </text>

                  {/* 图标 */}
                  <text
                    x={PAD.left + 78}
                    y={y + ROW_H / 2 - 8}
                    fontSize={32}
                  >
                    {it.icon}
                  </text>

                  {/* 主名 + 副 */}
                  <text
                    x={PAD.left + 120}
                    y={y + ROW_H / 2 - 8}
                    fontSize={22}
                    fontWeight={700}
                    fill={PALETTE.paperInk}
                  >
                    {it.label}
                  </text>
                  {it.sub ? (
                    <text
                      x={PAD.left + 120 + it.label.length * 16 + 14}
                      y={y + ROW_H / 2 - 4}
                      fontSize={16}
                      fill={PALETTE.paperInkMuted}
                    >
                      {it.sub}
                    </text>
                  ) : null}

                  {/* 进度条底 */}
                  <rect
                    x={barX}
                    y={y + 14}
                    width={innerW}
                    height={20}
                    rx={10}
                    fill="rgba(0,0,0,0.06)"
                  />
                  {/* 进度条填充 */}
                  <rect
                    x={barX}
                    y={y + 14}
                    width={barLen}
                    height={20}
                    rx={10}
                    fill={`url(#bar-${i})`}
                  />

                  {/* 数值 */}
                  <text
                    x={valueX}
                    y={y + 30}
                    fontSize={22}
                    fontWeight={700}
                    fill={PALETTE.paperInk}
                  >
                    {it.score}
                  </text>

                  {/* badge (可选) */}
                  {it.badge ? (
                    <g>
                      <rect
                        x={valueX + 60}
                        y={y + 12}
                        width={58}
                        height={26}
                        rx={6}
                        fill="#d94e4e"
                      />
                      <text
                        x={valueX + 89}
                        y={y + 30}
                        fontSize={16}
                        fontWeight={700}
                        fill="#fff"
                        textAnchor="middle"
                      >
                        {it.badge}
                      </text>
                    </g>
                  ) : null}
                </g>
              );
            })}

            {/* 渐变 defs */}
            <defs>
              {items.map((it, i) => (
                <linearGradient
                  key={`lg-${i}`}
                  id={`bar-${i}`}
                  x1="0"
                  y1="0"
                  x2="1"
                  y2="0"
                >
                  <stop offset="0%" stopColor={it.color} stopOpacity={0.55} />
                  <stop offset="100%" stopColor={it.color} stopOpacity={1} />
                </linearGradient>
              ))}
            </defs>
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
