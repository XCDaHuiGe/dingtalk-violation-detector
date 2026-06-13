import { useEffect, useRef } from "react";

interface Props {
  x: number;
  y: number;
  path: string;
  onClose: () => void;
  onOpenInExplorer: (path: string) => void;
  onCopy: (path: string) => void;
}

export function ContextMenu({ x, y, path, onClose, onOpenInExplorer, onCopy }: Props) {
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) {
        onClose();
      }
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, [onClose]);

  const items = [
    { label: "打开文件位置", action: () => onOpenInExplorer(path) },
    { label: "复制路径", action: () => onCopy(path) },
  ];

  return (
    <div
      ref={ref}
      className="fixed z-50 bg-[#202020] border border-[#353535] rounded shadow-lg py-1 min-w-[140px]"
      style={{ left: x, top: y }}
    >
      {items.map((item) => (
        <button
          key={item.label}
          className="w-full text-left px-3 py-1.5 text-xs text-[#e5e2e1] hover:bg-[#2a2a2a]"
          onClick={item.action}
        >
          {item.label}
        </button>
      ))}
    </div>
  );
}
