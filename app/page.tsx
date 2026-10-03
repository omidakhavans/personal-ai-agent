import Link from 'next/link';
import { ArrowRight, BookOpen, Braces, Code2, ShieldCheck, Waypoints } from 'lucide-react';
import { ThemeSwitch } from 'fumadocs-ui/layouts/shared/slots/theme-switch';

const learningPaths = [
  {
    title: 'Start the runtime',
    description: 'Run a local research workflow, inspect the saved state, and understand the artifact boundary.',
    href: '/docs/getting-started',
    icon: BookOpen,
  },
  {
    title: 'Trace one execution',
    description: 'Follow a command from CLI input through orchestration, stages, persistence, and resume behavior.',
    href: '/docs/learning/runtime-walkthrough',
    icon: Waypoints,
  },
  {
    title: 'Study the safeguards',
    description: 'See how private inputs, public artifacts, resource fetching, and retries are deliberately bounded.',
    href: '/docs/learning/runtime-hardening',
    icon: ShieldCheck,
  },
];

export default function HomePage() {
  return (
    <main className="min-h-screen bg-fd-background text-fd-foreground">
      <header className="border-b border-fd-border">
        <nav className="mx-auto flex h-16 max-w-6xl items-center justify-between px-5 sm:px-8" aria-label="Primary navigation">
          <Link href="/" className="font-semibold tracking-normal">Personal AI Agent</Link>
          <div className="flex items-center gap-1.5 sm:gap-3">
            <Link
              href="/docs"
              className="inline-flex items-center gap-2 rounded-md px-3 py-2 text-sm font-medium text-fd-muted-foreground transition-colors hover:bg-fd-accent hover:text-fd-accent-foreground"
            >
              Documentation
              <ArrowRight className="size-4" aria-hidden="true" />
            </Link>
            <a
              href="https://github.com/omidakhavans/personal-ai-agent"
              className="inline-flex size-9 items-center justify-center rounded-md text-fd-muted-foreground transition-colors hover:bg-fd-accent hover:text-fd-accent-foreground"
              aria-label="Open the GitHub repository"
              title="GitHub repository"
            >
              <Code2 className="size-4" aria-hidden="true" />
            </a>
            <ThemeSwitch className="max-sm:hidden" />
          </div>
        </nav>
      </header>

      <section className="mx-auto max-w-6xl px-5 pb-14 pt-16 sm:px-8 sm:pb-20 sm:pt-24">
        <div className="max-w-3xl">
          <p className="mb-5 font-mono text-sm font-medium text-fd-primary">PHASE 2 / LEARNING RUNTIME</p>
          <h1 className="max-w-2xl text-4xl font-semibold leading-tight tracking-normal sm:text-6xl">Personal AI Agent</h1>
          <p className="mt-6 max-w-2xl text-lg leading-8 text-fd-muted-foreground">
            A small Python runtime for learning how grounded AI workflows preserve evidence, state, safety boundaries, and human review.
          </p>
          <div className="mt-8 flex flex-wrap gap-3">
            <Link
              href="/docs"
              className="inline-flex items-center gap-2 rounded-md bg-fd-primary px-4 py-2.5 text-sm font-medium text-fd-primary-foreground transition-opacity hover:opacity-85"
            >
              Open the learning path
              <ArrowRight className="size-4" aria-hidden="true" />
            </Link>
            <Link
              href="/docs/architecture"
              className="inline-flex items-center gap-2 rounded-md border border-fd-border px-4 py-2.5 text-sm font-medium transition-colors hover:bg-fd-accent"
            >
              View architecture
              <Braces className="size-4" aria-hidden="true" />
            </Link>
          </div>
        </div>

        <div className="mt-14 border-y border-fd-border py-6 sm:mt-20">
          <p className="font-mono text-xs font-medium uppercase text-fd-muted-foreground">Current runtime shape</p>
          <ol className="mt-4 grid gap-3 text-sm font-medium sm:grid-cols-5 sm:gap-0">
            {['CLI input', 'Run state', 'Work research', 'Resource research', 'Evidence context'].map((step, index) => (
              <li key={step} className="flex items-center gap-3 sm:gap-0">
                <span className="flex size-7 shrink-0 items-center justify-center rounded-full border border-fd-border font-mono text-xs text-fd-muted-foreground">{index + 1}</span>
                <span className="sm:ms-3">{step}</span>
              </li>
            ))}
          </ol>
        </div>
      </section>

      <section className="border-t border-fd-border bg-fd-card">
        <div className="mx-auto max-w-6xl px-5 py-14 sm:px-8 sm:py-16">
          <div className="max-w-2xl">
            <p className="font-mono text-xs font-medium uppercase text-fd-muted-foreground">Read with the code open</p>
            <h2 className="mt-3 text-2xl font-semibold tracking-normal">Choose a useful place to begin.</h2>
          </div>
          <div className="mt-8 grid gap-px overflow-hidden rounded-lg border border-fd-border bg-fd-border lg:grid-cols-3">
            {learningPaths.map(({ title, description, href, icon: Icon }) => (
              <Link key={href} href={href} className="group bg-fd-background p-6 transition-colors hover:bg-fd-accent">
                <Icon className="size-5 text-fd-primary" aria-hidden="true" />
                <h3 className="mt-6 text-base font-semibold">{title}</h3>
                <p className="mt-2 text-sm leading-6 text-fd-muted-foreground">{description}</p>
                <span className="mt-6 inline-flex items-center gap-2 text-sm font-medium text-fd-primary">
                  Read guide
                  <ArrowRight className="size-4 transition-transform group-hover:translate-x-1" aria-hidden="true" />
                </span>
              </Link>
            ))}
          </div>
        </div>
      </section>
    </main>
  );
}
