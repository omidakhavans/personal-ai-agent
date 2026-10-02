import Link from 'next/link';
import { ArrowRight, BookOpen, ShieldCheck } from 'lucide-react';

export default function HomePage() {
  return (
    <main className="mx-auto grid min-h-screen max-w-5xl content-center gap-10 px-6 py-16 sm:px-10">
      <div className="max-w-3xl">
        <p className="mb-5 font-mono text-sm font-medium text-emerald-700">PHASE 2 LEARNING DOCUMENTATION</p>
        <h1 className="text-4xl font-semibold tracking-normal text-stone-950 sm:text-6xl">Personal AI Agent</h1>
        <p className="mt-6 max-w-2xl text-lg leading-8 text-stone-700">
          A small Python runtime for learning how grounded AI workflows preserve evidence, state, safety boundaries, and human review.
        </p>
      </div>
      <div className="grid gap-4 sm:grid-cols-2">
        <Link href="/docs" className="group border border-stone-300 bg-white p-6 transition-colors hover:border-emerald-700">
          <BookOpen className="mb-5 size-5 text-emerald-700" aria-hidden="true" />
          <h2 className="text-lg font-semibold text-stone-950">Read the learning path</h2>
          <p className="mt-2 text-sm leading-6 text-stone-600">Start with the runtime, then trace its grounded research stages.</p>
          <span className="mt-5 inline-flex items-center gap-2 text-sm font-medium text-emerald-800">Open documentation <ArrowRight className="size-4" aria-hidden="true" /></span>
        </Link>
        <section className="border border-stone-300 bg-stone-950 p-6 text-stone-50">
          <ShieldCheck className="mb-5 size-5 text-emerald-300" aria-hidden="true" />
          <h2 className="text-lg font-semibold">Grounded by design</h2>
          <p className="mt-2 text-sm leading-6 text-stone-300">Source selection, evidence references, durable run state, and draft-first outputs stay explicit.</p>
        </section>
      </div>
    </main>
  );
}
