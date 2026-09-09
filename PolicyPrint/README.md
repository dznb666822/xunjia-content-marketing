# PolicyPrint

> 来源：https://github.com/Ancommie/PolicyPrint（Ancommie）
> 拉取方式：codeload zip 解压（GitHub 直连 git clone 在国内会 `schannel: server closed abruptly` 中断）

基于 `https://sousuo.www.gov.cn/`（中国政府网站内搜索）全文检索含指定主题关键词的公文条目，并打印成 PDF。

## 项目机制（源码读完后的真实情况）

- 依赖 **Selenium + Edge 浏览器 + msedgedriver**，用 `webdriver.Edge(headless)` 打开搜索页
- 搜索结果由 **JS 动态渲染**（`search.shtml` 初始 HTML 里没有公文链接，需等浏览器执行 JS）
- 下载的本质是 **`Page.printToPDF` CDP 命令把公文详情页"打印"成 PDF**，不是下载现成 PDF 文件
- 搜索接口需要 **`code` / `sign` 两个反爬校验参数**（有有效期，需从浏览器 Network 面板手动抓，脚本里当前为空）

## 集成到 xunjia-web 容器的障碍（实测结论）

| 门槛 | 说明 |
|---|---|
| 无 Edge | web 容器是 Python 3.11 slim（Linux），没有 Edge/msedgedriver，装浏览器很重 |
| code/sign 反爬 | 需手动抓 + 有有效期，无法硬编码 |
| JS 渲染 | 站内搜索结果是 JS 动态加载，纯 `requests` 拿不到列表 |

## 实测发现（可替代路径）

- `https://www.gov.cn/zhengce/zuixin/` 等政策列表页是**服务端渲染**，`requests` 可直接拿到公文详情页链接（`content_xxx.htm`）
- 即：**拿公文列表不需要 Selenium**；但"正文 → PDF"仍需 HTML→PDF 工具（weasyprint / wkhtmltopdf，容器内可装，无需浏览器）

## 结论

PolicyPrint **原样塞进 web 容器跑不通**（Edge + 反爬 + JS 渲染三座大山）。"下载 gov.cn 政策公文"可用更轻的 `requests` 方案替代（走政策文件库列表页，绕开站内搜索反爬），详见项目 memory 2026-09-09。
