type ScanPhase = "Idle" | "Registry" | "FixedPaths" | "FullScan" | "Complete";

interface Props {
  phase: ScanPhase;
}

const PHASES: { key: ScanPhase; label: string }[] = [
  { key: "Registry", label: "注册表检测" },
  { key: "FixedPaths", label: "固定路径检测" },
  { key: "FullScan", label: "全盘文件扫描" },
];

export function PhaseProgress({ phase }: Props) {
  const currentIdx = PHASES.findIndex((p) => p.key === phase);
  const isComplete = phase === "Complete";

  return (
    <div className="flex items-center gap-3 px-5 py-2 border-b border-[#2a2a2a]">
      {PHASES.map((p, i) => {
        const isActive = i === currentIdx;
        const isDone = isComplete || i < currentIdx;

        return (
          <div key={p.key} className="flex items-center gap-2">
            <div
              className={`w-2 h-2 rounded-full ${
                isDone ? "bg-[#0078d4]" : isActive ? "bg-[#0078d4] animate-pulse" : "bg-[#353535]"
              }`}
            />
            <span
              className={`text-xs ${
                isDone || isActive ? "text-[#e5e2e1]" : "text-[#5a5a5a]"
              }`}
            >
              {p.label}
            </span>
            {i < PHASES.length - 1 && (
              <div
                className={`w-8 h-px ${
                  isDone || (isActive && i === currentIdx - 1)
                    ? "bg-[#0078d4]"
                    : "bg-[#2a2a2a]"
                }`}
              />
            )}
          </div>
        );
      })}

      {isComplete && (
        <span className="text-xs text-[#4caf50] ml-2">✓ 扫描完成</span>
      )}
    </div>
  );
}
