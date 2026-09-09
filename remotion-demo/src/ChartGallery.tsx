import React from "react";
import {
  AbsoluteFill,
  useCurrentFrame,
  interpolate,
} from "remotion";
import { LineChart3D } from "./LineChart3D";
import { BarChart3D } from "./BarChart3D";
import { PieChart3D } from "./PieChart3D";
import { RankBars } from "./RankBars";
import { ProgressRing } from "./ProgressRing";

// —— Chart 总览片 ——
// 5 段依次播放：折线 → 柱状 → 饼图 → 排行 → 进度环
// 每段 100f，其中前 10f 切换淡入淡出

const TOTAL_DURATION = 510;
const SEG_DUR = 100;       // 每段 100f
const SWITCH_FRAMES = 18;  // 段间淡入淡出过渡

const seg = (i: number) => ({ start: i * SEG_DUR, length: SEG_DUR });

export const ChartGallery: React.FC = () => {
  const frame = useCurrentFrame();

  // 渲染分段
  const s0 = seg(0);
  const s1 = seg(1);
  const s2 = seg(2);
  const s3 = seg(3);
  const s4 = seg(4);

  return (
    <AbsoluteFill style={{ background: "#05050e" }}>
      {/* 折线段 */}
      <Segment
        frame={frame}
        start={s0.start}
        length={s0.length}
        switchFrames={SWITCH_FRAMES}
      >
        <LineChart3D
          title="主要产油国石油产量"
          subtitle="1990 – 2025 · 多国对比"
          unit="百万桶/日"
          captionHi="美国成为全球第一大产油国"
          captionSub="the United States became the world's No.1 oil producer (2024)"
          years={[1990, 1995, 2000, 2005, 2010, 2015, 2020, 2025]}
          series={[
            { name: "美国", color: "#d94e4e", values: [9.0, 9.4, 9.8, 9.0, 10.5, 14.5, 17.5, 22.0] },
            { name: "沙特", color: "#3f9d63", values: [7.5, 8.5, 10.5, 11.0, 10.5, 12.0, 11.0, 10.5] },
            { name: "俄罗斯", color: "#e8a838", values: [10.0, 7.0, 6.5, 9.5, 10.5, 11.0, 10.5, 10.8] },
            { name: "中国", color: "#4f7ff0", values: [2.8, 3.0, 3.3, 3.6, 4.1, 4.3, 4.9, 5.0] },
          ]}
          maxValue={24}
          timeOffset={frame - s0.start}
        />
      </Segment>

      {/* 柱状段 */}
      <Segment
        frame={frame}
        start={s1.start}
        length={s1.length}
        switchFrames={SWITCH_FRAMES}
      >
        <BarChart3D
          title="全球 GDP Top 5 国家"
          subtitle="2023 财年 · 单位：万亿美元"
          captionHi="中美领跑,日本第三"
          captionSub="China & U.S. lead, Japan ranks 3rd"
          categories={["中国", "美国", "日本", "德国", "印度"]}
          values={[17.7, 27.4, 4.2, 4.1, 3.7]}
          maxValue={30}
          accent="#4f7ff0"
          accent2="#36b8c4"
          timeOffset={frame - s1.start}
        />
      </Segment>

      {/* 饼图段 */}
      <Segment
        frame={frame}
        start={s2.start}
        length={s2.length}
        switchFrames={SWITCH_FRAMES}
      >
        <PieChart3D
          title="全球电商市场份额"
          subtitle="2023 估算 · 主流平台 TOP 5"
          captionHi="亚马逊稳居第一,中系三强紧追"
          captionSub="Amazon leads, Chinese trio紧随"
          slices={[
            { label: "亚马逊", value: 26, color: "#e8a838" },
            { label: "淘宝", value: 22, color: "#d94e4e" },
            { label: "京东", value: 16, color: "#3f9d63" },
            { label: "拼多多", value: 12, color: "#4f7ff0" },
            { label: "其他", value: 24, color: "#b366d9" },
          ]}
          centerLabel="TOTAL"
          centerValue="100%"
          timeOffset={frame - s2.start}
        />
      </Segment>

      {/* 排行段 */}
      <Segment
        frame={frame}
        start={s3.start}
        length={s3.length}
        switchFrames={SWITCH_FRAMES}
      >
        <RankBars
          title="2024 最受欢迎编程语言"
          subtitle="按开发者使用率 · TIOBE / Stack Overflow 综合"
          captionHi="Python 连续 3 年霸榜"
          captionSub="Python leads for 3 consecutive years"
          items={[
            { rank: 1, label: "Python", sub: "AI / 数据科学首选", icon: "🐍", color: "#e8a838", score: 96, badge: "TOP 1" },
            { rank: 2, label: "JavaScript", sub: "Web 全栈", icon: "🌐", color: "#4f7ff0", score: 87 },
            { rank: 3, label: "Java", sub: "企业后端", icon: "☕", color: "#d94e4e", score: 72 },
            { rank: 4, label: "C++", sub: "系统/游戏", icon: "⚙️", color: "#36b8c4", score: 64 },
            { rank: 5, label: "Go", sub: "云原生", icon: "🚀", color: "#3f9d63", score: 53 },
          ]}
          timeOffset={frame - s3.start}
        />
      </Segment>

      {/* 进度环段 */}
      <Segment
        frame={frame}
        start={s4.start}
        length={Math.max(SEG_DUR, TOTAL_DURATION - s4.start)}
        switchFrames={SWITCH_FRAMES}
      >
        <ProgressRing
          title="中国一次能源消费结构"
          subtitle="2022 · 4 类占比 / 在能源消费总量中"
          captionHi="可再生能源占比上升至 17%"
          captionSub="Renewable share rises to 17%"
          items={[
            { label: "煤炭", value: 56, color: "#1f1f1f" },
            { label: "石油", value: 18, color: "#d94e4e" },
            { label: "天然气", value: 9, color: "#3f9d63" },
            { label: "可再生能源", value: 17, color: "#36b8c4" },
          ]}
          centerLabel="碳强度"
          centerValue="100"
          timeOffset={frame - s4.start}
        />
      </Segment>
    </AbsoluteFill>
  );
};

// 段落帧包装器：每段前 18f 淡入、后 18f 淡出（重叠淡入淡出）
const Segment: React.FC<{
  frame: number;
  start: number;
  length: number;
  switchFrames: number;
  children: React.ReactNode;
}> = ({ frame, start, length, switchFrames, children }) => {
  const local = frame - start;
  if (local < 0 || local > length) return null;
  const fadeIn = interpolate(local, [0, switchFrames], [0, 1], { extrapolateRight: "clamp" });
  const fadeOut = interpolate(local, [length - switchFrames, length], [1, 0], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
  const op = Math.min(fadeIn, fadeOut);
  return (
    <AbsoluteFill style={{ opacity: op }}>
      {children}
    </AbsoluteFill>
  );
};
