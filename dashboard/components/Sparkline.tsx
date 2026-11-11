'use client';

export default function Sparkline({
  data,
  height = 64,
  className = '',
}: {
  data: number[];
  height?: number;
  className?: string;
}) {
  if (!data || data.length === 0) {
    return (
      <div
        className={`w-full bg-surface-hi/30 rounded ${className}`}
        style={{ height }}
      />
    );
  }

  const w = 1000;
  const h = height;
  const pad = 4;
  const max = Math.max(...data, 1);
  const step = w / Math.max(data.length - 1, 1);

  const points = data.map((v, i) => {
    const x = i * step;
    const y = h - pad - (v / max) * (h - pad * 2);
    return [x, y] as const;
  });

  const lineD = points
    .map(([x, y], i) => `${i === 0 ? 'M' : 'L'}${x.toFixed(1)},${y.toFixed(1)}`)
    .join(' ');
  const areaD = `${lineD} L${w},${h} L0,${h} Z`;

  return (
    <svg
      viewBox={`0 0 ${w} ${h}`}
      preserveAspectRatio="none"
      className={className}
      style={{ height }}
    >
      <defs>
        <linearGradient id="sparkGrad" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor="#7ae64c" stopOpacity="0.35" />
          <stop offset="100%" stopColor="#7ae64c" stopOpacity="0" />
        </linearGradient>
      </defs>
      <path d={areaD} fill="url(#sparkGrad)" />
      <path
        d={lineD}
        fill="none"
        stroke="#7ae64c"
        strokeWidth="1.5"
        strokeLinejoin="round"
        strokeLinecap="round"
        vectorEffect="non-scaling-stroke"
      />
    </svg>
  );
}
