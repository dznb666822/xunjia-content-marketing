import React from "react";
import {
  AbsoluteFill,
  Sequence,
  spring,
  interpolate,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";

// —— 可被「数据驱动」替换的部分：品牌名 / 卖点 / 价格 / CTA ——
const BRAND = "宠食工坊";
const PRODUCT = "冻干鸡肉粒 · 猫狗通用";
const POINTS = [
  { icon: "🌿", text: "0 添加剂" },
  { icon: "💪", text: "高蛋白 68%" },
  { icon: "😋", text: "适口性极佳" },
];
const PRICE = "¥29.9";
const CTA = "立即下单";

const COLORS = {
  bg: "#17123a",
  accent: "#ff6b35",
  gold: "#ffc857",
  text: "#ffffff",
  sub: "#c9c4e8",
};

const springConfig = { damping: 14, stiffness: 120, mass: 0.9 };
const FONT = '"Microsoft YaHei", "PingFang SC", "Noto Sans SC", sans-serif';

// 场景 1：品牌名 + 产品名 弹入
const TitleScene: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const s = spring({ frame, fps, config: springConfig });
  const opacity = interpolate(frame, [0, 10], [0, 1], { extrapolateRight: "clamp" });
  const subOpacity = interpolate(frame, [12, 22], [0, 1], { extrapolateRight: "clamp" });

  return (
    <AbsoluteFill style={{ justifyContent: "center", alignItems: "center" }}>
      <div style={{ transform: `scale(${s})`, opacity, textAlign: "center" }}>
        <div style={{ fontSize: 100, fontWeight: 800, color: COLORS.text, letterSpacing: 6 }}>
          {BRAND}
        </div>
        <div style={{ marginTop: 28, fontSize: 40, color: COLORS.gold, fontWeight: 600 }}>
          {PRODUCT}
        </div>
      </div>
      <div
        style={{
          position: "absolute",
          bottom: 130,
          opacity: subOpacity,
          fontSize: 28,
          color: COLORS.sub,
        }}
      >
        宠物零食 · 新品首发
      </div>
    </AbsoluteFill>
  );
};

// 场景 2：三个卖点卡片依次滑入
const PointsScene: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  return (
    <AbsoluteFill style={{ justifyContent: "center", alignItems: "center", gap: 40 }}>
      {POINTS.map((it, i) => {
        const s = spring({ frame: frame - i * 10, fps, config: springConfig });
        const x = interpolate(s, [0, 1], [420, 0]);
        return (
          <div
            key={i}
            style={{
              transform: `translateX(${x}px)`,
              display: "flex",
              alignItems: "center",
              gap: 22,
              background: "rgba(255,255,255,0.08)",
              borderRadius: 40,
              padding: "24px 48px",
              width: 560,
              boxSizing: "border-box",
            }}
          >
            <span style={{ fontSize: 48 }}>{it.icon}</span>
            <span style={{ fontSize: 44, color: COLORS.text, fontWeight: 700 }}>{it.text}</span>
          </div>
        );
      })}
    </AbsoluteFill>
  );
};

// 场景 3：价格卡片弹出 + CTA
const PriceScene: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const s = spring({ frame, fps, config: springConfig });
  const scale = interpolate(s, [0, 1], [0.5, 1]);
  const ctaOpacity = interpolate(frame, [18, 28], [0, 1], { extrapolateRight: "clamp" });

  return (
    <AbsoluteFill style={{ justifyContent: "center", alignItems: "center" }}>
      <div
        style={{
          transform: `scale(${scale})`,
          textAlign: "center",
          background: "linear-gradient(135deg, #ff6b35, #ffc857)",
          borderRadius: 40,
          padding: "60px 90px",
        }}
      >
        <div style={{ fontSize: 32, color: "#fff", opacity: 0.9 }}>限时抢购价</div>
        <div style={{ fontSize: 120, fontWeight: 900, color: "#fff", marginTop: 10 }}>{PRICE}</div>
      </div>
      <div
        style={{
          marginTop: 64,
          opacity: ctaOpacity,
          background: "#fff",
          color: COLORS.accent,
          fontSize: 44,
          fontWeight: 800,
          padding: "22px 70px",
          borderRadius: 50,
        }}
      >
        {CTA} →
      </div>
    </AbsoluteFill>
  );
};

export const PetAd: React.FC = () => {
  return (
    <AbsoluteFill style={{ backgroundColor: COLORS.bg, fontFamily: FONT }}>
      <Sequence from={0} durationInFrames={50}>
        <TitleScene />
      </Sequence>
      <Sequence from={50} durationInFrames={50}>
        <PointsScene />
      </Sequence>
      <Sequence from={100} durationInFrames={50}>
        <PriceScene />
      </Sequence>
    </AbsoluteFill>
  );
};
