/**
 * Markdown 报告渲染。
 *
 * react-markdown 负责把 Markdown 文本渲染成 HTML。
 * components 属性里可以自定义每种标签的样式；
 * 想换报告排版，改这里最方便。
 */

import ReactMarkdown from "react-markdown";

export default function ReportView({ report }: { report: string }) {
  return (
    <article className="rounded-xl border border-zinc-200 bg-white p-8">
      <ReactMarkdown
        components={{
          h1: ({ children }) => (
            <h1 className="mb-6 border-b border-zinc-200 pb-4 text-3xl font-bold text-zinc-900">
              {children}
            </h1>
          ),
          h2: ({ children }) => (
            <h2 className="mb-3 mt-8 text-xl font-semibold text-zinc-900">
              {children}
            </h2>
          ),
          p: ({ children }) => (
            <p className="my-3 leading-7 text-zinc-700">{children}</p>
          ),
          ul: ({ children }) => (
            <ul className="my-3 list-disc space-y-1 pl-6 text-zinc-700">
              {children}
            </ul>
          ),
          blockquote: ({ children }) => (
            <blockquote className="my-4 border-l-4 border-zinc-300 pl-4 text-sm text-zinc-500">
              {children}
            </blockquote>
          ),
        }}
      >
        {report}
      </ReactMarkdown>
    </article>
  );
}
