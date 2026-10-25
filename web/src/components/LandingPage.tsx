"use client";

const features = [
  { number: "01", title: "Understand the structure", text: "Excel Copilot identifies tables, dates, measures, categories, formulas, and potential data-quality issues before showing you a chart." },
  { number: "02", title: "See what matters", text: "Get a focused set of KPIs, trends, comparisons, and grounded insights instead of an overwhelming dashboard of decoration." },
  { number: "03", title: "Ask better questions", text: "Explore your workbook in plain language. Every answer is calculated from your data and checked before it is shown." },
];

const useCases = ["Sales performance", "Financial reporting", "Inventory health", "Operations review", "Marketing results", "Management briefings"];

export default function LandingPage({ onGetStarted }: { onGetStarted: () => void }) {
  return (
    <main className="min-h-screen overflow-hidden bg-[#f8f9fc] text-zinc-950">
      <section className="relative">
        <div className="pointer-events-none absolute -right-48 -top-40 h-[34rem] w-[34rem] rounded-full bg-indigo-200/50 blur-3xl" aria-hidden />
        <div className="pointer-events-none absolute left-[-18rem] top-[28rem] h-[28rem] w-[28rem] rounded-full bg-violet-100/70 blur-3xl" aria-hidden />
        <nav className="relative mx-auto flex max-w-7xl items-center justify-between px-6 py-6 sm:px-8 lg:px-10">
          <a href="#" className="flex items-center gap-2.5" aria-label="Excel Copilot home">
            <span className="flex h-9 w-9 items-center justify-center rounded-xl bg-zinc-950 text-sm font-bold text-white shadow-lg shadow-zinc-950/15">E</span>
            <span className="text-base font-semibold tracking-tight">Excel Copilot</span>
          </a>
          <div className="hidden items-center gap-8 text-sm text-zinc-600 md:flex">
            <a href="#how-it-works" className="transition-colors hover:text-zinc-950">How it works</a>
            <a href="#capabilities" className="transition-colors hover:text-zinc-950">Capabilities</a>
            <a href="#privacy" className="transition-colors hover:text-zinc-950">Privacy</a>
          </div>
          <button type="button" onClick={onGetStarted} className="rounded-lg border border-zinc-200 bg-white px-4 py-2 text-sm font-semibold text-zinc-800 shadow-sm transition hover:border-zinc-300 hover:bg-zinc-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent">
            Sign in
          </button>
        </nav>

        <div className="relative mx-auto grid max-w-7xl items-center gap-14 px-6 pb-20 pt-14 sm:px-8 sm:pb-28 lg:grid-cols-[1.05fr_0.95fr] lg:px-10 lg:pt-20">
          <div>
            <div className="inline-flex items-center gap-2 rounded-full border border-indigo-200 bg-white/80 px-3 py-1.5 text-xs font-medium text-indigo-700 shadow-sm">
              <span className="h-1.5 w-1.5 rounded-full bg-indigo-500" aria-hidden />
              Your spreadsheet, explained
            </div>
            <h1 className="mt-6 max-w-3xl text-5xl font-semibold leading-[1.02] tracking-[-0.045em] text-zinc-950 sm:text-6xl lg:text-[4.5rem]">
              Turn Excel into <span className="text-indigo-600">clear decisions.</span>
            </h1>
            <p className="mt-6 max-w-xl text-lg leading-8 text-zinc-600">
              Upload a workbook and get the numbers, patterns, and next questions that matter. No formulas to write. No dashboard maze to navigate.
            </p>
            <div className="mt-8 flex flex-wrap items-center gap-3">
              <button type="button" onClick={onGetStarted} className="rounded-xl bg-zinc-950 px-5 py-3 text-sm font-semibold text-white shadow-xl shadow-zinc-950/15 transition hover:-translate-y-0.5 hover:bg-indigo-700 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent focus-visible:ring-offset-2">
                Analyze your workbook <span className="ml-2" aria-hidden>→</span>
              </button>
              <a href="#how-it-works" className="rounded-xl px-4 py-3 text-sm font-semibold text-zinc-600 transition hover:bg-white hover:text-zinc-950">See how it works</a>
            </div>
            <div className="mt-8 flex flex-wrap gap-x-6 gap-y-2 text-xs text-zinc-500">
              <span>✓ Built for .xlsx</span><span>✓ Grounded in your data</span><span>✓ Private by design</span>
            </div>
          </div>

          <div className="relative mx-auto w-full max-w-[30rem] lg:ml-auto">
            <div className="absolute -inset-5 rounded-[2rem] bg-indigo-200/30 blur-2xl" aria-hidden />
            <div className="relative rounded-[1.5rem] border border-zinc-200 bg-white p-3 shadow-2xl shadow-indigo-950/10">
              <div className="rounded-xl bg-[#f7f8fc] p-4 sm:p-5">
                <div className="flex items-center justify-between border-b border-zinc-200 pb-4">
                  <div><p className="text-[9px] font-semibold uppercase tracking-[0.18em] text-indigo-600">Workbook intelligence</p><p className="mt-1 text-sm font-semibold">Q3 sales performance.xlsx</p></div>
                  <span className="rounded-full bg-emerald-50 px-2 py-1 text-[9px] font-medium text-emerald-700">Ready</span>
                </div>
                <div className="mt-4 grid grid-cols-2 gap-2 sm:grid-cols-4">
                  {["$7.2M", "+71%", "339", "53%"].map((v, i) => <div key={v} className="rounded-lg border border-zinc-200 bg-white p-2.5"><p className="text-lg font-semibold tracking-tight">{v}</p><p className="mt-1 text-[8px] text-zinc-500">{["Total revenue", "vs last month", "Transactions", "Of target"][i]}</p></div>)}
                </div>
                <div className="mt-3 rounded-lg border border-zinc-200 bg-white p-3">
                  <div className="flex items-center justify-between"><p className="text-[10px] font-semibold">Revenue trend</p><span className="text-[8px] text-zinc-400">Jan — Sep</span></div>
                  <svg className="mt-4 h-28 w-full" viewBox="0 0 360 110" role="img" aria-label="Illustration of an upward and downward revenue trend">
                    <path d="M8 91H352M8 59H352M8 27H352" stroke="#e4e4e7" strokeWidth="1" />
                    <path d="M8 78 C35 70, 44 78, 65 62 S99 35, 123 50 S153 88, 179 69 S211 38, 236 54 S264 84, 286 74 S315 44, 352 22" fill="none" stroke="#5e6ad2" strokeWidth="3" strokeLinecap="round" />
                    <circle cx="352" cy="22" r="4" fill="#5e6ad2" />
                  </svg>
                  <div className="flex justify-between text-[8px] text-zinc-400"><span>Jan</span><span>Apr</span><span>Jul</span><span>Sep</span></div>
                </div>
                <div className="mt-3 flex items-start gap-2 rounded-lg border border-indigo-100 bg-indigo-50/70 p-3"><span className="mt-0.5 text-indigo-600">✦</span><div><p className="text-[10px] font-semibold text-indigo-950">What stands out</p><p className="mt-1 text-[9px] leading-4 text-indigo-900/70">Revenue increased in September, led by Electronics.</p></div></div>
              </div>
            </div>
          </div>
        </div>
      </section>

      <section className="border-y border-zinc-200 bg-white">
        <div className="mx-auto flex max-w-7xl flex-wrap items-center justify-between gap-5 px-6 py-5 sm:px-8 lg:px-10">
          <p className="text-xs font-medium text-zinc-400">For teams who need clarity from their spreadsheets</p>
          <div className="flex flex-wrap gap-x-6 gap-y-2 text-xs font-medium text-zinc-500"><span>Small business</span><span>Finance</span><span>Sales</span><span>Operations</span><span>Management</span></div>
        </div>
      </section>

      <section id="how-it-works" className="mx-auto max-w-7xl px-6 py-24 sm:px-8 lg:px-10">
        <div className="max-w-2xl"><p className="text-xs font-semibold uppercase tracking-[0.2em] text-indigo-600">From file to focus</p><h2 className="mt-3 text-3xl font-semibold tracking-tight sm:text-4xl">A smarter first look at your data.</h2><p className="mt-4 text-base leading-7 text-zinc-600">Excel Copilot does the first round of analysis for you, so you can spend time understanding the result instead of preparing the spreadsheet.</p></div>
        <div className="mt-12 grid gap-5 md:grid-cols-3">{features.map((feature) => <article key={feature.number} className="rounded-2xl border border-zinc-200 bg-white p-6 shadow-sm"><span className="text-xs font-semibold text-indigo-600">{feature.number}</span><h3 className="mt-12 text-lg font-semibold tracking-tight">{feature.title}</h3><p className="mt-3 text-sm leading-6 text-zinc-600">{feature.text}</p></article>)}</div>
      </section>

      <section id="capabilities" className="bg-zinc-950 text-white">
        <div className="mx-auto grid max-w-7xl gap-14 px-6 py-24 sm:px-8 lg:grid-cols-[0.8fr_1.2fr] lg:px-10">
          <div><p className="text-xs font-semibold uppercase tracking-[0.2em] text-indigo-300">One workspace</p><h2 className="mt-3 text-3xl font-semibold tracking-tight sm:text-4xl">Everything you need to make the spreadsheet useful.</h2><p className="mt-5 text-sm leading-7 text-zinc-400">A focused experience for the questions behind the numbers—not another generic chart generator.</p><button type="button" onClick={onGetStarted} className="mt-8 rounded-xl bg-white px-4 py-2.5 text-sm font-semibold text-zinc-950 hover:bg-indigo-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-white">Try it with your workbook →</button></div>
          <div className="grid gap-3 sm:grid-cols-2">{["Automatic KPIs and trends", "Grounded insights", "Data-quality signals", "Plain-language questions", "Guided investigation", "Client-ready PDF reports"].map((item) => <div key={item} className="flex items-center gap-3 rounded-xl border border-white/10 bg-white/5 px-4 py-4 text-sm text-zinc-200"><span className="flex h-7 w-7 items-center justify-center rounded-lg bg-indigo-500/20 text-indigo-300">✓</span>{item}</div>)}</div>
        </div>
      </section>

      <section id="privacy" className="mx-auto max-w-7xl px-6 py-24 sm:px-8 lg:px-10">
        <div className="rounded-3xl border border-indigo-100 bg-gradient-to-br from-indigo-50 to-white p-8 sm:p-12"><div className="max-w-2xl"><p className="text-xs font-semibold uppercase tracking-[0.2em] text-indigo-600">Trust the process</p><h2 className="mt-3 text-3xl font-semibold tracking-tight">Your workbook stays yours.</h2><p className="mt-4 text-base leading-7 text-zinc-600">Files are private to your account. The analysis is built from deterministic calculations, and AI assistance is optional. You stay in control of what you upload, inspect, export, and delete.</p></div><div className="mt-8 grid gap-3 text-sm sm:grid-cols-3"><div className="rounded-xl bg-white p-4 shadow-sm"><p className="font-semibold">Private storage</p><p className="mt-1 text-xs leading-5 text-zinc-500">Your files are protected by account-level access controls.</p></div><div className="rounded-xl bg-white p-4 shadow-sm"><p className="font-semibold">Traceable numbers</p><p className="mt-1 text-xs leading-5 text-zinc-500">Figures are recomputed and linked back to their source rows.</p></div><div className="rounded-xl bg-white p-4 shadow-sm"><p className="font-semibold">You decide</p><p className="mt-1 text-xs leading-5 text-zinc-500">Review, filter, ask, export, or delete whenever you want.</p></div></div></div>
      </section>

      <section className="border-t border-zinc-200 bg-white">
        <div className="mx-auto max-w-7xl px-6 py-20 text-center sm:px-8 lg:px-10"><p className="text-xs font-semibold uppercase tracking-[0.2em] text-indigo-600">Ready when you are</p><h2 className="mt-3 text-3xl font-semibold tracking-tight sm:text-4xl">Bring the spreadsheet. Leave with clarity.</h2><p className="mx-auto mt-4 max-w-lg text-sm leading-6 text-zinc-600">Start with one workbook and see what your data has been trying to tell you.</p><button type="button" onClick={onGetStarted} className="mt-7 rounded-xl bg-zinc-950 px-6 py-3 text-sm font-semibold text-white shadow-xl shadow-zinc-950/15 hover:bg-indigo-700 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent focus-visible:ring-offset-2">Get started for free <span className="ml-2" aria-hidden>→</span></button></div>
      </section>

      <footer className="mx-auto flex max-w-7xl flex-wrap items-center justify-between gap-3 px-6 py-7 text-xs text-zinc-500 sm:px-8 lg:px-10"><span className="font-semibold text-zinc-800">Excel Copilot</span><span>Upload your Excel. Understand your data.</span><span>© 2026 Excel Copilot</span></footer>
    </main>
  );
}
