import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Stock Research Agent",
  description: "AI 股票研究助手：输入公司名，自动生成研究报告",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="zh-CN" className="h-full antialiased">
      <body className="min-h-full flex flex-col">{children}</body>
    </html>
  );
}
