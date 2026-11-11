import Link from 'next/link';

const items = [
  { href: '/', label: 'Overview' },
  { href: '/jobs', label: 'Jobs' },
];

export default function Nav() {
  return (
    <nav className="bg-slate-900 text-white">
      <div className="max-w-6xl mx-auto px-4 py-3 flex items-center gap-6">
        <Link href="/" className="font-bold text-lg">TaskForge</Link>
        <div className="flex gap-4 text-sm">
          {items.map((i) => (
            <Link key={i.href} href={i.href} className="hover:text-slate-300">
              {i.label}
            </Link>
          ))}
        </div>
      </div>
    </nav>
  );
}
