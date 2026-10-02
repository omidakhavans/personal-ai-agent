import { DocsLayout } from 'fumadocs-ui/layouts/docs';
import { layoutOptions } from '@/lib/layout';
import { source } from '@/lib/source';

export default function DocsRootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return <DocsLayout tree={source.getPageTree()} {...layoutOptions}>{children}</DocsLayout>;
}
