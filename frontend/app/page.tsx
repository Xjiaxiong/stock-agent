/** 首页：一个简单的入口，指向 /analysis */

import Link from "next/link";

export default function Home() {
  return (
    <main className="flex min-h-screen flex-col items-center justify-center gap-6 bg-zinc-50 px-6">
      <div className="text-center">
        <h1 className="text-4xl font-bold tracking-tight text-zinc-900">
          Stock Research Agent
        </h1>
        <p className="mt-4 max-w-md text-zinc-500">
          输入一家公司，Agent 自动完成行情、新闻、财务、风险分析，生成研究报告。
        </p>
      </div>
      <Link
        href="/analysis"
        className="rounded-lg bg-blue-600 px-6 py-3 font-medium text-white transition hover:bg-blue-700"
      >
        开始研究 →
      </Link>
    </main>
  );
}
