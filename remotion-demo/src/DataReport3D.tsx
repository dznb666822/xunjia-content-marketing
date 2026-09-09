// 历史 Composition ID：保持向后兼容，内部直接使用参数化的 LineChart3D
import React from "react";
import { LineChart3D } from "./LineChart3D";

export const DataReport3D: React.FC = () => (
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
  />
);
