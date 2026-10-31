import { CopyCommandButton } from "./CopyCommandButton";
import {
    serviceComputerReachabilityCommand,
    serviceContainerCheckCommand,
    serviceListeningPortCommand,
} from "../utils/serviceReachabilityCommand";
import { safeText } from "../utils/safeText";

export function ServiceComputerChecks({ address, serviceName }: { address: unknown; serviceName: unknown }) {
    const reachabilityCommand = serviceComputerReachabilityCommand(address);
    const listeningPortCommand = serviceListeningPortCommand(address);
    const name = safeText(serviceName) || "the service";
    return <>
        <p className="text-sm leading-6 text-mc-text-secondary">These checks run on the computer that runs {name}. They show whether the app is running locally; they do not test whether Atlas Core can reach it. If the app runs directly on this computer, check its own status and listening port.</p>
        {reachabilityCommand && <div className="space-y-1 pt-1 text-sm leading-6 text-mc-text-secondary">
            <p>Check whether the app answers at the address Atlas uses:</p>
            <div role="group" aria-label="Service computer HTTP check command" className="flex flex-wrap items-start gap-2 rounded border border-slate-800 bg-slate-900 p-2">
                <code className="min-w-0 flex-1 break-all font-mono text-xs text-slate-200">{reachabilityCommand}</code>
                <CopyCommandButton command={reachabilityCommand} />
            </div>
            <p>Any HTTP status means the app answered from this computer. HTTP 000 or a curl error means no response. This check does not test the connection from Atlas Core.</p>
        </div>}
        {listeningPortCommand && <div className="space-y-1 pt-1 text-sm leading-6 text-mc-text-secondary">
            <p>On a Linux computer that runs {name}, run this read-only check for the configured port:</p>
            <div role="group" aria-label="Service computer listening-port command" className="flex flex-wrap items-start gap-2 rounded border border-slate-800 bg-slate-900 p-2">
                <code className="min-w-0 flex-1 break-all font-mono text-xs text-slate-200">{listeningPortCommand}</code>
                <CopyCommandButton command={listeningPortCommand} />
            </div>
            <p>A <code>LISTEN</code> row means something is listening on that port. No row means nothing is listening on that port on this computer. If the app runs in Docker, also check its port mapping below.</p>
        </div>}
        <details className="pt-1">
            <summary className="mc-focusable cursor-pointer text-sm text-mc-primary-strong">If the app runs in Docker</summary>
            <ol aria-label="Docker and Compose checks" className="mt-2 list-decimal space-y-2 pl-5 text-sm leading-6 text-mc-text-secondary">
                <li>
                    <div className="space-y-1">
                        <p>On the computer that runs {name}, run <code>{serviceContainerCheckCommand}</code>. It lists running and stopped containers, networks, and published ports.</p>
                        <CopyCommandButton command={serviceContainerCheckCommand} />
                    </div>
                </li>
                <li>
                    Find the app&apos;s container. <code>Up</code> means it is running; <code>Exited</code> means it stopped. If it is missing, this Docker engine does not manage it. Check another engine or VM, or whether the app runs directly on the computer. A running container does not prove its web app responds.
                </li>
                <li>
                    Check <code>PORTS</code>. With host networking, a blank value is expected because the app listens on the service computer&apos;s port. Otherwise, blank means no host port is published. A mapping starting with <code>127.0.0.1:</code> works only on that computer.
                </li>
                <li>
                    To publish a port, use Compose&apos;s <code>ports:</code> or <code>docker run -p</code>. For <code>HOST_PORT:CONTAINER_PORT</code>, use <code>HOST_PORT</code> in Atlas&apos;s address and match <code>CONTAINER_PORT</code> to the app&apos;s listening port. Recreate the container after changing the ports.
                </li>
            </ol>
        </details>
    </>;
}
