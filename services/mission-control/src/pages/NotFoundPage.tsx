import { Link } from "react-router-dom";

export function NotFoundPage() {
    return (
        <main className="flex min-h-[50vh] items-center justify-center p-4 sm:p-8">
            <section className="max-w-lg text-center">
                <p className="text-sm font-semibold uppercase tracking-[0.2em] text-blue-400">
                    404
                </p>

                <h1 className="mt-4 text-3xl font-bold text-slate-100">
                    Page not found
                </h1>

                <p className="mt-3 text-sm leading-6 text-slate-400">
                    This page is not available. Use the navigation to choose a
                    screen, or return to Mission Control.
                </p>

                <Link
                    to="/"
                    className="mt-6 inline-flex rounded-lg border border-slate-700 bg-slate-900 px-4 py-2 text-sm font-medium text-slate-200 transition hover:border-slate-600 hover:text-white"
                >
                    Return to Mission Control
                </Link>
            </section>
        </main>
    );
}
