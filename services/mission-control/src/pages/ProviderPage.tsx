import { Link, useParams } from "react-router-dom";

function formatProviderName(providerId: string): string {
    return providerId
        .split("-")
        .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
        .join(" ");
}

export function ProviderPage() {
    const { providerId } = useParams<{
        providerId: string;
    }>();

    const providerName = providerId
        ? formatProviderName(providerId)
        : "Unknown Provider";

    return (
        <main className="mx-auto max-w-7xl p-8">
            <Link
                to="/"
                className="text-sm font-medium text-blue-400 transition hover:text-blue-300"
            >
                ← Mission Control
            </Link>

            <section className="mt-6 rounded-lg border border-slate-800 bg-slate-900 p-8">
                <p className="text-xs font-semibold uppercase tracking-[0.15em] text-slate-500">
                    Provider
                </p>

                <h1 className="mt-3 text-3xl font-bold tracking-tight text-slate-100">
                    {providerName}
                </h1>

                <p className="mt-3 max-w-2xl text-sm leading-6 text-slate-400">
                    Provider details, metrics, findings, recommendations, and
                    controls will appear here.
                </p>
            </section>
        </main>
    );
}
