interface Props {
  isScanning: boolean;
  hasResults: boolean;
  hasSelection: boolean;
  onStart: () => void;
  onCancel: () => void;
  onDelete: () => void;
  onSelectAll: () => void;
  onDeselectAll: () => void;
  onCopyPaths: () => void;
  onCleanRegistry: () => void;
  onSendReport: () => void;
}

export function ActionBar({
  isScanning,
  hasResults,
  hasSelection,
  onStart,
  onCancel,
  onDelete,
  onSelectAll,
  onDeselectAll,
  onCopyPaths,
  onCleanRegistry,
  onSendReport,
}: Props) {
  const btn =
    "px-3 py-1.5 text-sm rounded transition-colors disabled:opacity-40 disabled:cursor-not-allowed";

  return (
    <div className="flex items-center gap-2">
      <button
        onClick={onStart}
        disabled={isScanning}
        className={`${btn} bg-[#0078d4] text-white hover:bg-[#006cbe] flex items-center gap-1`}
      >
        <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 24 24">
          <path d="M8 5v14l11-7z" />
        </svg>
        开始
      </button>

      <button
        onClick={onCancel}
        disabled={!isScanning}
        className={`${btn} bg-[#4a4a4a] text-[#e5e2e1] hover:bg-[#5a5a5a]`}
      >
        取消
      </button>

      <div className="w-px h-6 bg-[#2a2a2a]" />

      <button
        onClick={onSelectAll}
        disabled={!hasResults}
        className={`${btn} text-[#8a919e] hover:text-[#e5e2e1] hover:bg-[#2a2a2a]`}
      >
        全选
      </button>

      <button
        onClick={onDeselectAll}
        disabled={!hasSelection}
        className={`${btn} text-[#8a919e] hover:text-[#e5e2e1] hover:bg-[#2a2a2a]`}
      >
        取消全选
      </button>

      <button
        onClick={onDelete}
        disabled={!hasSelection}
        className={`${btn} text-[#ffb4ab] hover:bg-[#93000a]/30 disabled:text-[#5a3a3a]`}
      >
        删除所选
      </button>

      <button
        onClick={onCopyPaths}
        disabled={!hasSelection}
        className={`${btn} text-[#8a919e] hover:text-[#e5e2e1] hover:bg-[#2a2a2a]`}
      >
        复制路径
      </button>

      <div className="w-px h-6 bg-[#2a2a2a]" />

      <button
        onClick={onCleanRegistry}
        className={`${btn} text-[#ffb597] hover:bg-[#4d1a00]/30`}
      >
        清理注册表
      </button>

      <button
        onClick={onSendReport}
        disabled={!hasResults}
        className={`${btn} bg-[#0078d4]/20 text-[#a3c9ff] hover:bg-[#0078d4]/30`}
      >
        上报
      </button>
    </div>
  );
}
