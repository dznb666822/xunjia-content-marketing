import React from "react";
import {
  AbsoluteFill,
  Sequence,
  spring,
  interpolate,
  useCurrentFrame,
  useVideoConfig,
  Easing,
} from "remotion";

// ============================================================================
// 参考脚本《视频剪辑脚本拆解报告》可复刻元素 —— Remotion 复刻
// 9:16 竖屏 1080×1920，用占位素材复刻「版式 + 动效」，不涉及真实口播/照片内容。
// 元素清单（对应报告 §五 字幕系统 + §六 特效清单）：
//   1 字幕系统(白/黄/蓝公式字+双层+pop)  2 浏览器线框pop+zoom
//   3 右上画中画+循环箭头                4 对比图上下残边拼贴
//   5 橙色弧线标注(描线)                6 whip pan 甩镜
//   7 小红书笔记卡片UI弹入               8 vignette 暗角开关
//   9 3D礼物盒掌心弹出                  10 撕纸边静态清单页
// ============================================================================

const FONT = '"Microsoft YaHei", "PingFang SC", "Noto Sans SC", sans-serif';
const C = {
  white: "#ffffff",
  yellow: "#f0d060",
  blue: "#bfe3f2",
  blueStroke: "#1e3a5f",
  ink: "#1e293b",
  muted: "#94a3b8",
  accent: "#ff6b35",
  bgTop: "#0f172a",
  bgBottom: "#1e293b",
  roomTop: "#111827",
  roomBottom: "#1f2937",
};

const popConfig = { damping: 12, stiffness: 180, mass: 0.8 };

// 通用：模拟「室内夜景口播背景」的渐变 + 人物占位剪影
const RoomBackdrop: React.FC<{ children?: React.ReactNode }> = ({ children }) => (
  <AbsoluteFill
    style={{
      background: `linear-gradient(180deg, ${C.roomTop} 0%, ${C.roomBottom} 100%)`,
      fontFamily: FONT,
    }}
  >
    {/* 窗户光斑 */}
    <div
      style={{
        position: "absolute",
        top: 120,
        left: 120,
        width: 340,
        height: 340,
        borderRadius: 18,
        background: "linear-gradient(180deg, #1e3a5f 0%, #0b1c2f 100%)",
        boxShadow: "inset 0 0 60px rgba(80,140,220,0.25)",
      }}
    />
    {/* 人物占位剪影（居中偏左） */}
    <div
      style={{
        position: "absolute",
        left: 180,
        bottom: 0,
        width: 560,
        height: 1050,
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
      }}
    >
      <div
        style={{
          width: 300,
          height: 300,
          borderRadius: "50%",
          background: "linear-gradient(180deg,#3b4a5f 0%,#25303f 100%)",
        }}
      />
      <div
        style={{
          width: 420,
          height: 760,
          marginTop: -10,
          borderRadius: "60px 60px 0 0",
          background: "linear-gradient(180deg,#33455c 0%,#22303f 100%)",
        }}
      />
    </div>
    {/* 桌面占下 1/4 */}
    <div
      style={{
        position: "absolute",
        left: 0,
        right: 0,
        bottom: 0,
        height: 400,
        background: "linear-gradient(180deg,#1a2433 0%,#0d141f 100%)",
      }}
    />
    {children}
  </AbsoluteFill>
);

// ============================================================================
// 1. 字幕系统 —— 白字/黄字/蓝公式字，双层，pop 弹入
// ============================================================================
type SubStyle = "white" | "yellow" | "blue";
const SUB_STYLE: Record<SubStyle, { color: string; stroke: string; italic?: boolean; size: number }> = {
  white: { color: C.white, stroke: "#000", italic: true, size: 62 },
  yellow: { color: C.yellow, stroke: "#000", size: 62 },
  blue: { color: C.blue, stroke: C.blueStroke, size: 88 },
};

const SubtitleLine: React.FC<{
  text: string;
  style: SubStyle;
  delay?: number;
  bottom?: string;
}> = ({ text, style, delay = 0, bottom = "17%" }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const s = spring({ frame: frame - delay, fps, config: popConfig });
  const cfg = SUB_STYLE[style];
  return (
    <div
      style={{
        position: "absolute",
        left: 0,
        right: 0,
        bottom,
        textAlign: "center",
        transform: `scale(${Math.max(0, s)})`,
        opacity: Math.max(0, s),
      }}
    >
      <span
        style={{
          fontSize: cfg.size,
          fontWeight: 800,
          color: cfg.color,
          fontStyle: cfg.italic ? "italic" : "normal",
          WebkitTextStroke: `2px ${cfg.stroke}`,
          textShadow: "0 3px 10px rgba(0,0,0,0.65)",
          letterSpacing: 2,
        }}
      >
        {text}
      </span>
    </div>
  );
};

// ============================================================================
// 2. 浏览器线框 pop 弹入 + 框内 zoom 满屏
// ============================================================================
const BrowserFrame: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const pop = spring({ frame, fps, config: { damping: 13, stiffness: 160 } });
  const zoom = interpolate(frame, [30, 55], [1, 3.2], {
    easing: Easing.in(Easing.cubic),
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
  const fade = interpolate(frame, [50, 60], [1, 0], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
  const ctrl = ["◀", "▶", "↻", "★", "⋯", "✕"];
  return (
    <AbsoluteFill style={{ alignItems: "center", justifyContent: "center", opacity: fade }}>
      <div
        style={{
          width: 640,
          height: 880,
          border: "3px solid #fff",
          borderRadius: 14,
          background: "rgba(8,14,24,0.72)",
          overflow: "hidden",
          transform: `scale(${pop * zoom})`,
          boxShadow: "0 40px 90px rgba(0,0,0,0.6)",
        }}
      >
        {/* 地址栏 */}
        <div
          style={{
            height: 56,
            background: "#fff",
            display: "flex",
            alignItems: "center",
            padding: "0 14px",
            gap: 12,
            color: "#334155",
            fontSize: 22,
          }}
        >
          {ctrl.map((x, i) => (
            <span key={i} style={{ width: 28, textAlign: "center" }}>{x}</span>
          ))}
          <div
            style={{
              flex: 1,
              height: 30,
              borderRadius: 15,
              background: "#eef1f5",
              marginLeft: 6,
              fontSize: 13,
              color: "#94a3b8",
              display: "flex",
              alignItems: "center",
              paddingLeft: 12,
            }}
          >
            https://www.gov.cn/...
          </div>
        </div>
        {/* 内容区（预加载画面占位） */}
        <div
          style={{
            flex: 1,
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            background: "linear-gradient(180deg,#1e3a5f 0%,#0f2438 100%)",
          }}
        >
          <div style={{ color: "#bfe3f2", fontSize: 30, fontWeight: 600 }}>B3 舌头演示画面</div>
        </div>
      </div>
    </AbsoluteFill>
  );
};

// ============================================================================
// 3. 右上画中画小窗 + 循环上下箭头动画
// ============================================================================
const PipArrow: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const inO = interpolate(frame, [0, 12], [0, 1], { extrapolateRight: "clamp" });
  const outO = interpolate(frame, [55, 70], [1, 0], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
  const bounce = Math.sin((frame / fps) * Math.PI * 2) * 26;
  return (
    <AbsoluteFill>
      {/* 右上小窗 */}
      <div
        style={{
          position: "absolute",
          top: 220,
          right: 90,
          width: 360,
          height: 480,
          borderRadius: 16,
          border: "3px solid rgba(255,255,255,0.85)",
          overflow: "hidden",
          background: "linear-gradient(180deg,#25374a 0%,#16232f 100%)",
          opacity: inO * outO,
          boxShadow: "0 24px 60px rgba(0,0,0,0.55)",
        }}
      >
        <div style={{ padding: 14, color: "#cbd5e1", fontSize: 20 }}>B4 鼻部特写</div>
        {/* 上下箭头 */}
        {[0, 1, 2].map((i) => (
          <div
            key={i}
            style={{
              position: "absolute",
              left: 90 + i * 70,
              top: 120,
              color: "#fff",
              fontSize: 46,
              transform: `translateY(${bounce}px)`,
              opacity: 0.9,
            }}
          >
            ↕
          </div>
        ))}
      </div>
    </AbsoluteFill>
  );
};

// ============================================================================
// 4. 对比图「上下留主画面残边」层叠拼贴版式
// ============================================================================
const CompareSplit: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const pop = spring({ frame, fps, config: popConfig });
  const left = ["改造前", "粉运动内衣 · 镜前自拍", "#b45a6b"];
  const right = ["改造后", "灰运动内衣 · 镜前自拍", "#3f9d63"];
  const half = ({ t, s, c, align }: { t: string; s: string; c: string; align: string }) => (
    <div
      style={{
        flex: 1,
        background: `linear-gradient(180deg, ${c} 0%, ${c}cc 100%)`,
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "center",
        gap: 10,
      }}
    >
      <div style={{ color: "#fff", fontSize: 34, fontWeight: 700 }}>{t}</div>
      <div style={{ color: "rgba(255,255,255,0.85)", fontSize: 20, padding: "0 20px", textAlign: "center" }}>{s}</div>
    </div>
  );
  return (
    <AbsoluteFill>
      {/* 上下留出的主画面残边（桌面/背景色块，制造层叠感） */}
      <div style={{ position: "absolute", top: 140, left: 60, right: 60, height: 14, background: "#0d141f", borderRadius: 6 }} />
      <div style={{ position: "absolute", bottom: 300, left: 60, right: 60, height: 14, background: "#0d141f", borderRadius: 6 }} />
      <div
        style={{
          position: "absolute",
          top: 170,
          bottom: 330,
          left: 60,
          right: 60,
          display: "flex",
          borderRadius: 12,
          overflow: "hidden",
          transform: `scale(${pop})`,
          boxShadow: "0 30px 70px rgba(0,0,0,0.55)",
        }}
      >
        <div style={{ flex: 1.1, borderRight: "3px solid #fff" }}>{half({ t: left[0], s: left[1], c: left[2], align: "left" })}</div>
        <div style={{ flex: 1 }}>{half({ t: right[0], s: right[1], c: right[2], align: "right" })}</div>
      </div>
    </AbsoluteFill>
  );
};

// ============================================================================
// 5. 橙色手绘弧线标注（SVG 描线动画）
// ============================================================================
const ArcAnnotation: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const p = interpolate(frame, [0, 30], [0, 1], {
    easing: Easing.out(Easing.cubic),
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
  // 下颌线两条弧线（path 总长约 500，用 dashoffset 做描线出现）
  const L = 520;
  const arcs = [
    "M 300 820 Q 540 900 780 800",
    "M 320 880 Q 540 950 760 860",
  ];
  return (
    <AbsoluteFill>
      {/* 侧脸占位 */}
      <div
        style={{
          position: "absolute",
          top: 360,
          left: 300,
          width: 480,
          height: 560,
          borderRadius: "50% 50% 44% 44%",
          background: "linear-gradient(160deg,#d9c2a8 0%,#b9977c 100%)",
        }}
      />
      <svg
        width="1080"
        height="1920"
        viewBox="0 0 1080 1920"
        style={{ position: "absolute", inset: 0 }}
      >
        {arcs.map((d, i) => (
          <path
            key={i}
            d={d}
            fill="none"
            stroke="#ff8c2e"
            strokeWidth={10}
            strokeLinecap="round"
            strokeDasharray={L}
            strokeDashoffset={L * (1 - p)}
            style={{ filter: "drop-shadow(0 0 6px rgba(255,140,46,0.7))" }}
          />
        ))}
      </svg>
    </AbsoluteFill>
  );
};

// ============================================================================
// 6. whip pan 甩镜转场（横向快速平移 + motion blur）
// ============================================================================
const WhipPan: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const x = interpolate(frame, [0, 20], [0, 1200], {
    easing: Easing.in(Easing.quad),
    extrapolateRight: "clamp",
  });
  const blur = interpolate(frame, [0, 10], [0, 18], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
  return (
    <AbsoluteFill>
      <div
        style={{
          position: "absolute",
          inset: -200,
          background:
            "linear-gradient(90deg,#0f172a 0%,#1e3a5f 30%,#33455c 60%,#0f172a 100%)",
          transform: `translateX(${x}px)`,
          filter: `blur(${blur}px)`,
        }}
      />
      <div style={{ position: "absolute", inset: 0, display: "flex", alignItems: "center", justifyContent: "center" }}>
        <span style={{ color: "#fff", fontSize: 40, fontWeight: 700, letterSpacing: 8, opacity: 0.9 }}>
          WHIP PAN →
        </span>
      </div>
    </AbsoluteFill>
  );
};

// ============================================================================
// 7. 小红书笔记卡片 UI（置顶标/播放量/点赞/头像昵称/标题）弹入
// ============================================================================
const XhsCard: React.FC<{ from: "left" | "right" }> = ({ from }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const s = spring({ frame, fps, config: popConfig });
  const slideX = from === "left" ? -420 : 420;
  const x = interpolate(s, [0, 1], [slideX, 0]);
  return (
    <div
      style={{
        position: "absolute",
        top: from === "left" ? 420 : 540,
        left: from === "left" ? 160 : 560,
        width: 360,
        background: "#fff",
        borderRadius: 16,
        overflow: "hidden",
        transform: `translateX(${x}px) scale(${s})`,
        boxShadow: "0 24px 60px rgba(0,0,0,0.5)",
      }}
    >
      {/* 封面占位 */}
      <div
        style={{
          height: 220,
          background: "linear-gradient(135deg,#ff8c6b 0%,#ff5f6d 60%,#d94e4e 100%)",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          color: "#fff",
          fontSize: 60,
        }}
      >
        {from === "left" ? "📅" : "📆"}
      </div>
      {/* 标题 */}
      <div style={{ padding: "14px 16px 6px", fontSize: 22, fontWeight: 700, color: "#1e293b" }}>
        {from === "left" ? "8月课题" : "7月课题"}
      </div>
      {/* 作者行 */}
      <div style={{ display: "flex", alignItems: "center", gap: 10, padding: "0 16px 12px" }}>
        <div style={{ width: 34, height: 34, borderRadius: "50%", background: "#ff6b6b", color: "#fff", display: "flex", alignItems: "center", justifyContent: "center", fontSize: 16 }}>我</div>
        <span style={{ fontSize: 15, color: "#64748b" }}>自我提升小号</span>
      </div>
      {/* 数据行 */}
      <div style={{ display: "flex", gap: 14, padding: "8px 16px 14px", borderTop: "1px solid #f1f5f9", color: "#94a3b8", fontSize: 13 }}>
        <span>▶ 901,234</span>
        <span>👍 7.1万</span>
      </div>
      {/* 置顶标 */}
      <div style={{ position: "absolute", top: 10, left: 10, background: "#ff2e4d", color: "#fff", fontSize: 13, padding: "3px 8px", borderRadius: 4 }}>
        置顶
      </div>
    </div>
  );
};

// ============================================================================
// 8. vignette 暗角（径向渐变黑边，开关动画）
// ============================================================================
const Vignette: React.FC = () => {
  const frame = useCurrentFrame();
  const on = interpolate(frame, [0, 15], [0, 0.85], {
    easing: Easing.in(Easing.quad),
    extrapolateRight: "clamp",
  });
  const off = interpolate(frame, [45, 60], [0.85, 0], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
  const o = Math.min(on, off);
  return (
    <AbsoluteFill>
      <div
        style={{
          position: "absolute",
          inset: 0,
          background:
            "radial-gradient(ellipse at center, rgba(0,0,0,0) 42%, rgba(0,0,0,0.95) 100%)",
          opacity: o,
        }}
      />
    </AbsoluteFill>
  );
};

// ============================================================================
// 9. 3D 礼物盒贴纸（缩放 + 旋转 pop，掌心弹出）
// ============================================================================
const GiftBox: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const s = spring({ frame, fps, config: { damping: 10, stiffness: 170 } });
  const rot = interpolate(s, [0, 1], [-30, 0]);
  return (
    <AbsoluteFill style={{ alignItems: "center", justifyContent: "center" }}>
      <div
        style={{
          width: 320,
          height: 320,
          position: "relative",
          transform: `scale(${s}) rotate(${rot}deg)`,
          filter: "drop-shadow(0 24px 40px rgba(0,0,0,0.5))",
        }}
      >
        {/* 盒子主体 */}
        <div
          style={{
            position: "absolute",
            left: 40,
            top: 90,
            width: 240,
            height: 190,
            borderRadius: 14,
            background: "linear-gradient(180deg,#ff7eb3 0%,#f4528c 100%)",
          }}
        />
        {/* 盖子 */}
        <div
          style={{
            position: "absolute",
            left: 28,
            top: 48,
            width: 264,
            height: 66,
            borderRadius: 12,
            background: "linear-gradient(180deg,#ff9cc7 0%,#f46a9e 100%)",
          }}
        />
        {/* 竖丝带 */}
        <div style={{ position: "absolute", left: 148, top: 48, width: 24, height: 232, background: "#ffd54f" }} />
        {/* 蝴蝶结 */}
        <div style={{ position: "absolute", left: 88, top: 8, fontSize: 130, lineHeight: 1 }}>🎀</div>
      </div>
    </AbsoluteFill>
  );
};

// ============================================================================
// 10. 撕纸边静态清单页（白底编号清单 + 蓝色数字图标 + 撕纸纹理）
// ============================================================================
const Checklist: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const fade = interpolate(frame, [0, 12], [0, 1], { extrapolateRight: "clamp" });
  const items = [
    "每天早上吃 2 颗水煮蛋",
    "每天按公式喝够水",
    "走路 8000 步",
    "每天把一张纸夹在膝盖中间",
    "一有时间就把舌头贴紧上颚",
    "难过压力大就闭眼观察呼吸",
    "10:30 放下手机、11 点睡觉",
  ];
  return (
    <AbsoluteFill style={{ background: "#ffffff", opacity: fade }}>
      <div style={{ padding: "90px 90px 120px", color: "#111" }}>
        <div style={{ fontSize: 54, fontWeight: 800, marginBottom: 40 }}>一个月改变挑战 · 清单</div>
        {items.map((t, i) => (
          <div key={i} style={{ display: "flex", alignItems: "center", gap: 20, marginBottom: 22 }}>
            <span
              style={{
                width: 52,
                height: 52,
                borderRadius: "50%",
                background: "#2f6fed",
                color: "#fff",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                fontSize: 24,
                fontWeight: 700,
                flexShrink: 0,
              }}
            >
              {i + 1}
            </span>
            <span style={{ fontSize: 30, fontWeight: 600, color: "#111" }}>{t}</span>
          </div>
        ))}
      </div>
      {/* 右下角撕纸边（锯齿 SVG） */}
      <svg
        width="220"
        height="160"
        viewBox="0 0 220 160"
        style={{ position: "absolute", right: 0, bottom: 0 }}
      >
        <path
          d="M 0 160 L 0 60 L 20 50 L 40 62 L 60 44 L 80 58 L 100 40 L 120 56 L 140 42 L 160 58 L 180 46 L 200 60 L 220 48 L 220 160 Z"
          fill="#e9e4da"
        />
      </svg>
    </AbsoluteFill>
  );
};

// ============================================================================
// 总览 showcase：按时序串联展示所有元素（22s @30fps = 660 帧）
// ============================================================================
const SEQ = [
  { from: 0, dur: 60, node: <SubtitleLine text="如果继续保持" style="white" /> },
  { from: 60, dur: 60, node: <><SubtitleLine text="基础饮水量(ml)=体重(kg)×30-35ml" style="blue" bottom="26%" /><SubtitleLine text="每天按照公式喝够水" style="yellow" bottom="16%" /></> },
  { from: 120, dur: 60, node: <BrowserFrame /> },
  { from: 180, dur: 75, node: <PipArrow /> },
  { from: 255, dur: 60, node: <CompareSplit /> },
  { from: 315, dur: 60, node: <ArcAnnotation /> },
  { from: 375, dur: 45, node: <WhipPan /> },
  { from: 420, dur: 60, node: <><XhsCard from="left" /><XhsCard from="right" /></> },
  { from: 480, dur: 60, node: <Vignette /> },
  { from: 540, dur: 60, node: <GiftBox /> },
  { from: 600, dur: 60, node: <Checklist /> },
];

export const ScriptReplicaShowcase: React.FC = () => {
  return (
    <AbsoluteFill style={{ background: `linear-gradient(180deg, ${C.bgTop}, ${C.bgBottom})`, fontFamily: FONT }}>
      {SEQ.map((s, i) => (
        <Sequence key={i} from={s.from} durationInFrames={s.dur}>
          <RoomBackdrop>{s.node}</RoomBackdrop>
        </Sequence>
      ))}
    </AbsoluteFill>
  );
};
