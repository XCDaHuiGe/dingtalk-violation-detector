interface Props {
  scanned: number;
  found: number;
  speed: number;
  elapsed: number;
}

export function StatsPanel({ scanned, found, speed, elapsed }: Props) {
  const fmt = (n: number) => n.toLocaleString();
  const fmtSpeed = (s: number) =>
    s > 1000 ? `${(s / 1000).toFixed(1)}k/s` : `${s.toFixed(0)}/s`;
  const fmtTime = (secs: number) => {
    const m = Math.floor(secs / 60);
    const s = secs % 60;
    return m > 0 ? `${m}分${s}秒` : `${s}秒`;
  };

  return (
    <div className="flex items-center gap-6 px-5 py-2 bg-[#1b1b1c]/50 border-b border-[#2a2a2a] text-xs">
      <Stat label="已扫描" value={fmt(scanned)} />
      <Stat label="发现数" value={fmt(found)} color="text-[#ffb597]" />
      <Stat label="速度" value={fmtSpeed(speed)} />
      <Stat label="用时" value={fmtTime(elapsed)} />
    </div>
  );
}

function Stat({
  label,
  value,
  color,
}: {
  label: string;
  value: string;
  color?: string;
}) {
  return (
    <div className="flex items-center gap-1.5">
      <span className="text-[#8a919e]">{label}:</span>
      <span className={`font-mono ${color || "text-[#a3c9ff]"}`}>{value}</span>
    </div>
  );
}
