import { useCallback, useEffect, useMemo, useState } from "react";

import { getAtlasErrorMessage } from "../api/atlas";
import {
    getProviderConnection,
    testProviderConnection,
    updateProviderConnection,
} from "../api/connections";
import type {
    ProviderConnectionField,
    ProviderConnectionSchema,
    TestProviderConnectionResult,
} from "../types/connections";
import type { Provider } from "../types/provider";
import { SectionHeader } from "./SectionHeader";

type ProviderConnectionProps = {
    provider: Provider;
};

type FormValues = Record<string, string | number | boolean>;

type BusyMode = "loading" | "testing" | "saving" | null;

export function ProviderConnection({ provider }: ProviderConnectionProps) {
    const hasConnectionCapability = provider.capabilities.includes("connection");
    const [schema, setSchema] = useState<ProviderConnectionSchema | null>(null);
    const [formValues, setFormValues] = useState<FormValues>({});
    const [secretValues, setSecretValues] = useState<Record<string, string>>({});
    const [busyMode, setBusyMode] = useState<BusyMode>(
        hasConnectionCapability ? "loading" : null,
    );
    const [error, setError] = useState<string | null>(null);
    const [testResult, setTestResult] =
        useState<TestProviderConnectionResult | null>(null);

    const loadConnection = useCallback(async () => {
        if (!hasConnectionCapability) {
            return;
        }

        setBusyMode("loading");
        setError(null);

        try {
            const nextSchema = await getProviderConnection(provider.id);
            setSchema(nextSchema);
            setFormValues(initialFormValues(nextSchema));
            setSecretValues({});
        } catch (requestError) {
            console.error(
                `Unable to load connection for ${provider.id}:`,
                requestError,
            );
            setError(
                getAtlasErrorMessage(
                    requestError,
                    `Mission Control could not load the connection schema for ${provider.name}.`,
                ),
            );
        } finally {
            setBusyMode(null);
        }
    }, [hasConnectionCapability, provider.id, provider.name]);

    useEffect(() => {
        if (!hasConnectionCapability) {
            return;
        }

        let cancelled = false;

        getProviderConnection(provider.id)
            .then((nextSchema) => {
                if (cancelled) {
                    return;
                }
                setSchema(nextSchema);
                setFormValues(initialFormValues(nextSchema));
                setSecretValues({});
            })
            .catch((requestError: unknown) => {
                if (cancelled) {
                    return;
                }
                console.error(
                    `Unable to load connection for ${provider.id}:`,
                    requestError,
                );
                setError(
                    getAtlasErrorMessage(
                        requestError,
                        `Mission Control could not load the connection schema for ${provider.name}.`,
                    ),
                );
            })
            .finally(() => {
                if (!cancelled) {
                    setBusyMode(null);
                }
            });

        return () => {
            cancelled = true;
        };
    }, [hasConnectionCapability, provider.id, provider.name]);

    const editableFields = useMemo(
        () => schema?.fields.filter((field) => field.editable) ?? [],
        [schema],
    );
    const canSave = Boolean(schema?.editable && editableFields.length > 0);
    const statusLabel = connectionStatus(schema);
    const isBusy = busyMode !== null;

    if (!hasConnectionCapability) {
        return null;
    }

    function updateFormField(
        field: ProviderConnectionField,
        value: string | number | boolean,
    ): void {
        if (field.secret) {
            setSecretValues((current) => ({
                ...current,
                [field.key]: String(value),
            }));
            return;
        }

        setFormValues((current) => ({
            ...current,
            [field.key]: normalizeFormValue(field, value),
        }));
    }

    async function runTest(): Promise<void> {
        if (!schema) {
            return;
        }

        const confirmed = window.confirm(
            `Run a live connection test for ${provider.name}?`,
        );
        if (!confirmed) {
            return;
        }

        setBusyMode("testing");
        setError(null);
        setTestResult(null);

        try {
            const result = await testProviderConnection(provider.id, {
                confirmed: true,
                values: requestValues(schema, formValues, secretValues),
            });
            setTestResult(result);
        } catch (requestError) {
            const message = sanitizeMessage(
                getAtlasErrorMessage(
                    requestError,
                    "Atlas Core could not test this provider connection.",
                ),
                secretValues,
            );
            console.error(
                `Unable to test connection for ${provider.id}:`,
                message,
            );
            setError(message);
        } finally {
            setBusyMode(null);
        }
    }

    async function saveConnection(): Promise<void> {
        if (!schema || !canSave) {
            return;
        }

        const confirmed = window.confirm(
            `Save connection settings for ${provider.name}?`,
        );
        if (!confirmed) {
            return;
        }

        setBusyMode("saving");
        setError(null);

        try {
            const result = await updateProviderConnection(provider.id, {
                confirmed: true,
                values: requestValues(schema, formValues, secretValues),
            });
            setSchema(result.connection_schema);
            setFormValues(initialFormValues(result.connection_schema));
            setSecretValues({});
            setTestResult(null);
        } catch (requestError) {
            const message = sanitizeMessage(
                getAtlasErrorMessage(
                    requestError,
                    "Atlas Core could not save this provider connection.",
                ),
                secretValues,
            );
            console.error(
                `Unable to save connection for ${provider.id}:`,
                message,
            );
            setError(message);
        } finally {
            setBusyMode(null);
        }
    }

    return (
        <section>
            <SectionHeader
                title="Connection"
                description="Manage how Atlas connects to this provider."
            />

            <div className="rounded-lg border border-slate-800 bg-slate-900 p-6">
                <div className="flex flex-wrap items-start justify-between gap-4">
                    <div>
                        <span className={statusClass(statusLabel)}>
                            {statusLabel}
                        </span>
                        {schema?.updated_at && (
                            <p className="mt-2 text-xs text-slate-500">
                                Last updated {formatTimestamp(schema.updated_at)}
                            </p>
                        )}
                        {schema?.metadata.reload_required === true && (
                            <p className="mt-2 text-sm text-amber-300">
                                Reload required for changes to take effect.
                            </p>
                        )}
                        {schema?.metadata.privileged_local_runtime === true && (
                            <p className="mt-2 text-sm text-amber-300">
                                Privileged local runtime connection. A read-only socket mount does not make the Docker API read-only.
                            </p>
                        )}
                    </div>

                    <button
                        type="button"
                        onClick={() => void loadConnection()}
                        disabled={isBusy}
                        className="rounded-lg border border-slate-700 px-3 py-2 text-sm font-medium text-slate-300 transition hover:border-slate-500 hover:text-white disabled:cursor-not-allowed disabled:opacity-50"
                    >
                        Reload Schema
                    </button>
                </div>

                {busyMode === "loading" && (
                    <p className="mt-6 text-sm text-slate-400">
                        Loading connection schema...
                    </p>
                )}

                {error && (
                    <div
                        role="alert"
                        className="mt-6 rounded-lg border border-red-500/30 bg-red-500/10 p-4 text-sm text-red-200"
                    >
                        {error}
                    </div>
                )}

                {schema && (
                    <>
                        <div className="mt-6 grid gap-4 lg:grid-cols-2">
                            {schema.fields.map((field) => (
                                <ConnectionField
                                    key={field.key}
                                    field={field}
                                    value={formValues[field.key]}
                                    secretValue={secretValues[field.key] ?? ""}
                                    disabled={isBusy || !field.editable}
                                    onChange={(value) => updateFormField(field, value)}
                                />
                            ))}
                        </div>

                        {testResult && (
                            <TestResult
                                result={testResult}
                                redactedValues={Object.values(secretValues)}
                            />
                        )}

                        <div className="mt-6 flex flex-wrap gap-3">
                            {schema.testable && (
                                <button
                                    type="button"
                                    onClick={() => void runTest()}
                                    disabled={isBusy}
                                    className="rounded-lg border border-blue-500/40 bg-blue-500/10 px-4 py-2 text-sm font-semibold text-blue-200 transition hover:border-blue-400 hover:text-white disabled:cursor-not-allowed disabled:opacity-50"
                                >
                                    {busyMode === "testing" ? "Testing..." : "Test Connection"}
                                </button>
                            )}

                            {canSave && (
                                <button
                                    type="button"
                                    onClick={() => void saveConnection()}
                                    disabled={isBusy}
                                    className="rounded-lg border border-emerald-500/40 bg-emerald-500/10 px-4 py-2 text-sm font-semibold text-emerald-200 transition hover:border-emerald-400 hover:text-white disabled:cursor-not-allowed disabled:opacity-50"
                                >
                                    {busyMode === "saving" ? "Saving..." : "Save Connection"}
                                </button>
                            )}

                            {!canSave && (
                                <span className="rounded-lg border border-slate-700 px-4 py-2 text-sm text-slate-400">
                                    Connection editing is not available for this provider.
                                </span>
                            )}
                        </div>
                    </>
                )}
            </div>
        </section>
    );
}

type ConnectionFieldProps = {
    field: ProviderConnectionField;
    value: string | number | boolean | undefined;
    secretValue: string;
    disabled: boolean;
    onChange: (value: string | number | boolean) => void;
};

function ConnectionField({
    field,
    value,
    secretValue,
    disabled,
    onChange,
}: ConnectionFieldProps) {
    const fieldId = `connection-${field.key}`;

    return (
        <label className="block rounded-lg border border-slate-800 bg-slate-950/50 p-4">
            <span className="flex items-center justify-between gap-3">
                <span className="text-sm font-semibold text-slate-200">
                    {field.label}
                    {field.required && <span className="text-amber-300"> *</span>}
                </span>
                <span className="text-xs text-slate-500">
                    {field.source ? `Source: ${field.source}` : "No source"}
                </span>
            </span>

            <div className="mt-3">
                {renderFieldControl({
                    field,
                    fieldId,
                    value,
                    secretValue,
                    disabled,
                    onChange,
                })}
            </div>

            {field.secret && (
                <p className="mt-2 text-xs text-slate-400">
                    Secret is {field.secret_state === "configured" ? "Configured" : "Missing"}. Leave blank to keep the existing value.
                </p>
            )}

            {field.help_text && (
                <p className="mt-2 text-xs text-slate-500">
                    {field.help_text}
                </p>
            )}
        </label>
    );
}

function renderFieldControl({
    field,
    fieldId,
    value,
    secretValue,
    disabled,
    onChange,
}: ConnectionFieldProps & { fieldId: string }) {
    const baseClass =
        "w-full rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-slate-100 disabled:cursor-not-allowed disabled:opacity-60";

    if (field.secret) {
        return (
            <input
                id={fieldId}
                aria-label={field.label}
                type="password"
                value={secretValue}
                disabled={disabled}
                placeholder="Enter replacement secret"
                onChange={(event) => onChange(event.target.value)}
                className={baseClass}
            />
        );
    }

    if (field.kind === "boolean") {
        return (
            <input
                id={fieldId}
                aria-label={field.label}
                type="checkbox"
                checked={Boolean(value)}
                disabled={disabled}
                onChange={(event) => onChange(event.target.checked)}
                className="h-5 w-5 rounded border-slate-600 bg-slate-950 text-blue-500 disabled:cursor-not-allowed disabled:opacity-60"
            />
        );
    }

    if (field.kind === "select") {
        return (
            <select
                id={fieldId}
                aria-label={field.label}
                value={String(value ?? "")}
                disabled={disabled}
                onChange={(event) => onChange(event.target.value)}
                className={baseClass}
            >
                <option value="">Select...</option>
                {field.options.map((option) => (
                    <option key={option.value} value={option.value}>
                        {option.label}
                    </option>
                ))}
            </select>
        );
    }

    return (
        <input
            id={fieldId}
            aria-label={field.label}
            type={field.kind === "port" ? "number" : "text"}
            value={String(value ?? "")}
            disabled={disabled}
            required={field.required}
            onChange={(event) => onChange(event.target.value)}
            className={baseClass}
        />
    );
}

function TestResult({
    result,
    redactedValues,
}: {
    result: TestProviderConnectionResult;
    redactedValues: string[];
}) {
    return (
        <div className="mt-6 rounded-lg border border-slate-800 bg-slate-950 p-4">
            <p className="text-sm font-semibold text-slate-200">
                Test {result.status}
                {result.latency_ms !== null && ` · ${result.latency_ms} ms`}
            </p>
            {result.message && (
                <p className="mt-1 text-sm text-slate-400">
                    {sanitizeText(result.message, redactedValues)}
                </p>
            )}
            {Object.keys(result.diagnostics).length > 0 && (
                <dl className="mt-3 grid gap-2 text-xs text-slate-500 sm:grid-cols-2">
                    {Object.entries(result.diagnostics).map(([key, value]) => (
                        <div key={key}>
                            <dt className="font-semibold text-slate-400">{key}</dt>
                            <dd>{formatDiagnosticValue(value, redactedValues)}</dd>
                        </div>
                    ))}
                </dl>
            )}
        </div>
    );
}

function initialFormValues(schema: ProviderConnectionSchema): FormValues {
    return Object.fromEntries(
        schema.fields
            .filter((field) => !field.secret)
            .map((field) => [
                field.key,
                field.current_value ?? defaultValue(field),
            ]),
    );
}

function defaultValue(field: ProviderConnectionField): string | number | boolean {
    if (field.kind === "boolean") {
        return false;
    }
    return "";
}

function normalizeFormValue(
    field: ProviderConnectionField,
    value: string | number | boolean,
): string | number | boolean {
    if (field.kind === "port" && value !== "") {
        return Number(value);
    }
    return value;
}

function requestValues(
    schema: ProviderConnectionSchema,
    formValues: FormValues,
    secretValues: Record<string, string>,
): Record<string, unknown> {
    const values: Record<string, unknown> = {};

    for (const field of schema.fields) {
        if (!field.editable) {
            continue;
        }
        if (field.secret) {
            const secretValue = secretValues[field.key];
            if (secretValue && secretValue.length > 0) {
                values[field.key] = secretValue;
            }
            continue;
        }
        values[field.key] = formValues[field.key] ?? defaultValue(field);
    }

    return values;
}

function connectionStatus(schema: ProviderConnectionSchema | null): string {
    if (!schema) {
        return "incomplete";
    }
    if (!schema.editable && schema.metadata.update_supported === false) {
        return "unsupported";
    }
    const requiredFields = schema.fields.filter((field) => field.required);
    const hasMissingRequired = requiredFields.some((field) => {
        if (field.secret) {
            return field.secret_state !== "configured";
        }
        return field.current_value === null || field.current_value === "";
    });
    return hasMissingRequired ? "incomplete" : "configured";
}

function statusClass(status: string): string {
    const base = "inline-flex rounded-full px-2.5 py-1 text-xs font-semibold uppercase tracking-wide";
    if (status === "configured") {
        return `${base} bg-emerald-500/10 text-emerald-300`;
    }
    if (status === "unsupported") {
        return `${base} bg-slate-700/60 text-slate-300`;
    }
    return `${base} bg-amber-500/10 text-amber-300`;
}

function formatTimestamp(value: string): string {
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) {
        return value;
    }
    return date.toLocaleString();
}

function formatDiagnosticValue(value: unknown, redactedValues: string[]): string {
    if (value === null || value === undefined) {
        return "none";
    }
    if (typeof value === "string" || typeof value === "number" || typeof value === "boolean") {
        return sanitizeText(String(value), redactedValues);
    }
    return sanitizeText(JSON.stringify(value), redactedValues);
}

function sanitizeMessage(
    message: string,
    secretValues: Record<string, string>,
): string {
    return sanitizeText(message, Object.values(secretValues));
}

function sanitizeText(message: string, redactedValues: string[]): string {
    return redactedValues.reduce((current, value) => {
        if (!value) {
            return current;
        }
        return current.split(value).join("[redacted]");
    }, message);
}
