import { useState, useMemo } from "react";
import type { DetectionResult } from "../App";

interface Props {
  results: DetectionResult[];
  selected: Set<string>;
  onToggle: (path: string) => void;
  onContextMenu: (e: React.MouseEvent, path: string) => void;
  onOpenInExplorer: (path: string) => void;
}

function fmtSize(bytes: number): string {
  if (bytes === 0) return "-";
  const units = ["B", "KB", "MB", "GB"];
  let i = 0;
  let size = bytes;
  while (size >= 1024 && i < units.length - 1) {
    size /= 1024;
    i++;
  }
  return `${size.toFixed(i === 0 ? 0 : 1)} ${units[i]}`;
}

function typeIcon(fileType: string): string {
  switch (fileType) {
    case "安装程序": return "📦";
    case "压缩包": return "🗜️";
    case "文档": return "📄";
    case "视频": return "🎬";
    case "音频": return "🎵";
    case "日志/文本": return "📝";
    case "配置文件": return "⚙️";
    case "临时/缓存": return "🗑️";
    case "系统文件": return "⚡";
    case "快捷方式": return "🔗";
    case "目录": return "📁";
    case "注册表项": return "📋";
    default: return "📄";
  }
}

export function ResultTree({
  results,
  selected,
  onToggle,
  onContextMenu,
  onOpenInExplorer,
}: Props) {
  const [collapsedDirs, setCollapsedDirs] = useState<Set<string>>(new Set());

  const grouped = useMemo(() => {
    const map = new Map<string, DetectionResult[]>();
    for (const r of results) {
      const dir = r.source === "注册表扫描"
        ? "注册表"
        : r.path.substring(0, r.path.lastIndexOf("\\"));
      const key = dir || "其他";
      if (!map.has(key)) map.set(key, []);
      map.get(key)!.push(r);
    }
    return Array.from(map.entries()).sort(([a], [b]) => a.localeCompare(b));
  }, [results]);

  const toggleDir = (dir: string) => {
    setCollapsedDirs((prev) => {
      const next = new Set(prev);
      if (next.has(dir)) next.delete(dir);
      else next.add(dir);
      return next;
    });
  };

  return (
    <table className="w-full text-xs">
      <thead>
        <tr className="text-[#8a919e] border-b border-[#2a2a2a]">
          <th className="w-8 py-1.5 text-left" />
          <th className="py-1.5 text-left w-16">类型</th>
          <th className="py-1.5 text-left">名称</th>
          <th className="py-1.5 text-left">路径</th>
          <th className="py-1.5 text-right w-20">大小</th>
        </tr>
      </thead>
      <tbody>
        {grouped.map(([dir, items]) => {
          const isCollapsed = collapsedDirs.has(dir);
          return (
            <>
              {/* Directory header */}
              <tr
                key={dir}
                className="text-[#a3c9ff] hover:bg-[#1b1b1c] cursor-pointer"
                onClick={() => toggleDir(dir)}
              >
                <td className="py-1 pl-1">
                  <span className="select-none">{isCollapsed ? "▶" : "▼"}</span>
                </td>
                <td className="py-1" colSpan={4}>
                  <span className="font-medium">{dir}</span>
                  <span className="text-[#5a5a5a] ml-2">({items.length} 项)</span>
                </td>
              </tr>

              {!isCollapsed &&
                items.map((r) => (
                  <tr
                    key={r.path}
                    className="hover:bg-[#1b1b1c] border-b border-[#1b1b1c] group"
                    onContextMenu={(e) => onContextMenu(e, r.path)}
                  >
                    <td className="py-1 pl-2">
                      <input
                        type="checkbox"
                        checked={selected.has(r.path)}
                        onChange={() => onToggle(r.path)}
                        className="accent-[#0078d4] w-3 h-3"
                      />
                    </td>
                    <td className="py-1 text-[#8a919e]" title={r.file_type}>
                      {typeIcon(r.file_type)}
                    </td>
                    <td className="py-1 text-[#e5e2e1] max-w-[240px] truncate" title={r.filename}>
                      {r.filename}
                    </td>
                    <td
                      className="py-1 text-[#8a919e] max-w-[400px] truncate cursor-pointer hover:text-[#a3c9ff]"
                      title={r.path}
                      onDoubleClick={() => onOpenInExplorer(r.path)}
                    >
                      {r.path}
                    </td>
                    <td className="py-1 text-right text-[#5a5a5a] font-mono">
                      {fmtSize(r.size)}
                    </td>
                  </tr>
                ))}
            </>
          );
        })}
      </tbody>
    </table>
  );
}
