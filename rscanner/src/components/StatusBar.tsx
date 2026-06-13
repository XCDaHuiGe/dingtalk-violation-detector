type ScanPhase = "Idle" | "Registry" | "FixedPaths" | "FullScan" | "Complete";

interface Props {
  phase: ScanPhase;
  selectedCount: number;
  totalCount: number;
}

export function StatusBar({ phase, selectedCount, totalCount }: Props) {
  const phaseLabels: Record<ScanPhase, string> = {
    Idle: "就绪",
    Registry: "注册表检测中...",
    FixedPaths: "固定路径检测中...",
    FullScan: "全盘扫描中...",
    Complete: "扫描完成",
  };

  return (
    <footer className="flex items-center justify-between px-5 py-1.5 bg-[#0e0e0e] border-t border-[#2a2a2a] text-xs text-[#5a5a5a]">
      <span>{phaseLabels[phase]}</span>
      <span>
        已选 {selectedCount} / 共 {totalCount} 项
      </span>
    </footer>
  );
}
