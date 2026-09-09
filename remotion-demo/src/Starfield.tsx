import React, { useMemo } from "react";
import { AbsoluteFill, useCurrentFrame, random } from "remotion";

type Dust = { x: number; y: number; size: number; speed: number; tone: string };
type Medium = { x: number; y: number; size: number; speed: number; phase: number; tone: string };
type Hero = { x: number; y: number; size: number; phase: number; tone: string };

// 接近真实恒星色温分布：冷白偏多，暖橙其次，少量粉/青
const TONES = [
  "232,238,255", // 冷白
  "202,222,255", // 蓝白
  "255,208,148", // 暖橙
  "200,235,255", // 冷青
  "255,198,218", // 粉
];
function pickTone(r: number) {
  if (r < 0.55) return TONES[0];
  if (r < 0.78) return TONES[1];
  if (r < 0.9) return TONES[2];
  if (r < 0.97) return TONES[3];
  return TONES[4];
}

// 三层星空：dust（背景尘，340 颗，无 glow）→ medium（中景，90 颗，弱 glow）→ hero（亮星，18 颗，强 halo，静止）
export const Starfield: React.FC<{ seed?: string }> = ({ seed = "stars" }) => {
  const frame = useCurrentFrame();

  const { dust, medium, hero } = useMemo(() => {
    const dust: Dust[] = Array.from({ length: 340 }).map((_, i) => ({
      x: random(`${seed}-d-x-${i}`) * 100,
      y: random(`${seed}-d-y-${i}`) * 100,
      size: 0.4 + random(`${seed}-d-s-${i}`) * 0.5,
      speed: 0.0008 + random(`${seed}-d-v-${i}`) * 0.0015,
      tone: pickTone(random(`${seed}-d-c-${i}`)),
    }));
    const medium: Medium[] = Array.from({ length: 90 }).map((_, i) => ({
      x: random(`${seed}-m-x-${i}`) * 100,
      y: random(`${seed}-m-y-${i}`) * 100,
      size: 0.8 + random(`${seed}-m-s-${i}`) * 0.9,
      speed: 0.0004 + random(`${seed}-m-v-${i}`) * 0.0008,
      phase: random(`${seed}-m-p-${i}`) * Math.PI * 2,
      tone: pickTone(random(`${seed}-m-c-${i}`)),
    }));
    const hero: Hero[] = Array.from({ length: 18 }).map((_, i) => ({
      x: random(`${seed}-h-x-${i}`) * 100,
      y: random(`${seed}-h-y-${i}`) * 100,
      size: 1.6 + random(`${seed}-h-s-${i}`) * 1.8,
      phase: random(`${seed}-h-p-${i}`) * Math.PI * 2,
      tone: pickTone(random(`${seed}-h-c-${i}`)),
    }));
    return { dust, medium, hero };
  }, [seed]);

  return (
    <>
      {/* Layer 1 · Dust：极慢漂移、无 glow、不闪烁，铺底 */}
      <AbsoluteFill style={{ pointerEvents: "none" }}>
        {dust.map((s, i) => {
          const y = (s.y + frame * s.speed) % 100;
          return (
            <div
              key={`d-${i}`}
              style={{
                position: "absolute",
                left: `${s.x}%`,
                top: `${y}%`,
                width: s.size,
                height: s.size,
                borderRadius: "50%",
                background: `rgba(${s.tone},0.45)`,
              }}
            />
          );
        })}
      </AbsoluteFill>

      {/* Layer 2 · Medium：弱 glow、慢呼吸 */}
      <AbsoluteFill style={{ pointerEvents: "none" }}>
        {medium.map((s, i) => {
          const y = (s.y + frame * s.speed) % 100;
          const tw = 0.65 + 0.18 * Math.sin(frame * 0.022 + s.phase);
          return (
            <div
              key={`m-${i}`}
              style={{
                position: "absolute",
                left: `${s.x}%`,
                top: `${y}%`,
                width: s.size,
                height: s.size,
                borderRadius: "50%",
                background: `rgba(${s.tone},${tw})`,
                boxShadow: `0 0 ${s.size * 2.2}px ${s.size * 0.5}px rgba(${s.tone},${tw * 0.32})`,
              }}
            />
          );
        })}
      </AbsoluteFill>

      {/* Layer 3 · Hero：双层 halo、几乎不动、慢脉冲，对应参考图里的"亮星点" */}
      <AbsoluteFill style={{ pointerEvents: "none" }}>
        {hero.map((s, i) => {
          const tw = 0.82 + 0.16 * Math.sin(frame * 0.016 + s.phase);
          return (
            <div
              key={`h-${i}`}
              style={{
                position: "absolute",
                left: `${s.x}%`,
                top: `${s.y}%`,
                width: s.size,
                height: s.size,
                borderRadius: "50%",
                background: `rgba(${s.tone},${tw})`,
                boxShadow: `0 0 ${s.size * 5}px ${s.size * 1.6}px rgba(${s.tone},${tw * 0.55}), 0 0 ${s.size * 9}px ${s.size * 2.6}px rgba(${s.tone},${tw * 0.2})`,
              }}
            />
          );
        })}
      </AbsoluteFill>
    </>
  );
};
