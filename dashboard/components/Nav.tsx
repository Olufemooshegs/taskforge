'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { useState, useEffect } from 'react';
import { api } from '@/lib/api';
import { usePolling } from '@/lib/usePolling';
import LiveDot from './LiveDot';

export default function Nav() {
  const pathname = usePathname();
  const [clock, setClock] = useState('--:--:--');
  const { data: stats } = usePolling(() => api.overview(), 4000);

  useEffect(() => {
    const tick = () => {
      const now = new Date();
      setClock(
        now.toLocaleTimeString('en-GB', {
          hour12: false,
          hour: '2-digit',
          minute: '2-digit',
          second: '2-digit',
        }),
      );
    };
    tick();
    const id = setInterval(tick, 1000);
    return () => clearInterval(id);
  }, []);

  const liveWorkers = stats?.workers.live ?? 0;

  const links = [
    { href: '/', label: 'overview' },
    { href: '/jobs', label: 'jobs' },
  ];

  return (
    <header className="border-b border-border bg-bg/90 backdrop-blur-md sticky top-0 z-40">
      <div className="max-w-[1440px] mx-auto px-6 h-14 flex items-center gap-6">
        <Link href="/" className="flex items-center gap-2 group">
          <span className="w-2 h-2 bg-accent rounded-sm group-hover:scale-125 transition-transform" />
          <span className="font-mono font-semibold text-text tracking-tight">taskforge</span>
        </Link>

        <nav className="flex items-center gap-1 ml-2">
          {links.map((l) => {
            const active =
              l.href === '/' ? pathname === '/' : pathname.startsWith(l.href);
            return (
              <Link
                key={l.href}
                href={l.href}
                className={`px-3 py-1.5 rounded text-sm font-mono transition-colors ${
                  active
                    ? 'bg-surface-hi text-text'
                    : 'text-muted hover:text-text hover:bg-surface'
                }`}
              >
                {l.label}
              </Link>
            );
          })}
        </nav>

        <div className="ml-auto flex items-center gap-5 text-xs font-mono">
          <div className="flex items-center gap-1.5 text-muted">
            <LiveDot tone={liveWorkers > 0 ? 'good' : 'bad'} pulse={liveWorkers > 0} />
            <span>{liveWorkers} worker{liveWorkers === 1 ? '' : 's'}</span>
          </div>
          <span className="text-dim">{clock}</span>
        </div>
      </div>
    </header>
  );
}
