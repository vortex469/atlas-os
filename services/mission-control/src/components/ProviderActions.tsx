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
    const [parameters, setParameters] = useState<
        Record<string, ProviderActionParameters>
    >({});

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
            const actionParameters = parameters[action.id] ?? {};
            const actionResult = await runProviderAction(
                provider.id,
                action.id,
                {
                    confirmed,
                    parameters: actionParameters,
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
            {compact ? (
                <div className="mb-3">
                    <h3 className="text-sm font-semibold uppercase tracking-wider text-slate-400">
                        Operations
                    </h3>
                    <p className="mt-1 text-xs text-slate-500">
                        Safe actions advertised by this service provider.
                    </p>
                </div>
            ) : (
                <SectionHeader
                    title="Provider Actions"
                    description="Safe operations advertised by this provider."
                />
            )}

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
                                                                {
                                                                    parameterName
                                                                }
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
                                                                    null
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
