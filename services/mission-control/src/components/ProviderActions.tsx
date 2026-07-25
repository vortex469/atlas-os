import {
    useCallback,
    useEffect,
    useState,
} from "react";

import {
    getAtlasErrorMessage,
    getProviderActions,
    runProviderAction,
} from "../api/atlas";
import type { Provider } from "../types/provider";
import type {
    ProviderAction,
    ProviderActionResult,
} from "../types/providerAction";
import { SectionHeader } from "./SectionHeader";

type ProviderActionsProps = {
    provider: Provider;
    onActionCompleted: () => Promise<void>;
};

export function ProviderActions({
    provider,
    onActionCompleted,
}: ProviderActionsProps) {
    const [actions, setActions] = useState<ProviderAction[]>(
        [],
    );
    const [isLoading, setIsLoading] = useState(true);
    const [runningActionId, setRunningActionId] = useState<
        string | null
    >(null);
    const [error, setError] = useState<string | null>(null);
    const [result, setResult] =
        useState<ProviderActionResult | null>(null);

    const loadActions = useCallback(async () => {
        setIsLoading(true);
        setError(null);

        try {
            const providerActions = await getProviderActions(
                provider.id,
            );
            setActions(providerActions);
        } catch (requestError) {
            console.error(
                `Unable to load actions for ${provider.id}:`,
                requestError,
            );
            setError(
                getAtlasErrorMessage(
                    requestError,
                    `Mission Control could not load actions for ${provider.name}.`,
                ),
            );
        } finally {
            setIsLoading(false);
        }
    }, [provider.id, provider.name]);

    useEffect(() => {
        let cancelled = false;

        getProviderActions(provider.id)
            .then((providerActions) => {
                if (cancelled) {
                    return;
                }

                setActions(providerActions);
                setError(null);
            })
            .catch((requestError: unknown) => {
                if (cancelled) {
                    return;
                }

                console.error(
                    `Unable to load actions for ${provider.id}:`,
                    requestError,
                );
                setError(
                    getAtlasErrorMessage(
                        requestError,
                        `Mission Control could not load actions for ${provider.name}.`,
                    ),
                );
            })
            .finally(() => {
                if (!cancelled) {
                    setIsLoading(false);
                }
            });

        return () => {
            cancelled = true;
        };
    }, [provider.id, provider.name]);

    async function executeAction(
        action: ProviderAction,
    ): Promise<void> {
        if (!action.enabled || runningActionId !== null) {
            return;
        }

        let confirmed = false;

        if (action.requires_confirmation) {
            const confirmationMessage = action.destructive
                ? `${action.label} is marked as destructive. Continue?`
                : `${action.label} requires confirmation. Continue?`;

            confirmed = window.confirm(confirmationMessage);

            if (!confirmed) {
                return;
            }
        }

        setRunningActionId(action.id);
        setError(null);
        setResult(null);

        try {
            const actionResult = await runProviderAction(
                provider.id,
                action.id,
                {
                    confirmed,
                    parameters: {},
                },
            );

            setResult(actionResult);

            if (actionResult.success) {
                await onActionCompleted();
            }
        } catch (requestError) {
            console.error(
                `Unable to run ${action.id} for ${provider.id}:`,
                requestError,
            );
            setError(
                getAtlasErrorMessage(
                    requestError,
                    `Atlas Core could not run ${action.label}.`,
                ),
            );
        } finally {
            setRunningActionId(null);
        }
    }

    return (
        <section>
            <SectionHeader
                title="Provider Actions"
                description="Safe operations advertised by this provider."
            />

            {isLoading && (
                <div className="rounded-lg border border-slate-800 bg-slate-900 p-6">
                    <p className="text-sm text-slate-400">
                        Loading provider actions...
                    </p>
                </div>
            )}

            {!isLoading && error && (
                <div
                    role="alert"
                    className="rounded-lg border border-red-500/30 bg-red-500/10 p-5"
                >
                    <p className="font-semibold text-red-300">
                        Action unavailable
                    </p>
                    <p className="mt-1 text-sm text-red-200/80">
                        {error}
                    </p>
                    <button
                        type="button"
                        onClick={() => void loadActions()}
                        className="mt-4 rounded-lg border border-red-400/30 px-3 py-2 text-sm font-medium text-red-200 transition hover:border-red-300/50 hover:text-white"
                    >
                        Try again
                    </button>
                </div>
            )}

            {!isLoading &&
                !error &&
                actions.length === 0 && (
                    <div className="rounded-lg border border-slate-800 bg-slate-900 p-6 text-sm text-slate-400">
                        This provider does not advertise any
                        actions.
                    </div>
                )}

            {!isLoading &&
                !error &&
                actions.length > 0 && (
                    <div className="grid gap-4 lg:grid-cols-2">
                        {actions.map((action) => {
                            const isRunning =
                                runningActionId === action.id;
                            const isBlocked =
                                runningActionId !== null ||
                                !action.enabled;

                            return (
                                <article
                                    key={action.id}
                                    className="rounded-lg border border-slate-800 bg-slate-900 p-6"
                                >
                                    <div className="flex items-start justify-between gap-4">
                                        <div>
                                            <h3 className="font-semibold text-slate-100">
                                                {action.label}
                                            </h3>
                                            <p className="mt-2 text-sm leading-6 text-slate-400">
                                                {action.description}
                                            </p>
                                        </div>

                                        <span
                                            className={
                                                action.enabled
                                                    ? "rounded-full border border-emerald-500/30 bg-emerald-500/10 px-3 py-1 text-xs font-medium text-emerald-300"
                                                    : "rounded-full border border-slate-700 bg-slate-950 px-3 py-1 text-xs font-medium text-slate-500"
                                            }
                                        >
                                            {action.enabled
                                                ? "Enabled"
                                                : "Disabled"}
                                        </span>
                                    </div>

                                    <div className="mt-5 flex flex-wrap gap-2">
                                        {action.requires_confirmation && (
                                            <span className="rounded-full border border-amber-500/30 bg-amber-500/10 px-3 py-1 text-xs text-amber-300">
                                                Confirmation required
                                            </span>
                                        )}

                                        {action.destructive && (
                                            <span className="rounded-full border border-red-500/30 bg-red-500/10 px-3 py-1 text-xs text-red-300">
                                                Destructive
                                            </span>
                                        )}
                                    </div>

                                    <button
                                        type="button"
                                        disabled={isBlocked}
                                        onClick={() =>
                                            void executeAction(
                                                action,
                                            )
                                        }
                                        className="mt-6 inline-flex min-w-36 items-center justify-center rounded-lg bg-blue-600 px-4 py-2 text-sm font-semibold text-white transition hover:bg-blue-500 disabled:cursor-not-allowed disabled:bg-slate-700 disabled:text-slate-400"
                                    >
                                        {isRunning
                                            ? "Running..."
                                            : action.label}
                                    </button>
                                </article>
                            );
                        })}
                    </div>
                )}

            {result && (
                <div
                    role="status"
                    className={
                        result.success
                            ? "mt-4 rounded-lg border border-emerald-500/30 bg-emerald-500/10 p-5"
                            : "mt-4 rounded-lg border border-red-500/30 bg-red-500/10 p-5"
                    }
                >
                    <p
                        className={
                            result.success
                                ? "font-semibold text-emerald-300"
                                : "font-semibold text-red-300"
                        }
                    >
                        {result.success
                            ? "Action completed"
                            : "Action failed"}
                    </p>

                    <p className="mt-1 text-sm text-slate-200">
                        {result.message}
                    </p>

                    {result.warnings.length > 0 && (
                        <ul className="mt-3 space-y-1 text-sm text-amber-200">
                            {result.warnings.map(
                                (warning, index) => (
                                    <li
                                        key={`${warning}-${index}`}
                                    >
                                        {warning}
                                    </li>
                                ),
                            )}
                        </ul>
                    )}
                </div>
            )}
        </section>
    );
}
