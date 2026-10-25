import { Link } from "react-router-dom";

export function PageErrorPage() {
    return (
        <main className="mx-auto max-w-3xl p-6 sm:p-8">
            <section role="alert" className="rounded-xl border border-red-500/30 bg-red-500/10 p-6">
                <h1 className="text-2xl font-semibold text-slate-100">This page could not load</h1>
                <p className="mt-3 text-sm leading-6 text-slate-300">
                    Reload to try again, or choose another screen from the navigation.
                </p>
                <div className="mt-5 flex flex-wrap gap-3">
                    <button type="button" onClick={() => window.location.reload()} className="mc-control mc-focusable px-4 py-2 text-sm font-semibold">
                        Reload page
                    </button>
                    <Link to="/" className="mc-control mc-focusable px-4 py-2 text-sm font-semibold">
                        Return to Mission Control
                    </Link>
                </div>
            </section>
        </main>
    );
}
