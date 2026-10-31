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
        <p className="text-sm leading-6 text-mc-text-secondary">These checks run on the computer where {name} runs. They show whether it is running there, not whether Atlas Core can connect. If it is installed directly on this computer, check that it is running on the port Atlas uses.</p>
        {reachabilityCommand && <div className="space-y-1 pt-1 text-sm leading-6 text-mc-text-secondary">
            <p>Check whether the app answers at the address Atlas uses:</p>
            <div role="group" aria-label="Service computer HTTP check command" className="flex flex-wrap items-start gap-2 rounded border border-slate-800 bg-slate-900 p-2">
                <code className="min-w-0 flex-1 break-all font-mono text-xs text-slate-200">{reachabilityCommand}</code>
                <CopyCommandButton command={reachabilityCommand} />
            </div>
            <p>Any HTTP status means {name} answered from this computer. HTTP 000 or a curl error means it did not answer. This does not test whether Atlas Core can connect.</p>
        </div>}
        {listeningPortCommand && <div className="space-y-1 pt-1 text-sm leading-6 text-mc-text-secondary">
            <p>On a Linux computer that runs {name}, run this read-only check for the configured port:</p>
            <div role="group" aria-label="Service computer listening-port command" className="flex flex-wrap items-start gap-2 rounded border border-slate-800 bg-slate-900 p-2">
                <code className="min-w-0 flex-1 break-all font-mono text-xs text-slate-200">{listeningPortCommand}</code>
                <CopyCommandButton command={listeningPortCommand} />
            </div>
            <p>Read the <code>Local Address:Port</code> column. <code>127.0.0.1:PORT</code> accepts connections only from this computer. <code>0.0.0.0:PORT</code> or this computer&apos;s LAN address can accept connections from other computers if the firewall allows them. A <code>LISTEN</code> row means a program is listening; it does not prove the app responds. No row means nothing is listening on this port. If {name} runs in Docker, also check its published ports below.</p>
        </div>}
        <details className="pt-1">
            <summary className="mc-focusable cursor-pointer text-sm text-mc-primary-strong">If the app runs in Docker</summary>
            <ol aria-label="Docker and Compose checks" className="mt-2 list-decimal space-y-2 pl-5 text-sm leading-6 text-mc-text-secondary">
                <li>
                    <div className="space-y-1">
                        <p>On the computer that runs {name}, run <code>{serviceContainerCheckCommand}</code>. Use the container name or image to find {name}; Docker&apos;s name may differ from Atlas&apos;s. The list also shows whether containers are running, their networks, and published ports.</p>
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
