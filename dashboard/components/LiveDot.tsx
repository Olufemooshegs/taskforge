export default function LiveDot({
  tone = 'idle',
  pulse = false,
  size = 'sm',
}: {
  tone?: 'good' | 'warn' | 'bad' | 'idle' | 'info';
  pulse?: boolean;
  size?: 'xs' | 'sm' | 'md';
}) {
  const colors: Record<string, string> = {
    good: 'bg-accent',
    warn: 'bg-warn',
    bad: 'bg-danger',
    idle: 'bg-dim',
    info: 'bg-info',
  };
  const sizes: Record<string, string> = {
    xs: 'w-1.5 h-1.5',
    sm: 'w-2 h-2',
    md: 'w-2.5 h-2.5',
  };
  return (
    <span className="relative inline-flex">
      {pulse && (
        <span
          className={`absolute inset-0 ${colors[tone]} ${sizes[size]} rounded-full opacity-40 animate-ping`}
        />
      )}
      <span
        className={`${colors[tone]} ${sizes[size]} rounded-full ${
          pulse ? 'animate-pulse-dot' : ''
        }`}
      />
    </span>
  );
}
