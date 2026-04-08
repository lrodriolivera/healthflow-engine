import type { Metadata } from 'next';
import './globals.css';

export const metadata: Metadata = {
  title: 'HealthFlow Engine',
  description: 'AI-native healthcare integration engine',
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className="bg-gray-50 min-h-screen">
        <nav className="bg-healthflow-900 text-white px-6 py-3 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <h1 className="text-lg font-bold">HealthFlow Engine</h1>
            <span className="text-xs bg-healthflow-700 px-2 py-0.5 rounded">v0.1.0</span>
          </div>
          <div className="flex gap-4 text-sm">
            <a href="/" className="hover:text-healthflow-50">Dashboard</a>
            <a href="/flows" className="hover:text-healthflow-50">Flows</a>
            <a href="/messages" className="hover:text-healthflow-50">Messages</a>
            <a href="/agents" className="hover:text-healthflow-50">AI Agents</a>
          </div>
        </nav>
        <main className="max-w-7xl mx-auto px-6 py-6">{children}</main>
      </body>
    </html>
  );
}
