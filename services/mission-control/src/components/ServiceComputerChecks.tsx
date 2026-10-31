import { CopyCommandButton } from "./CopyCommandButton";
import { serviceContainerCheckCommand } from "../utils/serviceReachabilityCommand";

export function ServiceComputerChecks() {
    return <>
        <p className="text-sm leading-6 text-mc-text-secondary">Confirm the app is running and listening at the configured address. If it runs directly on this computer, check the app&apos;s own status and listening port.</p>
        <details className="pt-1">
            <summary className="mc-focusable cursor-pointer text-sm text-mc-primary-strong">If the app runs in Docker</summary>
            <ol aria-label="Docker and Compose checks" className="mt-2 list-decimal space-y-2 pl-5 text-sm leading-6 text-mc-text-secondary">
                <li>
                    <div className="space-y-1">
                        <p>On the service computer, run <code>{serviceContainerCheckCommand}</code>. It lists running and stopped containers, networks, and published ports.</p>
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
