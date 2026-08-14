import { useState, type FormEvent } from "react";
import { Navigate, useLocation, useNavigate } from "react-router-dom";

import { useOperatorSession } from "../hooks/operatorSessionContext";

type LoginLocationState = { returnTo?: string };

export function OperatorLoginPage() {
    const session = useOperatorSession();
    const location = useLocation();
    const navigate = useNavigate();
    const [operatorId, setOperatorId] = useState("");
    const [password, setPassword] = useState("");
    const [submitting, setSubmitting] = useState(false);
    const returnTo = (location.state as LoginLocationState | null)?.returnTo ?? "/operations/request";

    async function submit(event: FormEvent<HTMLFormElement>) {
        event.preventDefault();
        if (submitting) return;
        setSubmitting(true);
        const succeeded = await session.login(operatorId, password);
        setPassword("");
        setSubmitting(false);
        if (succeeded) navigate(returnTo, { replace: true });
    }

    if (!session.loading && session.authenticated) {
        return <Navigate to={returnTo} replace />;
    }

    return (
        <main className="mx-auto max-w-xl space-y-6 p-8">
            <header>
                <p className="text-xs uppercase tracking-[0.3em] text-blue-300">Operator session</p>
                <h1 className="mt-2 text-3xl font-bold text-white">Operator login</h1>
                <p className="mt-3 text-sm text-slate-400">Authenticate with Atlas Core to request bounded maintenance.</p>
            </header>
            <form onSubmit={submit} className="space-y-5 rounded-xl border border-slate-800 bg-slate-900/70 p-6">
                <label className="block text-sm text-slate-300">
                    Operator ID
                    <input value={operatorId} onChange={(event) => setOperatorId(event.target.value)} required autoComplete="username" className="mt-2 w-full rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-white" />
                </label>
                <label className="block text-sm text-slate-300">
                    Password
                    <input type="password" value={password} onChange={(event) => setPassword(event.target.value)} required autoComplete="current-password" className="mt-2 w-full rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-white" />
                </label>
                {session.error && <p role="alert" className="text-sm text-red-300">{session.error}</p>}
                <button disabled={submitting || session.loading} className="rounded-lg bg-blue-500 px-4 py-2 text-sm font-semibold text-white disabled:bg-slate-700">
                    {submitting ? "Signing in…" : "Sign in"}
                </button>
            </form>
        </main>
    );
}
