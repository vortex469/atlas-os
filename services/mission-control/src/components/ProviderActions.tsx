import {
    useCallback,
    useEffect,
    useRef,
    useState,
} from "react";
import { Link } from "react-router-dom";

import {
    getAtlasErrorMessage,
    getProviderActions,
    runProviderAction,
} from "../api/atlas";
import type { Provider } from "../types/provider";
import type {
    ProviderAction,
    ProviderActionParameters,
    ProviderActionResult,
} from "../types/providerAction";
import { SectionHeader } from "./SectionHeader";

type ProviderActionsProps = {
    provider: Pick<Provider, "id" | "name">;
    onActionCompleted: () => Promise<void> | void;
    compact?: boolean;
};

type ActionParameterDefinition = {
    type?: string;
    required?: boolean;
    description?: string;
    example?: string;
};

const parameterLabelTerms = new Map([
    ["api", "API"],
    ["id", "ID"],
    ["ip", "IP"],
    ["mac", "MAC"],
    ["ssh", "SSH"],
    ["url", "URL"],
    ["vm", "VM"],
    ["vmid", "VM ID"],
]);

function formatParameterLabel(value: string): string {
    return value
        .replace(/([a-z0-9])([A-Z])/g, "$1 $2")
        .split(/[_-]+/)
        .filter(Boolean)
        .map((part) => parameterLabelTerms.get(part.toLowerCase()) ?? `${part.charAt(0).toUpperCase()}${part.slice(1)}`)
        .join(" ");
}

function getParameterDefinition(
    value: unknown,
): ActionParameterDefinition {
    if (
        typeof value !== "object" ||
        value === null ||
        Array.isArray(value)
    ) {
        return {};
    }

    return value as ActionParameterDefinition;
}

export function ProviderActions({
    provider,
    onActionCompleted,
    compact = false,
}: ProviderActionsProps) {
    return <ProviderActionPanel key={provider.id} provider={provider} onActionCompleted={onActionCompleted} compact={compact} />;
}

function ProviderActionPanel({ provider, onActionCompleted, compact = false }: ProviderActionsProps) {
    const active = useRef(true);
    useEffect(() => {
        active.current = true;
        return () => { active.current = false; };
    }, []);
    const [actions, setActions] = useState<ProviderAction[]>(
        [],
    );
    const [isLoading, setIsLoading] = useState(true);
    const [runningActionId, setRunningActionId] = useState<
        string | null
    >(null);
    const [catalogError, setCatalogError] = useState<string | null>(null);
    const [catalogErrorDetails, setCatalogErrorDetails] = useState<string | null>(null);
    const [executionError, setExecutionError] = useState<string | null>(null);
    const [result, setResult] =
        useState<ProviderActionResult | null>(null);
    const [parameters, setParameters] = useState<
        Record<string, ProviderActionParameters>
    >({});

    const loadActions = useCallback(async () => {
        setIsLoading(true);
        setCatalogError(null);
        setCatalogErrorDetails(null);

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
            setCatalogError("Mission Control could not load the available actions. No action was run.");
            setCatalogErrorDetails(actionCatalogErrorDetails(requestError, provider.name));
        } finally {
            setIsLoading(false);
        }
    }, [provider.id, provider.name]);

    useEffect(() => {
        let cancelled = false;

        void Promise.resolve().then(() => {
            if (cancelled) return;
            return getProviderActions(provider.id)
                .then((providerActions) => {
                    if (cancelled) {
                        return;
                    }

                    setActions(providerActions);
                    setCatalogError(null);
                    setCatalogErrorDetails(null);
                })
                .catch((requestError: unknown) => {
                    if (cancelled) {
                        return;
                    }

                    console.error(
                        `Unable to load actions for ${provider.id}:`,
                        requestError,
                    );
                    setCatalogError("Mission Control could not load the available actions. No action was run.");
                    setCatalogErrorDetails(actionCatalogErrorDetails(requestError, provider.name));
                })
                .finally(() => {
                    if (!cancelled) {
                        setIsLoading(false);
                    }
                });
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
        setExecutionError(null);
        setResult(null);

        try {
            const actionParameters = parameters[action.id] ?? {};
            const actionResult = await runProviderAction(
                provider.id,
                action.id,
                {
                    confirmed,
                    parameters: actionParameters,
                },
            );

            if (!active.current) return;

            setResult(actionResult);

            if (actionResult.success) {
                await onActionCompleted();
            }
        } catch (requestError) {
            if (!active.current) return;
            console.error(
                `Unable to run ${action.id} for ${provider.id}:`,
                requestError,
            );
            setExecutionError(
                getAtlasErrorMessage(
                    requestError,
                    "Mission Control could not confirm the action result.",
                ),
            );
        } finally {
            if (active.current) setRunningActionId(null);
        }
    }

    return (
        <section>
            {compact ? (
                <div className="mb-3">
                    <h3 className="text-sm font-semibold uppercase tracking-wider text-slate-400">
                        Direct provider actions
                    </h3>
                    <p className="mt-1 text-xs text-slate-500">
                        These buttons run actions directly on this provider. Monitoring settings never run them. For planned maintenance, submit a request for review and approval.
                    </p>
                </div>
            ) : (
                <SectionHeader
                    title="Direct provider actions"
                    description="These buttons run actions directly on this provider. Monitoring settings never run them. For planned maintenance, submit a request for review and approval."
                />
            )}

            {isLoading && (
                <div className="rounded-lg border border-slate-800 bg-slate-900 p-6">
                    <p className="text-sm text-slate-400">
                        Loading available actions…
                    </p>
                </div>
            )}

            {!isLoading && catalogError && (
                <div
                    role="alert"
                    className="rounded-lg border border-red-500/30 bg-red-500/10 p-5"
                >
                    <h3 className="font-semibold text-red-300">
                        Direct provider actions are unavailable
                    </h3>
                    <p className="mt-1 text-sm text-red-200/80">
                        {catalogError}
                    </p>
                    {catalogErrorDetails && <details className="mt-3">
                        <summary className="cursor-pointer text-sm font-medium text-slate-300 focus:outline-none focus:ring-2 focus:ring-blue-300">Technical details</summary>
                        <p className="mt-2 break-words text-sm text-slate-400">{catalogErrorDetails}</p>
                    </details>}
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
                !catalogError &&
                actions.length === 0 && (
                    <div className="rounded-lg border border-slate-800 bg-slate-900 p-6 text-sm text-slate-400">
                        No actions are available for this provider.
                    </div>
                )}

            {!isLoading &&
                !catalogError &&
                actions.length > 0 && (
                    <div
                        className={
                            compact
                                ? "grid gap-3"
                                : "grid gap-4 lg:grid-cols-2"
                        }
                    >
                        {actions.map((action) => {
                            const isRunning =
                                runningActionId === action.id;
                            const parameterEntries =
                                Object.entries(action.parameters);
                            const actionParameters =
                                parameters[action.id] ?? {};
                            const hasMissingRequiredParameter =
                                parameterEntries.some(
                                    ([parameterName, schema]) => {
                                        const definition =
                                            getParameterDefinition(
                                                schema,
                                            );
                                        const value =
                                            actionParameters[
                                                parameterName
                                            ];

                                        return (
                                            definition.required ===
                                                true &&
                                            (typeof value !==
                                                "string" ||
                                                value.trim() === "")
                                        );
                                    },
                                );
                            const isBlocked =
                                runningActionId !== null ||
                                executionError !== null ||
                                !action.enabled ||
                                hasMissingRequiredParameter;

                            return (
                                <article
                                    key={action.id}
                                    className={`rounded-lg border border-slate-800 bg-slate-900 ${
                                        compact ? "p-4" : "p-6"
                                    }`}
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

                                    {parameterEntries.length > 0 && (
                                        <div className="mt-5 space-y-4">
                                            {parameterEntries.map(
                                                ([
                                                    parameterName,
                                                    schema,
                                                ]) => {
                                                    const definition =
                                                        getParameterDefinition(
                                                            schema,
                                                        );
                                                    const inputId = `${provider.id}-${action.id}-${parameterName}`;

                                                    return (
                                                        <div
                                                            key={
                                                                parameterName
                                                            }
                                                        >
                                                            <label
                                                                htmlFor={
                                                                    inputId
                                                                }
                                                                className="text-sm font-medium text-slate-300"
                                                            >
                                                                {formatParameterLabel(parameterName)}
                                                                {definition.required && (
                                                                    <span className="text-red-300">
                                                                        {" "}
                                                                        *
                                                                    </span>
                                                                )}
                                                            </label>
                                                            <input
                                                                id={
                                                                    inputId
                                                                }
                                                                type="text"
                                                                value={
                                                                    typeof actionParameters[
                                                                        parameterName
                                                                    ] ===
                                                                    "string"
                                                                        ? String(
                                                                              actionParameters[
                                                                                  parameterName
                                                                              ],
                                                                          )
                                                                        : ""
                                                                }
                                                                placeholder={
                                                                    definition.example
                                                                }
                                                                disabled={
                                                                    runningActionId !==
                                                                    null ||
                                                                    executionError !== null
                                                                }
                                                                onChange={(
                                                                    event,
                                                                ) =>
                                                                    setParameters(
                                                                        (
                                                                            current,
                                                                        ) => ({
                                                                            ...current,
                                                                            [action.id]:
                                                                                {
                                                                                    ...(current[
                                                                                        action
                                                                                            .id
                                                                                    ] ??
                                                                                        {}),
                                                                                    [parameterName]:
                                                                                        event
                                                                                            .target
                                                                                            .value,
                                                                                },
                                                                        }),
                                                                    )
                                                                }
                                                                className="mt-2 w-full rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-slate-100 outline-none transition placeholder:text-slate-600 focus:border-blue-500 disabled:cursor-not-allowed disabled:opacity-50"
                                                            />
                                                            {definition.description && (
                                                                <p className="mt-1 text-xs text-slate-500">
                                                                    {
                                                                        definition.description
                                                                    }
                                                                </p>
                                                            )}
                                                        </div>
                                                    );
                                                },
                                            )}
                                        </div>
                                    )}

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

            {executionError && (
                <div role="alert" className="mt-4 rounded-lg border border-red-500/30 bg-red-500/10 p-5">
                    <h3 className="font-semibold text-red-300">Action result unavailable</h3>
                    <p className="mt-1 text-sm text-red-200/80">The action may have completed, but Mission Control did not receive a final result. Direct provider actions are paused here to prevent a duplicate.</p>
                    <p className="mt-2 text-sm text-slate-300">Check Action history, then reload this provider page before deciding whether to try again.</p>
                    <Link to="/operations" className="mt-3 inline-flex text-sm font-semibold text-blue-300 underline underline-offset-4">Open Action history →</Link>
                    <details className="mt-3">
                        <summary className="cursor-pointer text-sm font-medium text-slate-300 focus:outline-none focus:ring-2 focus:ring-blue-300">Technical details</summary>
                        <p className="mt-2 break-words text-sm text-slate-400">{executionError}</p>
                    </details>
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

function actionCatalogErrorDetails(error: unknown, providerName: string): string | null {
    const fallback = `Mission Control could not load actions for ${providerName}.`;
    const details = getAtlasErrorMessage(error, fallback);
    return details === fallback ? null : details;
}
