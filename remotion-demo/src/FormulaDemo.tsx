import React from "react";
import {
  AbsoluteFill,
  Sequence,
  spring,
  interpolate,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";
import katex from "katex";
import "katex/dist/katex.min.css";
import { SpaceBackground } from "./SpaceBackground";

// —— 推导步骤（LaTeX 源码）——
const STEPS = [
  { latex: "ax^2 + bx + c = 0", note: "原方程" },
  { latex: "x^2 + \\frac{b}{a}x = -\\frac{c}{a}", note: "两边同除以 a" },
  {
    latex: "x^2 + \\frac{b}{a}x + \\frac{b^2}{4a^2} = \\frac{b^2 - 4ac}{4a^2}",
    note: "配方：两边加 (b/2a)²",
  },
  { latex: "(x + \\frac{b}{2a})^2 = \\frac{b^2 - 4ac}{4a^2}", note: "左边写成完全平方" },
  { latex: "x + \\frac{b}{2a} = \\pm \\frac{\\sqrt{b^2 - 4ac}}{2a}", note: "两边开平方" },
];

const FINAL_LATEX = "x = \\frac{-b \\pm \\sqrt{b^2 - 4ac}}{2a}";
const ACCENT = "#c9b2ff";

// 预渲染 KaTeX → HTML，避免每帧重复计算
const STEP_HTML = STEPS.map((s) =>
  katex.renderToString(s.latex, { throwOnError: false, displayMode: false })
);
const FINAL_HTML = katex.renderToString(FINAL_LATEX, {
  throwOnError: false,
  displayMode: true,
});

const springConfig = { damping: 16, stiffness: 130, mass: 0.9 };
const FONT = '"Microsoft YaHei", "PingFang SC", "KaTeX_Main", serif';

// 单条推导步骤：玻璃卡片 + 数字徽章 + 扫光高亮 + 下箭头
const StepCard: React.FC<{ index: number }> = ({ index }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const s = spring({ frame, fps, config: springConfig });
  const y = interpolate(s, [0, 1], [46, 0]);
  const opacity = interpolate(frame, [0, 8], [0, 1], { extrapolateRight: "clamp" });
  // 扫光：白亮带从左到右扫过一次，营造"正在推导"感
  const sweep = interpolate(frame, [6, 34], [-160, 260], { extrapolateRight: "clamp" });
  const sweepOp = interpolate(frame, [6, 24, 40], [0, 0.9, 0], {
    extrapolateRight: "clamp",
  });
  const step = STEPS[index];

  return (
    <AbsoluteFill style={{ justifyContent: "center", alignItems: "center" }}>
      <div
        style={{
          transform: `translateY(${y}px)`,
          opacity,
          width: "82%",
          maxWidth: 900,
          borderRadius: 28,
          background: "rgba(255,255,255,0.06)",
          backdropFilter: "blur(20px) saturate(150%)",
          border: "1px solid rgba(255,255,255,0.14)",
          boxShadow:
            "inset 0 1px 0 rgba(255,255,255,0.22), 0 30px 70px rgba(0,0,0,0.5), 0 0 40px rgba(120,90,255,0.12)",
          padding: "52px 56px",
          position: "relative",
          overflow: "hidden",
        }}
      >
        {/* 顶部：序号 + 步骤名 */}
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: 18,
            marginBottom: 26,
          }}
        >
          <div
            style={{
              width: 46,
              height: 46,
              borderRadius: "50%",
              background: "rgba(201,178,255,0.16)",
              color: ACCENT,
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              fontSize: 22,
              fontWeight: 800,
              border: "1.5px solid rgba(201,178,255,0.5)",
              boxShadow: "0 0 18px rgba(201,178,255,0.35)",
            }}
          >
            {index + 1}
          </div>
          <div style={{ fontSize: 22, color: "rgba(255,255,255,0.7)", letterSpacing: 1 }}>
            推导步骤 {index + 1}
          </div>
        </div>

        {/* 公式（KaTeX） */}
        <div
          style={{
            fontSize: 52,
            color: "#f6f4ff",
            textAlign: "center",
            textShadow: "0 0 22px rgba(180,150,255,0.4)",
          }}
          dangerouslySetInnerHTML={{ __html: STEP_HTML[index] }}
        />

        {/* 扫光层 */}
        <div
          style={{
            position: "absolute",
            top: 0,
            left: 0,
            width: 60,
            height: "100%",
            background: "linear-gradient(90deg, transparent, rgba(255,255,255,0.5), transparent)",
            transform: `translateX(${sweep}%)`,
            opacity: sweepOp,
            mixBlendMode: "screen",
            pointerEvents: "none",
          }}
        />
      </div>

      {/* 步骤说明 */}
      <div
        style={{
          position: "absolute",
          bottom: 210,
          fontSize: 24,
          color: "rgba(255,255,255,0.6)",
          letterSpacing: 1,
          opacity: interpolate(frame, [8, 18], [0, 1], { extrapolateRight: "clamp" }),
        }}
      >
        {step.note}
      </div>
    </AbsoluteFill>
  );
};

// 最终结论卡片（金色发光玻璃卡）
const FinalCard: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const s = spring({ frame, fps, config: { damping: 12, stiffness: 160, mass: 0.8 } });
  const scale = interpolate(s, [0, 1], [0.62, 1]);
  const glow = interpolate(frame, [15, 45], [0, 1], { extrapolateRight: "clamp" });

  return (
    <AbsoluteFill style={{ justifyContent: "center", alignItems: "center" }}>
      <div
        style={{
          transform: `scale(${scale})`,
          textAlign: "center",
          background: "linear-gradient(135deg, rgba(255,150,60,0.92), rgba(255,200,90,0.92))",
          backdropFilter: "blur(10px)",
          borderRadius: 30,
          padding: "44px 72px",
          boxShadow: `0 0 ${50 + glow * 50}px rgba(255,150,60,${0.3 + glow * 0.4}), inset 0 1px 0 rgba(255,255,255,0.6)`,
        }}
      >
        <div
          style={{
            fontSize: 24,
            color: "rgba(255,255,255,0.92)",
            marginBottom: 10,
            fontWeight: 600,
            letterSpacing: 2,
          }}
        >
          求根公式
        </div>
        <div style={{ fontSize: 64, color: "#fff" }} dangerouslySetInnerHTML={{ __html: FINAL_HTML }} />
      </div>
    </AbsoluteFill>
  );
};

// 底部品牌玻璃条
const BrandStrip: React.FC = () => {
  const frame = useCurrentFrame();
  const opacity = interpolate(frame, [205, 235], [0, 1], { extrapolateRight: "clamp" });
  const y = interpolate(frame, [205, 235], [40, 0], { extrapolateRight: "clamp" });
  return (
    <div
      style={{
        position: "absolute",
        bottom: 150,
        left: 0,
        right: 0,
        display: "flex",
        justifyContent: "center",
        opacity,
        transform: `translateY(${y}px)`,
      }}
    >
      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: 18,
          padding: "26px 44px",
          borderRadius: 24,
          background: "rgba(30,40,80,0.34)",
          backdropFilter: "blur(24px) saturate(160%)",
          border: "1px solid rgba(255,255,255,0.16)",
          boxShadow:
            "inset 0 1px 0 rgba(255,255,255,0.25), 0 30px 60px rgba(0,0,0,0.5), 0 0 46px rgba(90,120,255,0.16)",
        }}
      >
        <div
          style={{
            width: 40,
            height: 40,
            borderRadius: 12,
            background: "linear-gradient(135deg, #7f77dd, #4f7ff0)",
            boxShadow: "0 0 20px rgba(127,119,221,0.7)",
          }}
        />
        <div style={{ textAlign: "left" }}>
          <div style={{ fontSize: 30, fontWeight: 700, color: "#eef0ff", letterSpacing: 2 }}>
            一元二次方程 · 通解
          </div>
          <div
            style={{ fontSize: 18, color: "rgba(255,255,255,0.62)", letterSpacing: 1, marginTop: 4 }}
          >
            Quadratic Formula · 完美复刻
          </div>
        </div>
      </div>
    </div>
  );
};

export const FormulaDemo: React.FC = () => {
  return (
    <SpaceBackground>
      {/* 顶部标题（发光） */}
      <div
        style={{
          position: "absolute",
          top: 150,
          left: 0,
          right: 0,
          textAlign: "center",
          color: "#fff",
          fontSize: 50,
          fontWeight: 800,
          letterSpacing: 3,
          textShadow: "0 0 26px rgba(180,150,255,0.55), 0 4px 20px rgba(0,0,0,0.6)",
        }}
      >
        二次方程求根公式推导
      </div>

      {/* 步骤指示器 */}
      <div
        style={{
          position: "absolute",
          top: 240,
          left: 0,
          right: 0,
          display: "flex",
          justifyContent: "center",
          gap: 12,
        }}
      >
        {STEPS.map((_, i) => (
          <div
            key={i}
            style={{
              width: 11,
              height: 11,
              borderRadius: "50%",
              background: i < 4 ? "rgba(255,255,255,0.28)" : "#ffc857",
              boxShadow: i >= 4 ? "0 0 14px rgba(255,200,87,0.7)" : "none",
            }}
          />
        ))}
      </div>

      {/* 五步推导：每步 32 帧 */}
      <Sequence from={30} durationInFrames={32}>
        <StepCard index={0} />
      </Sequence>
      <Sequence from={62} durationInFrames={32}>
        <StepCard index={1} />
      </Sequence>
      <Sequence from={94} durationInFrames={32}>
        <StepCard index={2} />
      </Sequence>
      <Sequence from={126} durationInFrames={32}>
        <StepCard index={3} />
      </Sequence>
      <Sequence from={158} durationInFrames={32}>
        <StepCard index={4} />
      </Sequence>

      {/* 最终结论 */}
      <Sequence from={195} durationInFrames={75}>
        <FinalCard />
      </Sequence>

      {/* 底部品牌玻璃条 */}
      <BrandStrip />
    </SpaceBackground>
  );
};
