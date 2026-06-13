interface Props {
  stats: {
    installers: number;
    logs: number;
    documents: number;
    registry: number;
  };
  totalFound: number;
  logs: string[];
}

export function Sidebar({ stats, totalFound, logs }: Props) {
  return (
    <aside className="w-56 bg-[#1b1b1c] border-r border-[#2a2a2a] flex flex-col overflow-hidden">
      {/* Stats */}
      <div className="p-4 border-b border-[#2a2a2a]">
        <h3 className="text-xs font-semibold text-[#8a919e] uppercase tracking-wider mb-3">
          统计
        </h3>
        <div className="space-y-2">
          <StatRow icon="📦" label="安装程序" value={stats.installers} />
          <StatRow icon="📝" label="日志/文本" value={stats.logs} />
          <StatRow icon="📄" label="文档" value={stats.documents} />
          <StatRow icon="📋" label="注册表" value={stats.registry} />
          <div className="pt-2 mt-2 border-t border-[#2a2a2a]">
            <StatRow icon="🔍" label="总计" value={totalFound} highlight />
          </div>
        </div>
      </div>

      {/* Logs */}
      <div className="flex-1 overflow-hidden flex flex-col">
        <h3 className="text-xs font-semibold text-[#8a919e] uppercase tracking-wider px-4 pt-3 pb-1">
          运行日志
        </h3>
        <div className="flex-1 overflow-auto px-4 pb-3">
          {logs.length === 0 ? (
            <span className="text-[#5a5a5a] text-xs">暂无日志</span>
          ) : (
            logs.map((line, i) => (
              <div key={i} className="text-xs text-[#8a919e] py-0.5 font-mono">
                {line}
              </div>
            ))
          )}
        </div>
      </div>

      {/* Shortcuts */}
      <div className="p-3 border-t border-[#2a2a2a]">
        <div className="text-[#5a5a5a] text-xs space-y-1">
          <div>Ctrl+A 全选</div>
          <div>Ctrl+C 复制</div>
          <div>Delete 删除</div>
        </div>
      </div>
    </aside>
  );
}

function StatRow({
  icon,
  label,
  value,
  highlight,
}: {
  icon: string;
  label: string;
  value: number;
  highlight?: boolean;
}) {
  return (
    <div className="flex items-center justify-between text-xs">
      <span className="flex items-center gap-1.5 text-[#8a919e]">
        <span>{icon}</span>
        {label}
      </span>
      <span
        className={`font-mono ${
          highlight ? "text-[#ffb597] font-semibold" : "text-[#a3c9ff]"
        }`}
      >
        {value}
      </span>
    </div>
  );
}
