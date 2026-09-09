// 图表库统一主题 —— 给所有 Chart* 组件共用
// 留出 PALETTE/TYPE/SHADOW 的扩展接口,后续 Style 套件可直接替换 theme 实现主题切换

export const PALETTE = {
  ink: "#ffffff",
  inkMuted: "rgba(255,255,255,0.65)",
  inkDim: "rgba(255,255,255,0.35)",
  paperBg: "linear-gradient(180deg, #ffffff 0%, #ecece6 100%)",
  paperGrid: "rgba(0,0,0,0.10)",
  paperAxis: "rgba(0,0,0,0.40)",
  paperInk: "#1a1a1a",
  paperInkMuted: "rgba(0,0,0,0.55)",
  // 默认系列色板（折线/饼图/排行共用，按顺序取）
  series: ["#d94e4e", "#3f9d63", "#e8a838", "#4f7ff0", "#b366d9", "#36b8c4"],
  bar: ["#4f7ff0", "#36b8c4", "#3f9d63", "#e8a838", "#d94e4e", "#b366d9"],
  // 强调渐变
  accent: "linear-gradient(90deg, #4f7ff0, #d94e4e)",
};

export const TYPE = {
  titleHi: 56,
  titleSub: 24,
  captionHi: 46,
  captionSub: 23,
  paperAxis: 13,
  paperAxisYear: 14,
  legend: 16,
  paperTick: 16,
};

export const SHADOW = {
  dropStrong:
    "0 90px 150px rgba(0,0,0,0.75), 0 30px 60px rgba(0,0,0,0.5), inset 0 1px 0 rgba(255,255,255,0.9)",
};

// Catmull-Rom → 三次贝塞尔：把一组数据点转成平滑曲线 SVG path
// （每个 chart 独立渲染时不需要拉 @remotion/paths/d3-shape 的依赖）
export function smoothPath(xs: number[], ys: number[]): string {
  if (xs.length < 2) return "";
  let d = `M ${xs[0].toFixed(1)} ${ys[0].toFixed(1)}`;
  for (let i = 1; i < xs.length; i++) {
    const x0 = xs[i - 2] ?? xs[i - 1];
    const y0 = ys[i - 2] ?? ys[i - 1];
    const x1 = xs[i - 1];
    const y1 = ys[i - 1];
    const x2 = xs[i];
    const y2 = ys[i];
    const x3 = xs[i + 1] ?? x2;
    const y3 = ys[i + 1] ?? y2;
    const c1x = x1 + (x2 - x0) / 6;
    const c1y = y1 + (y2 - y0) / 6;
    const c2x = x2 - (x3 - x1) / 6;
    const c2y = y2 - (y3 - y1) / 6;
    d += ` C ${c1x.toFixed(1)} ${c1y.toFixed(1)}, ${c2x.toFixed(1)} ${c2y.toFixed(1)}, ${x2.toFixed(1)} ${y2.toFixed(1)}`;
  }
  return d;
}

// 通用：底部红蓝渐变短色条（电影感字幕块底部装饰）
export function AccentBar({ width = 68 }: { width?: number }) {
  return (
    <div
      style={{
        margin: "22px auto 0",
        width: width,
        height: 4,
        borderRadius: 2,
        background: PALETTE.accent,
      }}
    />
  );
}
