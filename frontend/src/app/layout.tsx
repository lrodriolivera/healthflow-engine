import type { Metadata } from 'next';
import './globals.css';
import Sidebar from '@/components/Sidebar';

export const metadata: Metadata = {
  title: 'HealthFlow Engine',
  description: 'AI-native healthcare integration engine',
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className="bg-slate-50 min-h-screen">
        <Sidebar />
        <main className="ml-[260px] min-h-screen">
          <div className="px-8 py-6">{children}</div>
        </main>
      </body>
    </html>
  );
}
