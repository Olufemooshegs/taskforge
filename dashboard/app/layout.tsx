import type { Metadata } from 'next';
import { GeistSans } from 'geist/font/sans';
import { GeistMono } from 'geist/font/mono';
import Nav from '@/components/Nav';
import './globals.css';

export const metadata: Metadata = {
  title: 'TaskForge',
  description: 'Distributed background-job engine dashboard',
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={`${GeistSans.variable} ${GeistMono.variable}`}>
      <body className="font-sans min-h-screen bg-bg text-text relative">
        <Nav />
        <main className="max-w-[1440px] mx-auto px-6 py-8 relative z-10">{children}</main>
      </body>
    </html>
  );
}
