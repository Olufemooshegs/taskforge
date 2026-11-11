export default function Card({
  title,
  meta,
  action,
  children,
  className = '',
  bodyClassName = '',
}: {
  title?: string;
  meta?: string;
  action?: React.ReactNode;
  children: React.ReactNode;
  className?: string;
  bodyClassName?: string;
}) {
  return (
    <section
      className={`border border-border rounded-lg bg-surface/50 backdrop-blur-sm ${className}`}
    >
      {(title || action) && (
        <div className="flex items-center gap-3 px-4 h-9 border-b border-border">
          {title && (
            <span className="text-[11px] font-mono uppercase tracking-wider text-muted">
              {title}
            </span>
          )}
          {meta && <span className="text-[11px] font-mono text-dim">{meta}</span>}
          {action && <div className="ml-auto">{action}</div>}
        </div>
      )}
      <div className={bodyClassName}>{children}</div>
    </section>
  );
}
