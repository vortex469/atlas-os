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
        summary: "mc-focusable cursor-pointer text-mc-primary-strong",
        group: "mt-2 rounded-lg border border-mc-border-subtle bg-mc-surface-muted p-3 text-sm text-mc-text-secondary",
        command: "mt-1 rounded border border-mc-border-subtle bg-mc-surface p-2",
        code: "text-mc-text-primary",
        note: "text-mc-text-secondary",
    },
    drawer: {
        details: "mt-2",
        summary: "mc-focusable cursor-pointer text-sm text-cyan-300",
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
            <summary className={style.summary}>Test from the Atlas computer</summary>
            <div role="group" aria-label="Next connection check" className={style.group}>
                <p>These commands only check status and send a GET request. They do not change Atlas or the service.</p>
                <ol aria-label="Steps to check the Atlas Core connection" className="list-decimal space-y-2 pl-5 text-sm">
                    <li>
                        <p>On the computer running Atlas Core, run this command. Find the <code>atlas-core</code> row: <code>Up</code> means running; <code>Exited</code> means stopped. No row means this Docker engine does not manage Atlas Core.</p>
                        <div role="group" aria-label="Atlas container status command" className={style.command}>
                            <div className="flex flex-wrap items-start gap-2">
                                <pre className={`min-w-0 flex-1 whitespace-pre-wrap break-all font-mono text-xs leading-5 ${style.code}`}>{serviceContainerCheckCommand}</pre>
                                <CopyCommandButton command={serviceContainerCheckCommand} />
                            </div>
                        </div>
                    </li>
                    <li>From Atlas&apos;s Compose folder (with <code>compose.production.yaml</code>), run this command to test whether Atlas Core can reach {name}. Running it on the service computer tests a different connection.</li>
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
                        <p className={`mt-2 text-sm ${style.note}`}>An HTTP status means the service answered. A timeout or connection error means Atlas Core got no HTTP response. Credentials and query values are left out.</p>
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
