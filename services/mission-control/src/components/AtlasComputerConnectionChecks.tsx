import { CopyCommandButton } from "./CopyCommandButton";
import {
    formatServiceCheckAddress,
    serviceContainerCheckCommand,
    serviceReachabilityCommand,
} from "../utils/serviceReachabilityCommand";
import { safeText } from "../utils/safeText";

type AtlasComputerConnectionChecksProps = {
    serviceName: string;
    address: unknown;
    surface: "overview" | "drawer";
};

const classes = {
    overview: {
        details: "mt-2 text-xs text-mc-text-muted",
        summary: "mc-focusable cursor-pointer break-words text-mc-primary-strong",
        group: "mt-2 rounded-lg border border-mc-border-subtle bg-mc-surface-muted p-3 text-sm text-mc-text-secondary",
        command: "mt-1 rounded border border-mc-border-subtle bg-mc-surface p-2",
        code: "text-mc-text-primary",
        note: "text-mc-text-secondary",
    },
    drawer: {
        details: "mt-2",
        summary: "mc-focusable cursor-pointer break-words text-sm text-cyan-300",
        group: "mt-2 rounded-lg border border-slate-800 bg-slate-900 p-3 text-sm text-slate-400",
        command: "mt-1 rounded border border-slate-800 bg-slate-900 p-2",
        code: "text-slate-200",
        note: "text-slate-400",
    },
} as const;

export function AtlasComputerConnectionChecks({
    serviceName,
    address,
    surface,
}: AtlasComputerConnectionChecksProps) {
    const style = classes[surface];
    const name = safeText(serviceName) || "this service";
    const checkedAddress = formatServiceCheckAddress(address);
    const command = serviceReachabilityCommand(address);

    return (
        <details className={style.details}>
            <summary className={style.summary}>Test the connection from Atlas Core to {name}</summary>
            <div role="group" aria-label="Next connection check" className={style.group}>
                <p>These commands only check status. They do not change Atlas or the service.</p>
                <ol aria-label="Steps to check the Atlas Core connection" className="list-decimal space-y-2 pl-5 text-sm">
                    <li>
                        <p>Run this on the computer where Atlas Core runs. Find the <code>atlas-core</code> row: <code>Up</code> means running; <code>Exited</code> means stopped. If no row appears, this Docker engine does not run Atlas Core.</p>
                        <div role="group" aria-label="Atlas container status command" className={style.command}>
                            <div className="flex flex-wrap items-start gap-2">
                                <pre className={`min-w-0 flex-1 whitespace-pre-wrap break-all font-mono text-xs leading-5 ${style.code}`}>{serviceContainerCheckCommand}</pre>
                                <CopyCommandButton command={serviceContainerCheckCommand} />
                            </div>
                        </div>
                    </li>
                    <li>Run this command from the folder containing <code>compose.production.yaml</code>. It checks whether Atlas Core can connect to {name}; running it on the service computer checks a different connection.</li>
                </ol>
                {surface === "overview" && <p className={checkedAddress ? "mt-1 break-all font-mono" : "mt-1"}>{checkedAddress ?? "Configured service address not reported"}</p>}
                {command ? (
                    <>
                        <div role="group" aria-label="Read-only Core connection check command" className={style.command}>
                            <div className="flex flex-wrap items-start gap-2">
                                <pre className={`min-w-0 flex-1 whitespace-pre-wrap break-all font-mono text-xs leading-5 ${style.code}`}>{command}</pre>
                                <CopyCommandButton command={command} />
                            </div>
                        </div>
                        <p className={`mt-2 text-sm ${style.note}`}>Any HTTP status means {name} answered from Atlas Core. A timeout or connection error means Atlas Core got no response. The command omits credentials and query values.</p>
                        <details className="mt-2">
                            <summary className={style.summary}>If Compose says the file is missing</summary>
                            <p className={`mt-2 text-sm ${style.note}`}>“No such file” means Compose did not run the check. Open Atlas&apos;s Compose folder or pass its full path with <code>--file</code>.</p>
                        </details>
                    </>
                ) : (
                    <p className={`mt-2 text-sm ${style.note}`}>No HTTP or HTTPS address was reported, so Atlas cannot provide a connection-check command.</p>
                )}
            </div>
        </details>
    );
}
