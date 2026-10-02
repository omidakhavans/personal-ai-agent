import type { Metadata } from 'next';
import { Provider } from '@/components/provider';
import './global.css';

export const metadata: Metadata = {
  title: {
    default: 'Personal AI Agent',
    template: '%s | Personal AI Agent',
  },
  description: 'Learning documentation for a small, grounded personal AI agent runtime.',
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body><Provider>{children}</Provider></body>
    </html>
  );
}
