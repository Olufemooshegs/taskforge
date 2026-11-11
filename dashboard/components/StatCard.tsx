export default function StatCard({
  label, value, hint, tone = 'default',
}: {
  label: string;
  value: string | number;
  hint?: string;
  tone?: 'default' | 'good' | 'warn' | 'bad';
}) {
  const tones = {
    default: 'border-slate-200',
    good: 'border-green-300',
    warn: 'border-amber-300',
    bad: 'border-red-300',
  };
  return (
    <div className={`bg-white rounded border ${tones[tone]} p-4`}>
      <div className="text-xs text-slate-500 uppercase tracking-wide">{label}</div>
      <div className="text-2xl font-semibold mt-1">{value}</div>
      {hint && <div className="text-xs text-slate-500 mt-1">{hint}</div>}
    </div>
  );
}
