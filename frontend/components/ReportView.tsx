/**
 * Markdown 报告渲染。
 *
 * react-markdown 负责把 Markdown 文本渲染成 HTML。
 * components 属性里可以自定义每种标签的样式；
 * 想换报告排版，改这里最方便。
 *
 * 注意：react-markdown 默认只认 CommonMark，**不解析表格**（GFM 扩展语法）。
 * 报告里的 `| 板块 | 指数涨幅 | ... |` 如果不挂 remark-gfm，会被当成普通段落，
 * 换行还会被压成空格，屏幕上就是一长串竖线。所以下面必须带 remarkGfm。
 */

import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

export default function ReportView({ report }: { report: string }) {
  return (
    <article className="rounded-xl border border-zinc-200 bg-white p-8 shadow-sm">
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
          h1: ({ children }) => (
            <h1 className="mb-6 border-b border-zinc-200 pb-4 text-2xl font-bold tracking-tight text-zinc-900">
              {children}
            </h1>
          ),
          h2: ({ children }) => (
            <h2 className="mb-3 mt-9 flex items-center gap-2 text-lg font-semibold text-zinc-900">
              <span className="h-4 w-1 rounded-full bg-blue-500" />
              {children}
            </h2>
          ),
          h3: ({ children }) => (
            <h3 className="mb-2 mt-5 text-base font-semibold text-zinc-800">
              {children}
            </h3>
          ),
          p: ({ children }) => (
            <p className="my-3 leading-7 text-zinc-700">{children}</p>
          ),
          ul: ({ children }) => (
            <ul className="my-3 list-disc space-y-1.5 pl-6 text-zinc-700 marker:text-zinc-400">
              {children}
            </ul>
          ),
          ol: ({ children }) => (
            <ol className="my-3 list-decimal space-y-1.5 pl-6 text-zinc-700 marker:text-zinc-400">
              {children}
            </ol>
          ),
          li: ({ children }) => <li className="leading-7">{children}</li>,
          strong: ({ children }) => (
            <strong className="font-semibold text-zinc-900">{children}</strong>
          ),
          blockquote: ({ children }) => (
            <blockquote className="my-4 rounded-r-lg border-l-4 border-amber-300 bg-amber-50/60 py-2 pl-4 text-sm text-zinc-600">
              {children}
            </blockquote>
          ),
          hr: () => <hr className="my-8 border-zinc-200" />,
          table: ({ children }) => (
            <div className="my-5 overflow-x-auto rounded-lg border border-zinc-200">
              <table className="w-full border-collapse text-[13px] [&_tr:last-child>td]:border-b-0">
                {children}
              </table>
            </div>
          ),
          thead: ({ children }) => <thead className="bg-zinc-50">{children}</thead>,
          th: ({ children }) => (
            <th className="whitespace-nowrap border-b border-zinc-200 px-3 py-2 text-left font-medium text-zinc-600">
              {children}
            </th>
          ),
          td: ({ children }) => (
            <td className="whitespace-nowrap border-b border-zinc-100 px-3 py-2 text-zinc-700">
              {children}
            </td>
          ),
          code: ({ children }) => (
            <code className="rounded bg-zinc-100 px-1.5 py-0.5 text-[13px] text-zinc-800">
              {children}
            </code>
          ),
        }}
      >
        {report}
      </ReactMarkdown>
    </article>
  );
}
