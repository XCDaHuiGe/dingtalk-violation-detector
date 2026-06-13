interface Props {
  value: string;
  onChange: (v: string) => void;
  disabled: boolean;
}

export function NameInput({ value, onChange, disabled }: Props) {
  return (
    <div className="flex items-center gap-2">
      <svg className="w-4 h-4 text-[#8a919e]" fill="none" viewBox="0 0 24 24" stroke="currentColor">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" />
      </svg>
      <input
        type="text"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        disabled={disabled}
        placeholder="被检测人姓名"
        className="bg-[#0e0e0e] border border-[#2a2a2a] rounded px-3 py-1.5 text-sm text-[#e5e2e1] placeholder-[#5a5a5a] focus:outline-none focus:border-[#0078d4] w-44 disabled:opacity-50"
      />
    </div>
  );
}
