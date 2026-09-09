import React from "react";
import { Composition } from "remotion";
import { PetAd } from "./PetAd";
import { DataReport3D } from "./DataReport3D";
import { FormulaDemo } from "./FormulaDemo";
import { LineChart3D } from "./LineChart3D";
import { BarChart3D } from "./BarChart3D";
import { PieChart3D } from "./PieChart3D";
import { RankBars } from "./RankBars";
import { ProgressRing } from "./ProgressRing";
import { ChartGallery } from "./ChartGallery";
import { ScriptReplicaShowcase } from "./ScriptReplica";

export const RemotionRoot: React.FC = () => {
  return (
    <>
      {/* 旧 demo composition（保持 ID 向后兼容，内部走 LineChart3D） */}
      <Composition
        id="PetAd"
        component={PetAd}
        durationInFrames={150}
        fps={30}
        width={720}
        height={1280}
      />
      <Composition
        id="DataReport3D"
        component={DataReport3D}
        durationInFrames={210}
        fps={30}
        width={1080}
        height={1920}
      />
      <Composition
        id="FormulaDemo"
        component={FormulaDemo}
        durationInFrames={270}
        fps={30}
        width={1080}
        height={1920}
      />

      {/* 数据图表组件库 · 5 大类 */}
      <Composition
        id="LineChart3D"
        component={LineChart3D}
        durationInFrames={210}
        fps={30}
        width={1080}
        height={1920}
        defaultProps={{
          title: "主要产油国石油产量",
          subtitle: "1990 – 2025 · 多国对比",
          unit: "百万桶/日",
          captionHi: "美国成为全球第一大产油国",
          captionSub: "the United States became the world's No.1 oil producer (2024)",
          years: [1990, 1995, 2000, 2005, 2010, 2015, 2020, 2025],
          series: [
            { name: "美国", color: "#d94e4e", values: [9.0, 9.4, 9.8, 9.0, 10.5, 14.5, 17.5, 22.0] },
            { name: "沙特", color: "#3f9d63", values: [7.5, 8.5, 10.5, 11.0, 10.5, 12.0, 11.0, 10.5] },
            { name: "俄罗斯", color: "#e8a838", values: [10.0, 7.0, 6.5, 9.5, 10.5, 11.0, 10.5, 10.8] },
            { name: "中国", color: "#4f7ff0", values: [2.8, 3.0, 3.3, 3.6, 4.1, 4.3, 4.9, 5.0] },
          ],
          maxValue: 24,
        }}
      />
      <Composition
        id="BarChart3D"
        component={BarChart3D}
        durationInFrames={210}
        fps={30}
        width={1080}
        height={1920}
        defaultProps={{
          title: "全球 GDP Top 5 国家",
          subtitle: "2023 财年 · 单位：万亿美元",
          captionHi: "中美领跑,日本第三",
          captionSub: "China & U.S. lead, Japan ranks 3rd",
          categories: ["中国", "美国", "日本", "德国", "印度"],
          values: [17.7, 27.4, 4.2, 4.1, 3.7],
          maxValue: 30,
          unit: "万亿美元",
        }}
      />
      <Composition
        id="PieChart3D"
        component={PieChart3D}
        durationInFrames={210}
        fps={30}
        width={1080}
        height={1920}
        defaultProps={{
          title: "全球电商市场份额",
          subtitle: "2023 估算 · 主流平台 TOP 5",
          captionHi: "亚马逊稳居第一,中系三强紧追",
          captionSub: "Amazon leads, Chinese trio紧随",
          slices: [
            { label: "亚马逊", value: 26, color: "#e8a838" },
            { label: "淘宝", value: 22, color: "#d94e4e" },
            { label: "京东", value: 16, color: "#3f9d63" },
            { label: "拼多多", value: 12, color: "#4f7ff0" },
            { label: "其他", value: 24, color: "#b366d9" },
          ],
          centerLabel: "TOTAL",
          centerValue: "100%",
        }}
      />
      <Composition
        id="RankBars"
        component={RankBars}
        durationInFrames={210}
        fps={30}
        width={1080}
        height={1920}
        defaultProps={{
          title: "2024 最受欢迎编程语言",
          subtitle: "按开发者使用率 · TIOBE / Stack Overflow 综合",
          captionHi: "Python 连续 3 年霸榜",
          captionSub: "Python leads for 3 consecutive years",
          items: [
            { rank: 1, label: "Python", sub: "AI / 数据科学首选", icon: "🐍", color: "#e8a838", score: 96, badge: "TOP 1" },
            { rank: 2, label: "JavaScript", sub: "Web 全栈", icon: "🌐", color: "#4f7ff0", score: 87 },
            { rank: 3, label: "Java", sub: "企业后端", icon: "☕", color: "#d94e4e", score: 72 },
            { rank: 4, label: "C++", sub: "系统/游戏", icon: "⚙️", color: "#36b8c4", score: 64 },
            { rank: 5, label: "Go", sub: "云原生", icon: "🚀", color: "#3f9d63", score: 53 },
          ],
        }}
      />
      <Composition
        id="ProgressRing"
        component={ProgressRing}
        durationInFrames={210}
        fps={30}
        width={1080}
        height={1920}
        defaultProps={{
          title: "中国一次能源消费结构",
          subtitle: "2022 · 4 类占比 / 在能源消费总量中",
          captionHi: "可再生能源占比上升至 17%",
          captionSub: "Renewable share rises to 17%",
          items: [
            { label: "煤炭", value: 56, color: "#1f1f1f" },
            { label: "石油", value: 18, color: "#d94e4e" },
            { label: "天然气", value: 9, color: "#3f9d63" },
            { label: "可再生能源", value: 17, color: "#36b8c4" },
          ],
          centerLabel: "碳强度",
          centerValue: "100",
        }}
      />

      {/* 总览片 · 5 段串联 */}
      <Composition
        id="ChartGallery"
        component={ChartGallery}
        durationInFrames={510}
        fps={30}
        width={1080}
        height={1920}
      />

      {/* 参考脚本可复刻元素 showcase（口播剪辑特效/字幕库） */}
      <Composition
        id="ScriptReplica"
        component={ScriptReplicaShowcase}
        durationInFrames={660}
        fps={30}
        width={1080}
        height={1920}
      />
    </>
  );
};
