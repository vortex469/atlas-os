import { useEffect, useRef, useState, type FormEvent } from "react";
import { Link, Navigate, useLocation, useNavigate } from "react-router-dom";

import { useOperatorSession } from "../hooks/operatorSessionContext";
import { proposalIdFromState } from "../features/discovery/proposalNavigation";

export function OperatorLoginPage() {
    const session = useOperatorSession();
    const location = useLocation();
    const navigate = useNavigate();
    const [operatorId, setOperatorId] = useState("");
    const [password, setPassword] = useState("");
    const [submitting, setSubmitting] = useState(false);
    const [loginError, setLoginError] = useState<string | null>(null);
    const viewActive = useRef(true);
    const proposalId = proposalIdFromState(location.state);
    const returnState = proposalId ? { proposalId } : undefined;

    useEffect(() => {
        viewActive.current = true;
        return () => { viewActive.current = false; };
    }, []);

    async function submit(event: FormEvent<HTMLFormElement>) {
        event.preventDefault();
        if (submitting || session.loading) return;
        setSubmitting(true);
        setLoginError(null);
        try {
            const succeeded = await session.login(operatorId, password);
            if (succeeded && viewActive.current) navigate("/operations/request", { replace: true, state: returnState });
        } catch {
            if (viewActive.current) setLoginError("Sign-in could not be completed.");
        } finally {
            setPassword("");
            if (viewActive.current) setSubmitting(false);
        }
    }

    if (!session.loading && session.authenticated) {
        return <Navigate to="/operations/request" state={returnState} replace />;
    }

    return (
        <main className="mx-auto max-w-xl space-y-6 p-8">
            <header>
                <p className="text-xs uppercase tracking-[0.3em] text-blue-300">Operator session</p>
                <h1 className="mt-2 text-3xl font-bold text-white">Operator login</h1>
                <p className="mt-3 text-sm text-slate-400">Sign in to choose a resource and request maintenance. Signing in does not approve or run a change.</p>
                {proposalId && <p className="mt-2 text-sm text-slate-400">After sign-in, maintenance will reload the proposal you were reviewing. You will still choose the resource yourself.</p>}
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
                {(loginError || session.error) && <p role="alert" className="text-sm text-red-300">{loginError ?? session.error}</p>}
                <button disabled={submitting || session.loading} className="rounded-lg bg-blue-500 px-4 py-2 text-sm font-semibold text-white disabled:bg-slate-700">
                    {submitting ? "Signing in…" : "Sign in"}
                </button>
            </form>
            <Link to="/" className="inline-flex text-sm text-blue-300">← Mission Control</Link>
        </main>
    );
}
