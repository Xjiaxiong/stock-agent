/**
 * Agent 执行进度列表。
 *
 * 状态规则：
 *   ✓  done    —— 该节点已完成（绿）
 *   ●  running —— 正在执行（蓝 + 呼吸动画）
 *   ○  pending —— 还没轮到（灰）
 *
 * 想改样式/动效：直接改下面 className 里的 tailwind 类即可。
 */

type StepStatus = "done" | "running" | "pending";

interface AgentProgressProps {
  steps: { node: string; label: string; status: StepStatus }[];
}

export default function AgentProgress({ steps }: AgentProgressProps) {
  return (
    <ol className="space-y-3 rounded-xl border border-zinc-200 bg-white p-5">
      {steps.map((step) => {
        const icon =
          step.status === "done" ? (
            <span className="text-green-600">✓</span>
          ) : step.status === "running" ? (
            <span className="inline-block animate-pulse text-blue-600">●</span>
          ) : (
            <span className="text-zinc-300">○</span>
          );

        const textColor =
          step.status === "done"
            ? "text-zinc-800"
            : step.status === "running"
              ? "font-medium text-blue-700"
              : "text-zinc-400";

        return (
          <li key={step.node} className="flex items-center gap-3">
            <span className="w-5 text-center">{icon}</span>
            <span className={textColor}>{step.label}</span>
            {step.status === "running" && (
              <span className="text-xs text-blue-500">处理中…</span>
            )}
          </li>
        );
      })}
    </ol>
  );
}
