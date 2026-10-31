import { fireEvent, render, screen, within } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";
import { Overview } from "./MissionControl";
import { safeText, timestamp, status, detailPath } from "./overviewEvidence";
import type { OverviewEvidence } from "./useOverviewEvidence";
const show = (evidence: OverviewEvidence = {}, loading = false) => render(<MemoryRouter><Overview evidence={evidence} loading={loading} /></MemoryRouter>);
const activity = () => within(screen.getByRole('region', { name: 'Recent provider actions' }));

describe("MC overview evidence", () => {
    it.each(['awaiting_implementation_approval', 'awaiting_verification_approval', 'awaiting_commit_approval'])("shows %s as a workflow decision rather than degraded health", workflow_state => {
        show({ workflows: { data: { items: [{ workflow_id: 'review-me', workflow_state, last_result_summary: 'Review the exact request', timeline: [] }], total: 1, limit: 200, offset: 0 } } });
        const attention = within(screen.getByRole('region', { name: 'Needs attention' }));
        const expectedStage = workflow_state === 'awaiting_implementation_approval'
            ? 'Review the change. If approved, choose Run approved change.'
            : workflow_state === 'awaiting_verification_approval'
                ? 'Review the checks. If approved, choose Run approved checks.'
                : 'Review the commit. If approved, choose Record approved commit.';
        expect(attention.getByRole('link', { name: 'Workflow' })).toHaveAttribute('href', '/workflows/review-me');
        expect(attention.getByText(`Action needed: ${expectedStage}`)).toBeVisible();
        const workflowId = attention.getByText('review-me');
        expect(workflowId).not.toBeVisible();
        fireEvent.click(attention.getByText('Technical details'));
        expect(workflowId).toBeVisible();
        expect(attention.queryByText('Degraded', { exact: true })).not.toBeInTheDocument();
    });

    it("describes operational approval as maintenance request approval", () => {
        show({ workflows: { data: { items: [{
            workflow_id: 'maintenance-review', workflow_state: 'awaiting_implementation_approval',
            effect_kind: 'operational_action', execution_intent: 'restart-service',
            last_result_summary: 'Waiting for implementation approval', timeline: [],
        }], total: 1, limit: 200, offset: 0 } } });
        const attention = within(screen.getByRole('region', { name: 'Needs attention' }));
        expect(attention.getByRole('link', { name: 'Restart Service' })).toHaveAttribute('href', '/workflows/maintenance-review');
        expect(attention.getByText('Action needed: Review the maintenance request. If approved, choose Run approved maintenance.')).toBeVisible();
        expect(attention.queryByText('Action needed: Review the change. If approved, choose Run approved change.')).not.toBeInTheDocument();
        expect(attention.queryByText('Waiting for implementation approval', { exact: true })).not.toBeInTheDocument();
    });

    it("plainly marks the stale maintenance approval report", () => {
        show({ workflows: { stale: true, unavailable: true, data: { items: [{
            workflow_id: 'old-maintenance-review', workflow_state: 'awaiting_implementation_approval',
            effect_kind: 'operational_action', execution_intent: 'restart-service',
            last_result_summary: 'Waiting for implementation approval', timeline: [],
        }], total: 1, limit: 200, offset: 0 } } });
        const attention = within(screen.getByRole('region', { name: 'Needs attention' }));
        expect(attention.getByRole('link', { name: 'Restart Service' })).toBeVisible();
        expect(attention.getByText('Last report: this workflow was waiting for maintenance request approval. Atlas could not confirm whether it still needs attention.')).toBeVisible();
        expect(attention.queryByText('Waiting for implementation approval', { exact: true })).not.toBeInTheDocument();
    });

    it('names a workflow attention item by its proposed action and keeps its ID in technical details', () => {
        show({ workflows: { data: { items: [{
            workflow_id: 'workflow-123', workflow_state: 'awaiting_verification_approval',
            execution_intent: 'update-compose-stack', last_result_summary: 'Review the exact verification', timeline: [],
        }], total: 1, limit: 200, offset: 0 } } });
        const attention = within(screen.getByRole('region', { name: 'Needs attention' }));
        expect(attention.getByRole('link', { name: 'Update Compose Stack' })).toHaveAttribute('href', '/workflows/workflow-123');
        expect(attention.getByText('Action needed: Review the checks. If approved, choose Run approved checks.')).toBeVisible();
        expect(attention.getByText('Review the exact verification')).toBeVisible();
        const workflowId = attention.getByText('workflow-123');
        expect(workflowId).not.toBeVisible();
        fireEvent.click(attention.getByText('Technical details'));
        expect(workflowId).toBeVisible();
    });

    it('keeps attention focused on direct condition links', () => {
        show({ workflows: { data: { items: [{
            workflow_id: 'review-me', workflow_state: 'awaiting_implementation_approval', timeline: [],
        }], total: 1, limit: 200, offset: 0 } } });
        const attention = within(screen.getByRole('region', { name: 'Needs attention' }));
        expect(attention.getByRole('link', { name: 'Workflow' })).toHaveAttribute('href', '/workflows/review-me');
        expect(attention.getByText('Action needed: Review the change. If approved, choose Run approved change.')).toBeVisible();
        expect(attention.queryByRole('link', { name: 'Review operational conditions →' })).not.toBeInTheDocument();
        expect(attention.queryByRole('link', { name: 'Review workflow attention →' })).not.toBeInTheDocument();
        expect(within(screen.getByRole('region', { name: 'Work activity' })).getByRole('link', { name: 'Review workflows →' })).toHaveAttribute('href', '/workflows');
        expect(within(screen.getByRole('region', { name: 'System health' })).queryByRole('link')).not.toBeInTheDocument();
        expect(within(screen.getByRole('region', { name: 'Service checks' })).queryByRole('link')).not.toBeInTheDocument();
    });

    it('prioritizes decisions and lets operators expand the full attention list', () => {
        const services = Object.fromEntries(Array.from({ length: 6 }, (_, index) => [`service-${index}`, {
            provider_id: `provider-${index}`,
            status: 'degraded',
            message: `Service ${index} needs attention`,
        }]));
        services.blocked = { provider_id: 'priority-blocked', status: 'blocked', message: 'This service is blocked' };
        show({
            health: { data: { atlas: 'healthy', services } },
            summary: { data: { findings: [{
                id: 'critical-finding',
                source: 'core',
                title: 'Critical condition',
                message: 'Immediate review required',
                severity: 'critical',
            }] } },
            workflows: { data: { items: [{
                workflow_id: 'needs-commit-review',
                workflow_state: 'awaiting_commit_approval',
                execution_intent: 'update-compose-stack',
                timeline: [],
            }], total: 1, limit: 200, offset: 0 } },
        });

        const attention = within(screen.getByRole('region', { name: 'Needs attention' }));
        const attentionList = attention.getByRole('list', { name: 'Items needing attention' });
        const visibleItems = within(attentionList).getAllByRole('listitem');
        expect(visibleItems).toHaveLength(5);
        expect(within(visibleItems[0]).getByRole('link')).toHaveTextContent('blocked');
        expect(within(visibleItems[1]).getByRole('link', { name: 'Critical condition' })).toBeVisible();
        expect(within(visibleItems[1]).getByRole('link', { name: 'Critical condition' })).toHaveAttribute('href', '#system-health');
        expect(within(visibleItems[2]).getByRole('link', {
            name: 'Update Compose Stack',
        })).toBeVisible();
        expect(screen.getByRole('region', { name: 'System health' })).toHaveAttribute('id', 'system-health');
        const expand = attention.getByRole('button', { name: 'Show all 9 items' });
        expect(expand).toHaveAttribute('aria-expanded', 'false');
        fireEvent.click(expand);
        expect(within(attentionList).getAllByRole('listitem')).toHaveLength(9);
        expect(attention.getByRole('link', { name: 'service-5' })).toHaveAttribute('href', '#service-checks');
        const collapse = attention.getByRole('button', { name: 'Show fewer items' });
        expect(collapse).toHaveAttribute('aria-expanded', 'true');
        fireEvent.click(collapse);
        expect(within(attentionList).getAllByRole('listitem')).toHaveLength(5);
    });

    it('lets operators expand and collapse all reported service checks', () => {
        const services = Object.fromEntries(Array.from({ length: 6 }, (_, index) => [`service-${index}`, {
            status: 'healthy',
            message: `Service ${index} status detail`,
        }]));
        show({ health: { data: { atlas: 'healthy', services } } });

        const checks = within(screen.getByRole('region', { name: 'Service checks' }));
        const serviceChecks = checks.getByRole("list", { name: "Configured service checks" });
        const serviceItems = () => Array.from(serviceChecks.querySelectorAll(":scope > li"));
        expect(serviceItems()).toHaveLength(4);
        expect(checks.queryByText('service-5')).not.toBeInTheDocument();

        const expand = checks.getByRole('button', { name: 'Show all 6 service checks' });
        expect(expand).toHaveAttribute('aria-expanded', 'false');
        fireEvent.click(expand);
        expect(serviceItems()).toHaveLength(6);
        expect(checks.getByText('service-5')).toBeVisible();

        const collapse = checks.getByRole('button', { name: 'Show fewer service checks' });
        expect(collapse).toHaveAttribute('aria-expanded', 'true');
        fireEvent.click(collapse);
        expect(serviceItems()).toHaveLength(4);
    });

    it("shows the most urgent service checks before the four-item preview cutoff", () => {
        show({ health: { data: { services: {
            Degraded: { status: "degraded" },
            Healthy: { status: "healthy" },
            Offline: { status: "offline" },
            Blocked: { status: "blocked" },
            Unknown: { status: "future_state" },
        } } } });
        const checks = within(screen.getByRole("region", { name: "Service checks" }));
        const serviceChecks = checks.getByRole("list", { name: "Configured service checks" });
        const visibleNames = Array.from(serviceChecks.querySelectorAll(":scope > li"))
            .map(item => item.querySelector("p")?.textContent);

        expect(visibleNames).toEqual(["Blocked", "Offline", "Degraded", "Unknown"]);
        expect(checks.queryByText("Healthy", { exact: true })).not.toBeInTheDocument();
    });

    it("describes unavailable service attention as a failed connection from Atlas Core", () => {
        show({ health: { data: { services: { iFileshare: {
            provider_id: "ifileshare",
            status: "offline",
            message: "Connection refused",
        }, PhotoShare: {
            provider_id: "photoshare",
            status: "offline",
            message: "Connection timed out",
        } } } } });
        const checks = within(screen.getByRole("region", { name: "Service checks" }));
        expect(checks.getByText("An unavailable service did not respond to Atlas Core. It might still be running on its own computer.")).toBeVisible();
        expect(checks.getAllByText("An unavailable service did not respond to Atlas Core. It might still be running on its own computer.")).toHaveLength(1);
        expect(checks.queryByText("Atlas Core could not reach this service. That does not tell whether its app is running on its own computer.")).not.toBeInTheDocument();
        expect(checks.getByText("iFileshare", { exact: true })).toBeVisible();
        expect(checks.getByText("PhotoShare", { exact: true })).toBeVisible();
        const attention = within(screen.getByRole("region", { name: "Needs attention" }));
        const conditions = within(attention.getByRole("list", { name: "Items needing attention" }));
        const condition = within(conditions.getByRole("link", { name: "iFileshare" }).closest("li") as HTMLElement);

        expect(condition.getByText("Atlas Core could not connect", { exact: true })).toBeVisible();
        expect(condition.queryByText("Unavailable", { exact: true })).not.toBeInTheDocument();
        expect(condition.getByRole("link", { name: "iFileshare" })).toHaveAttribute("href", "#service-checks");
        expect(screen.getByRole("region", { name: "Service checks" })).toHaveAttribute("id", "service-checks");
    });

    it("hides the unavailable-service explanation when all configured services are healthy", () => {
        show({ health: { data: { atlas: "healthy", services: {
            iFileshare: { status: "healthy" },
            PhotoShare: { status: "healthy" },
        } } } });

        expect(within(screen.getByRole("region", { name: "Service checks" })).queryByText(
            "An unavailable service did not respond to Atlas Core. It might still be running on its own computer.",
        )).not.toBeInTheDocument();
    });

    it("makes a responding service's unexpected HTTP status clear in the summary", () => {
        show({ health: { data: { services: { iFileshare: {
            provider_id: "ifileshare",
            status: "degraded",
            http_status: 503,
            message: "Service returned an unexpected status.",
        } } } } });

        const explanation = "The service answered HTTP 503, but Atlas Core does not count that response as healthy.";
        expect(within(screen.getByRole("region", { name: "Service checks" })).getByText(explanation)).toBeVisible();
        expect(within(screen.getByRole("region", { name: "Needs attention" })).getByText(explanation)).toBeVisible();
    });

    it("routes service-sourced findings to service checks instead of provider details", () => {
        show({
            health: { data: { services: { iFileshare: {
                provider_id: "ifileshare",
                status: "healthy",
                message: "The previous check timed out.",
            } } } },
            summary: { data: { findings: [{
                id: "ifileshare-recovery-review",
                source: "ifileshare",
                title: "iFileshare needs review",
                message: "The previous check timed out.",
                severity: "warning",
            }] } },
        });

        const attention = within(screen.getByRole("region", { name: "Needs attention" }));
        expect(attention.getByRole("link", { name: "iFileshare needs review" })).toHaveAttribute("href", "#service-checks");
    });

    it("shows a short next step and keeps extra connection checks collapsed", () => {
        show({ health: { data: { atlas: "degraded", services: { iFileshare: {
            status: "offline",
            message: "No route to host",
            details: { url: "http://operator:password@10.10.60.30:8080/?token=private" },
        } } } } });
        const checks = within(screen.getByRole("region", { name: "Service checks" }));
        const howToCheck = checks.getByText("Test the connection from Atlas Core to iFileshare");
        const connectionDetails = howToCheck.closest("details");
        const disclosureLabels = Array.from(
            screen.getByRole("region", { name: "Service checks" }).querySelectorAll("summary"),
            (summary) => summary.textContent ?? "",
        );
        expect(disclosureLabels.indexOf("Check iFileshare on the computer where it runs")).toBeLessThan(
            disclosureLabels.indexOf("Test the connection from Atlas Core to iFileshare"),
        );
        expect(connectionDetails).not.toHaveAttribute("open");
        expect(checks.getByText("An unavailable service did not respond to Atlas Core. It might still be running on its own computer.")).toBeVisible();
        fireEvent.click(howToCheck);
        const nextStep = checks.getByRole("group", { name: "Next connection check" });
        const summary = checks.getByText("Check iFileshare on the computer where it runs");
        const disclosure = summary.closest("details");

        const instructions = within(nextStep).getByRole("list", { name: "Steps to check the Atlas Core connection" });
        expect(instructions).toBeVisible();
        expect(nextStep).toHaveTextContent("These commands only check status. They do not change Atlas or the service.");
        expect(instructions).toHaveTextContent("Run this on the computer where Atlas Core runs. Find the atlas-core row: Up means running; Exited means stopped. If no row appears, this Docker engine does not run Atlas Core.");
        const atlasCommand = within(nextStep).getByRole("group", { name: "Atlas container status command" });
        expect(atlasCommand).toHaveTextContent("docker ps --all --format 'table {{.Names}}\\t{{.Image}}\\t{{.Status}}\\t{{.Networks}}\\t{{.Ports}}'");
        expect(instructions).toHaveTextContent("Run this command from the folder containing compose.production.yaml. It checks whether Atlas Core can connect to iFileshare; running it on the service computer checks a different connection.");
        expect(nextStep).toHaveTextContent("http://10.10.60.30:8080/?…");
        const command = within(nextStep).getByRole("group", { name: "Read-only Core connection check command" });
        expect(command).toHaveTextContent("docker compose --file compose.production.yaml exec --no-TTY atlas-core python -c");
        expect(command).toHaveTextContent('httpx.get("http://10.10.60.30:8080/"');
        expect(command).not.toHaveTextContent(/password|private|token=/);
        expect(nextStep).toHaveTextContent("Any HTTP status means iFileshare answered from Atlas Core. A timeout or connection error means Atlas Core got no response. The command omits credentials and query values.");
        const composeHelp = within(nextStep).getByText("If Compose says the file is missing").closest("details");
        expect(composeHelp).not.toHaveAttribute("open");
        fireEvent.click(within(composeHelp as HTMLDetailsElement).getByText("If Compose says the file is missing"));
        expect(composeHelp).toHaveTextContent("“No such file” means Compose did not run the check. Open Atlas's Compose folder or pass its full path with --file.");
        expect(nextStep).not.toHaveTextContent("blank PORTS field");
        expect(nextStep).not.toHaveTextContent("With host networking");
        expect(nextStep).not.toHaveTextContent(/password|private/);
        expect(disclosure).not.toHaveAttribute("open");
        fireEvent.click(summary);

        expect(disclosure).toHaveTextContent("http://10.10.60.30:8080/?…");
        expect(disclosure).toHaveTextContent("These checks run on the computer where iFileshare runs. They show whether it is running there, not whether Atlas Core can connect. If it is installed directly on this computer, check that it is running on the port Atlas uses.");
        const localHttpCheck = within(disclosure as HTMLDetailsElement).getByRole("group", { name: "Service computer HTTP check command" });
        expect(localHttpCheck).toHaveTextContent("curl --silent --show-error --output /dev/null --write-out 'HTTP %{http_code}\\n' --connect-timeout 2 --max-time 5 -- 'http://10.10.60.30:8080/'");
        expect(localHttpCheck).not.toHaveTextContent(/password|private|token=/);
        expect(disclosure).toHaveTextContent("Any HTTP status means iFileshare answered from this computer. HTTP 000 or a curl error means it did not answer. This does not test whether Atlas Core can connect.");
        const dockerSummary = within(disclosure as HTMLDetailsElement).getByText("If the app runs in Docker");
        expect(dockerSummary.closest("details")).not.toHaveAttribute("open");
        const dockerSteps = within(disclosure as HTMLDetailsElement).getByRole("list", { name: "Docker and Compose checks" });
        expect(dockerSteps).not.toBeVisible();
        fireEvent.click(dockerSummary);
        const steps = within(disclosure as HTMLDetailsElement).getByRole("list", {
            name: "Docker and Compose checks",
        });
        expect(within(steps).getAllByRole("listitem")).toHaveLength(4);
        expect(steps).toHaveClass("text-sm");
        expect(steps).not.toHaveTextContent("Run the test on the computer running Atlas Core or inside its atlas-core container.");
        expect(steps).toHaveTextContent("docker ps --all --format 'table {{.Names}}\\t{{.Image}}\\t{{.Status}}\\t{{.Networks}}\\t{{.Ports}}'");
        expect(steps).toHaveTextContent("Use the container name or image to find iFileshare; Docker's name may differ from Atlas's.");
        expect(steps).toHaveTextContent("The list also shows whether containers are running, their networks, and published ports.");
        expect(steps).toHaveTextContent("Up means it is running; Exited means it stopped.");
        expect(steps).toHaveTextContent("If it is missing, this Docker engine does not manage it.");
        expect(steps).toHaveTextContent("A running container does not prove its web app responds.");
        expect(steps).toHaveTextContent("Exited means it stopped.");
        expect(steps).toHaveTextContent("Check PORTS. With host networking, a blank value is expected because the app listens on the service computer's port.");
        expect(steps).toHaveTextContent("Otherwise, blank means no host port is published.");
        expect(steps).toHaveTextContent("A mapping starting with 127.0.0.1: works only on that computer.");
        expect(steps).toHaveTextContent("To publish a port, use Compose's ports: or docker run -p.");
        expect(steps).toHaveTextContent("use HOST_PORT in Atlas's address and match CONTAINER_PORT to the app's listening port.");
        expect(steps).toHaveTextContent("Recreate the container after changing the ports.");
        expect(steps).not.toHaveTextContent("With Docker host networking");
        expect(steps).toHaveTextContent("HOST_PORT:CONTAINER_PORT");
        expect(disclosure).toHaveTextContent("HTTP response: No response received");
        expect(disclosure).toHaveTextContent("Next check: Check the target address and the network or firewall route from Atlas Core to the service host.");
        expect(disclosure).not.toHaveTextContent(/password|private/);
    });

    it("copies the sanitized Atlas connection check and reports success", async () => {
        const writeText = vi.fn().mockResolvedValue(undefined);
        Object.defineProperty(navigator, "clipboard", {
            configurable: true,
            value: { writeText },
        });
        show({ health: { data: { services: { iFileshare: {
            status: "unavailable",
            details: { url: "http://operator:password@10.10.60.30:8080/?token=private" },
        } } } } });
        const checks = within(screen.getByRole("region", { name: "Service checks" }));
        fireEvent.click(checks.getByText("Test the connection from Atlas Core to iFileshare"));
        const command = checks.getByRole("group", { name: "Read-only Core connection check command" });

        fireEvent.click(within(command).getByRole("button", { name: "Copy command" }));

        expect(await within(command).findByRole("status")).toHaveTextContent("Command copied.");
        expect(writeText).toHaveBeenCalledTimes(1);
        expect(writeText.mock.calls[0][0]).toContain("http://10.10.60.30:8080/");
        expect(writeText.mock.calls[0][0]).not.toMatch(/password|private|token=/);
    });

    it("copies a bounded service-computer HTTP check without credentials or query values", async () => {
        const writeText = vi.fn().mockResolvedValue(undefined);
        Object.defineProperty(navigator, "clipboard", {
            configurable: true,
            value: { writeText },
        });
        show({ health: { data: { services: { iFileshare: {
            status: "unavailable",
            details: { url: "http://operator:password@10.10.60.30:8080/health?token=private" },
        } } } } });
        const checks = within(screen.getByRole("region", { name: "Service checks" }));
        fireEvent.click(checks.getByText("Check iFileshare on the computer where it runs"));
        const command = checks.getByRole("group", { name: "Service computer HTTP check command" });

        fireEvent.click(within(command).getByRole("button", { name: "Copy command" }));

        expect(await within(command).findByRole("status")).toHaveTextContent("Command copied.");
        expect(writeText).toHaveBeenCalledWith("curl --silent --show-error --output /dev/null --write-out 'HTTP %{http_code}\\n' --connect-timeout 2 --max-time 5 -- 'http://10.10.60.30:8080/health'");
        expect(writeText.mock.calls[0][0]).not.toMatch(/operator|password|private|token=/);
    });

    it("copies the read-only command for finding the Atlas Core container", async () => {
        const writeText = vi.fn().mockResolvedValue(undefined);
        Object.defineProperty(navigator, "clipboard", {
            configurable: true,
            value: { writeText },
        });
        show({ health: { data: { services: { iFileshare: {
            status: "unavailable",
            details: { url: "http://10.10.60.30:8080/" },
        } } } } });
        const checks = within(screen.getByRole("region", { name: "Service checks" }));
        fireEvent.click(checks.getByText("Test the connection from Atlas Core to iFileshare"));
        const command = checks.getByRole("group", { name: "Atlas container status command" });

        fireEvent.click(within(command).getByRole("button", { name: "Copy command" }));

        expect(await within(command).findByRole("status")).toHaveTextContent("Command copied.");
        expect(writeText).toHaveBeenCalledWith("docker ps --all --format 'table {{.Names}}\\t{{.Image}}\\t{{.Status}}\\t{{.Networks}}\\t{{.Ports}}'");
    });

    it("explains how to copy the command when clipboard access is unavailable", async () => {
        const writeText = vi.fn().mockRejectedValue(new Error("clipboard unavailable"));
        Object.defineProperty(navigator, "clipboard", {
            configurable: true,
            value: { writeText },
        });
        show({ health: { data: { services: { iFileshare: {
            status: "unavailable",
            details: { url: "http://10.10.60.30:8080/" },
        } } } } });
        const checks = within(screen.getByRole("region", { name: "Service checks" }));
        fireEvent.click(checks.getByText("Test the connection from Atlas Core to iFileshare"));
        const command = checks.getByRole("group", { name: "Read-only Core connection check command" });

        fireEvent.click(within(command).getByRole("button", { name: "Copy command" }));

        expect(await within(command).findByRole("status")).toHaveTextContent("Copy unavailable. Select and copy the command above.");
    });

    it("copies the detailed Docker status command for the service computer", async () => {
        const writeText = vi.fn().mockResolvedValue(undefined);
        Object.defineProperty(navigator, "clipboard", {
            configurable: true,
            value: { writeText },
        });
        show({ health: { data: { services: { iFileshare: {
            status: "healthy",
            details: { url: "http://10.10.60.30:8080/" },
        } } } } });
        const checks = within(screen.getByRole("region", { name: "Service checks" }));
        fireEvent.click(checks.getByText("Check iFileshare on the computer where it runs"));
        fireEvent.click(checks.getByText("If the app runs in Docker"));
        const firstStep = within(checks.getByRole("list", { name: "Docker and Compose checks" })).getAllByRole("listitem")[0];

        fireEvent.click(within(firstStep).getByRole("button", { name: "Copy command" }));

        expect(await within(firstStep).findByRole("status")).toHaveTextContent("Command copied.");
        expect(writeText).toHaveBeenCalledWith("docker ps --all --format 'table {{.Names}}\\t{{.Image}}\\t{{.Status}}\\t{{.Networks}}\\t{{.Ports}}'");
    });

    it("keeps the Core connection wording in stale service-check evidence", () => {
        show({ health: { stale: true, data: { services: { iFileshare: {
            status: "offline",
            message: "Connection refused",
        } } } } });
        const checks = within(screen.getByRole("region", { name: "Service checks" }));

        expect(checks.getByText("Status unknown")).toBeInTheDocument();
        expect(checks.getByText("Last known report (out of date): Atlas Core could not connect.")).toBeInTheDocument();
    });

    it.each([
        ["[Errno 111] Connection refused", "On the computer that runs iFileshare, confirm the app is listening. If it runs in Docker, check its network and published ports before changing anything. Then test again from Atlas Core."],
        ["[Errno 113] No route to host", "Check the target address and the network or firewall route from Atlas Core to the service host."],
        ["[Errno 101] Network is unreachable", "Check the target address and routing between Atlas Core and the service host."],
        ["[Errno -3] Temporary failure in name resolution", "Check that the host name is correct and resolves from the machine running Atlas Core."],
        ["[Errno 110] Connection timed out", "Check that the service is responding and that network or firewall rules allow access from Atlas Core."],
    ])("suggests a Core-side next check for %s", (message, nextCheck) => {
        show({ health: { data: { services: { iFileshare: {
            status: "offline",
            message,
            details: { url: "http://10.10.60.30:8080/" },
        } } } } });
        const checks = within(screen.getByRole("region", { name: "Service checks" }));
        const summary = checks.getByText("Check iFileshare on the computer where it runs");
        const disclosure = summary.closest("details");
        fireEvent.click(summary);

        expect(disclosure).toHaveTextContent(`Next check: ${nextCheck}`);
    });

    it("shows the reported HTTP response and response time in service check details", () => {
        show({ health: { data: { services: { iFileshare: {
            status: "degraded",
            http_status: 503,
            latency_ms: 42.4,
            details: { url: "http://10.10.60.30:8080/" },
        } } } } });
        const checks = within(screen.getByRole("region", { name: "Service checks" }));
        expect(checks.queryByRole("group", { name: "Next connection check" })).not.toBeInTheDocument();
        const summary = checks.getByText("Check iFileshare on the computer where it runs");
        const disclosure = summary.closest("details");
        fireEvent.click(summary);

        expect(disclosure).toHaveTextContent("HTTP response: 503");
        expect(disclosure).toHaveTextContent("Response time: 42 ms");
    });

    it('keeps the workflow action and approval stage on separate lines without repeating the result', () => {
        show({ workflows: { data: { items: [{
            workflow_id: 'review-me', workflow_state: 'awaiting_implementation_approval',
            execution_intent: 'update-compose-stack', last_result_summary: 'Waiting for implementation approval', timeline: [],
        }], total: 1, limit: 200, offset: 0 } } });
        const attention = within(screen.getByRole('region', { name: 'Needs attention' }));
        expect(attention.getByRole('link', { name: 'Update Compose Stack' })).toBeVisible();
        expect(attention.getByText('Action needed: Review the change. If approved, choose Run approved change.')).toBeVisible();
        expect(attention.queryByText('Waiting for implementation approval', { exact: true })).not.toBeInTheDocument();
        expect(attention.queryByText('Human action required', { exact: true })).not.toBeInTheDocument();
        expect(attention.queryByText('Review each item and use its link to see the details.')).not.toBeInTheDocument();
    });

    it('explains stale approval evidence in plain language', () => {
        show({ workflows: { stale: true, unavailable: true, data: { items: [{ workflow_id: 'old-review', workflow_state: 'awaiting_implementation_approval', last_result_summary: 'Previous review request', timeline: [] }], total: 1, limit: 200, offset: 0 } } });
        const attention = within(screen.getByRole('region', { name: 'Needs attention' }));
        expect(attention.getByText('Last report: this workflow was waiting for change approval. Atlas could not confirm whether it still needs attention.')).toBeVisible();
        expect(attention.getByRole('link', { name: 'Workflow' })).toBeVisible();
        expect(attention.queryByRole('link', { name: /Last known/ })).not.toBeInTheDocument();
        expect(attention.queryByText('Human action required', { exact: true })).not.toBeInTheDocument();
        expect(attention.queryByText('Degraded', { exact: true })).not.toBeInTheDocument();
    });

    it('does not repeat the stale warning for a blocked workflow', () => {
        show({ workflows: { stale: true, unavailable: true, data: { items: [{ workflow_id: 'old-blocked', workflow_state: 'blocked', last_result_summary: 'Previous failure', timeline: [] }], total: 1, limit: 200, offset: 0 } } });
        const attention = within(screen.getByRole('region', { name: 'Needs attention' }));
        expect(attention.getByRole('link', { name: 'Workflow' })).toBeVisible();
        expect(attention.getByText('Last report: this workflow was blocked. Atlas could not confirm its current status.')).toBeVisible();
        expect(attention.queryByText(/Last-known|current state unknown/)).not.toBeInTheDocument();
    });

    it.each([['healthy','healthy'], ['online','healthy'], ['warning','degraded'], ['critical','degraded'], ['offline','unavailable'], ['blocked','blocked'], ['idle','unknown'], ['executing','unknown'], [null,'unknown'], [{},'unknown'], [true,'unknown']])("maps %s without granting authority", (input, expected) => expect(status(input)).toBe(expected));
    it("keeps all six cards and unknown evidence visible", () => {
        show();
        for (const name of ['System health','Service checks','Work activity','Agent details','AI provider','Providers','Needs attention','Recent provider actions']) expect(screen.getByRole('region', { name })).toBeInTheDocument();
        expect(screen.queryByText('Healthy')).not.toBeInTheDocument();
        expect(screen.getByTestId('overview-grid')).toHaveClass('grid-cols-1', 'md:grid-cols-2', 'xl:grid-cols-3');
        expect(screen.getByText("Couldn't load all workflows, so the execution and blocked counts aren't shown.")).toBeInTheDocument();
    });
    it('keeps health source limitations available without crowding the dashboard scan', () => {
        show({ health: { data: { atlas: 'healthy', services: { api: { status: 'healthy' } } } } });
        const health = within(screen.getByRole('region', { name: 'System health' }));
        const report = health.getByRole('article', { name: 'Atlas Core health' });
        const guidance = health.getByText('How to read health');
        expect(report).toBeVisible();
        expect(report.compareDocumentPosition(guidance) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
        expect(health.queryByText(/Each report updates on its own/)).not.toBeVisible();
        fireEvent.click(health.getByText('How to read health'));
        expect(health.getByText(/Each report updates on its own, so check times may differ/)).toBeVisible();
        expect(health.getByText(/doesn't combine them into one score/)).toBeVisible();
        expect(health.getByText(/Reports more than a minute old are marked out of date/)).toBeVisible();

        const checks = within(screen.getByRole('region', { name: 'Service checks' }));
        const explanation = checks.getByText("These checks cover the listed services. For Atlas Core's own health, use the System health card.");
        expect(explanation).not.toBeVisible();
        fireEvent.click(checks.getByText('About service checks'));
        expect(explanation).toBeVisible();
    });
    it('keeps additional health checks under a collapsed health disclosure', () => {
        show();
        const health = within(screen.getByRole('region', { name: 'System health' }));
        const summary = health.getByText('Run additional health checks');
        const disclosure = summary.closest('details') as HTMLDetailsElement;
        expect(disclosure.open).toBe(false);
        const runButton = within(disclosure).getByText('Run health checks').closest('button') as HTMLButtonElement;
        expect(runButton).not.toBeVisible();
        fireEvent.click(summary);
        expect(disclosure.open).toBe(true);
        expect(runButton).toBeVisible();
    });
    it("describes an empty health report as missing service checks", () => {
        show({ health: { data: { atlas: 'healthy', services: {} } } });
        const message = 'No configured service checks were reported.';
        const serviceChecks = within(screen.getByRole('region', { name: 'Service checks' }));
        const systemHealth = within(screen.getByRole('region', { name: 'System health' }));
        expect(serviceChecks.getByText(message)).toBeVisible();
        expect(systemHealth.queryByText(message)).not.toBeInTheDocument();
        expect(screen.queryByText('Core did not report subsystem health.')).not.toBeInTheDocument();
    });
    it("shows a checking state instead of an empty result during the first load", () => {
        show({}, true);
        const attention = within(screen.getByRole('region', { name: 'Needs attention' }));
        expect(attention.getByText('Checking current information…')).toBeVisible();
        expect(attention.queryByText('The latest reports show no items needing attention.')).not.toBeInTheDocument();
        expect(attention.queryByText('System findings: Evidence unknown.')).not.toBeInTheDocument();
        expect(within(screen.getByRole('region', { name: 'Service checks' })).getByText('Checking configured services…')).toBeVisible();
        expect(activity().getByText('Checking recent provider actions…')).toBeVisible();
        expect(screen.queryByText('No current information is available.')).not.toBeInTheDocument();
    });
    it("describes partial first-load evidence as still checking, not missing", () => {
        show({ summary: { data: { findings: [] } } }, true);

        const attention = within(screen.getByRole('region', { name: 'Needs attention' }));
        expect(attention.getByRole('status')).toHaveTextContent("Checking the latest information. This list may update when more checks finish.");
        expect(attention.queryByText("Some checks aren't available. This list may be incomplete.")).not.toBeInTheDocument();
        expect(attention.queryByText('Checking current information…')).not.toBeInTheDocument();
        expect(attention.queryByText('Which results are missing?')).not.toBeInTheDocument();
    });
    it("reports no attention only after all current sources are checked", () => {
        show({
            summary: { data: { findings: [] } },
            health: { data: { atlas: 'healthy', services: {} } },
            providers: { data: [] },
            ai: { data: { health: { status: 'healthy' } } },
            workflows: { data: { items: [], total: 0, offset: 0, limit: 200 } },
        });
        const attention = within(screen.getByRole('region', { name: 'Needs attention' }));
        expect(attention.getByText('The latest reports show no items needing attention.')).toBeVisible();
        expect(attention.queryByText(/cannot confirm whether attention is needed/)).not.toBeInTheDocument();
    });
    it("keeps attention unknown when health details omit configured service checks", () => {
        show({
            summary: { data: { findings: [] } },
            workflows: { data: { items: [], total: 0, offset: 0, limit: 200 } },
            health: { data: { atlas: 'healthy' } },
            providers: { data: [] },
            ai: { data: { health: { status: 'healthy' } } },
        });
        const attention = within(screen.getByRole('region', { name: 'Needs attention' }));
        expect(attention.getByText("Some checks aren't available. This list may be incomplete.")).toBeVisible();
        expect(attention.getByText('System health: health details are incomplete.')).not.toBeVisible();
        fireEvent.click(attention.getByText('Which results are missing?'));
        expect(attention.getByText('System health: health details are incomplete.')).toBeVisible();
        expect(attention.queryByText('The latest reports show no items needing attention.')).not.toBeInTheDocument();
        const checks = within(screen.getByRole('region', { name: 'Service checks' }));
        expect(checks.getByText('Service check details are unavailable.')).toBeVisible();
    });
    it("does not report missing service checks after the health read fails", () => {
        show({ health: { unavailable: true } });
        const summary = within(screen.getByRole('region', { name: 'System health' }));
        expect(summary.getByText('Current information could not be loaded.')).toBeInTheDocument();
        expect(summary.queryByText('No service checks were reported.')).not.toBeInTheDocument();
    });
    it("does not repeat an incomplete-workflow warning when the source is unavailable", () => {
        show({
            summary: { data: { findings: [] } },
            workflows: { unavailable: true },
            health: { data: { atlas: 'healthy', services: {} } },
            providers: { data: [] },
            ai: { data: { health: { status: 'healthy' } } },
        });
        const attention = within(screen.getByRole('region', { name: 'Needs attention' }));
        expect(attention.getByText("Some checks aren't available. This list may be incomplete.")).toBeVisible();
        expect(attention.getByText('Workflows: current information could not be loaded.')).not.toBeVisible();
        fireEvent.click(attention.getByText('Which results are missing?'));
        expect(attention.getByText('Workflows: current information could not be loaded.')).toBeVisible();
        expect(attention.queryByText('Workflow results are incomplete.')).not.toBeInTheDocument();
    });
    it("warns that other attention may be hidden when a source is missing", () => {
        show({
            workflows: { data: { items: [{ workflow_id: "known", workflow_state: "blocked", last_result_summary: "Needs review", timeline: [] }], total: 1, limit: 200, offset: 0 } },
            health: { unavailable: true },
        });
        const attention = within(screen.getByRole('region', { name: 'Needs attention' }));
        expect(attention.getByRole('link', { name: 'Workflow · Blocked' })).toBeVisible();
        expect(attention.getByText("Some checks aren't available. This list may be incomplete.")).toBeVisible();
    });
    it("handles malformed values without success or a crash", () => {
        show({ health: { data: { atlas: {}, services: { broken: null } } }, providers: { data: [null, { health: { status: 23 } }] }, workflows: { data: { items: [null] } }, ai: { data: { health: { status: [] } } }, activity: { data: { items: [null] } } });
        expect(screen.queryByText('Healthy')).not.toBeInTheDocument();
        expect(screen.getByText('Some provider action records could not be read.')).toBeInTheDocument();
    });
    it("presents reported state, reasons, providers and safe detail links; deduplicates subsystem attention", () => {
        show({ health: { data: { atlas: 'degraded', services: { Beta: { provider_id: 'beta', status: 'offline', message: 'Connection refused' } } } }, providers: { data: [{ id: 'alpha', name: 'Alpha', health: { status: 'healthy' }, secret: 'private-credential' }, { id: 'beta', name: 'Beta', health: { status: 'offline', message: 'Connection refused', details: { token: 'private-credential' } } }] }, workflows: { data: { items: [{ workflow_id: 'w/1', workflow_state: 'blocked', last_result_summary: 'Approval expired' }, { workflow_id: 'w2', workflow_state: 'executing' }] } } });
        expect(screen.getByRole('link', { name: 'View Alpha →' })).toHaveAttribute('href', '/providers/alpha');
        expect(screen.getByRole('link', { name: 'Workflow · Blocked' })).toHaveAttribute('href', '/workflows/w%2F1');
        expect(within(screen.getByRole('region', { name: 'Needs attention' })).getAllByText('Beta')).toHaveLength(1);
        expect(screen.getByText("Couldn't load all workflows, so the execution and blocked counts aren't shown.")).toBeInTheDocument();
        expect(screen.queryByText(/private-credential/)).not.toBeInTheDocument();
    });
    it.each(['healthy','unavailable','unknown'])('shows configured AI %s without asserting locality', (value) => {
        show({ ai: { data: { provider: { id: 'runtime', name: 'Runtime' }, health: { status: value } } } });
        const card = screen.getByRole('region', { name: 'AI provider' });
        const label = value === "unknown" ? "Status unknown" : value[0].toUpperCase() + value.slice(1);
        expect(within(card).getAllByText(label).length).toBeGreaterThan(0);
        expect(within(card).getByText(/Atlas doesn’t report where this provider runs/)).toBeInTheDocument();
    });
    it("marks failed refresh evidence stale and never displays cached health as current", () => {
        show({ health: { data: { atlas: 'healthy' }, stale: true, unavailable: true }, activity: { stale: true, data: { items: [{ id:'a', action_label:'Restart', completed_at:'2020-01-01T00:00:00Z', status:'succeeded' }] } } });
        expect(screen.queryByText('Healthy')).not.toBeInTheDocument();
        expect(screen.getAllByText(/Refresh failed/).length).toBeGreaterThan(0);
        expect(activity().getByText('Results from earlier provider actions. Current health and alerts are shown above.')).toBeVisible();
        expect(activity().queryByText(/Historical evidence/)).not.toBeInTheDocument();
    });
    it("handles empty lists and links to existing routes", () => {
        show({ providers: { data: [] }, activity: { data: { items: [] } }, workflows: { data: { items: [] } } });
        expect(screen.getByText('No providers configured.')).toBeInTheDocument();
        expect(screen.getByText('No recent provider actions recorded.')).toBeInTheDocument();
        for (const [name, href] of [['Review workflows →','/workflows'], ['Open action history →','/operations']]) expect(screen.getByRole('link', { name })).toHaveAttribute('href', href);
        expect(within(screen.getByRole('region', { name: 'Agent details' })).queryByRole('link')).not.toBeInTheDocument();
    });
    it("rejects bad timestamps, unsafe paths and sensitive free text", () => {
        expect(timestamp('bad')).toBeNull();
        expect(timestamp({})).toBeNull();
        expect(detailPath('/providers', '..')).toBeNull();
        expect(detailPath('/providers', '\ud800')).toBeNull();
        for (const value of ['Authorization: Bearer abc', 'api_key=abc', 'https://user:pass@host', 'secret=abc']) expect(safeText(value)).toBe('[Sensitive text withheld]');
    });
});

describe('operational activity and runtime evidence', () => {
    it('shows failed outcomes and their existing audit route while keeping the recorded message optional', () => {
        show({ activity: { data: { items: [{ id: 'audit/1', action_label: 'Inspect resource', status: 'failed', message: 'Provider unavailable', completed_at: 'invalid' }] } }, ai: { data: { models: { running: [{ name: 'model-a' }] }, errors: {} } } });
        const activityCard = activity().getByRole('listitem');
        expect(within(activityCard).getByText('Failed · Inspect resource')).toBeInTheDocument();
        expect(within(activityCard).getByRole('link', { name: 'View action details →' })).toHaveAttribute('href', '/operations/actions/audit%2F1');
        expect(within(activityCard).getByText('Completion time unavailable.')).toBeInTheDocument();
        expect(within(activityCard).getByText('Provider unavailable')).not.toBeVisible();
        fireEvent.click(within(activityCard).getByText('More details'));
        expect(within(activityCard).getByText('Provider unavailable')).toBeVisible();
        expect(screen.getByText('Running models: model-a')).toBeInTheDocument();
        expect(screen.queryByText('Healthy')).not.toBeInTheDocument();
    });
    it('deduplicates an identical finding and provider condition', () => {
        show({ providers: { data: [{ id: 'p', name: 'Provider', health: { status: 'offline', message: 'No connection' } }] }, summary: { data: { findings: [{ id: 'f', source: 'p', title: 'Provider offline', message: 'No connection', severity: 'critical' }] } } });
    const attention = within(screen.getByRole('region', { name: 'Needs attention' }));
    expect(attention.getAllByText('No connection')).toHaveLength(1);
    expect(attention.getByRole('link', { name: 'Provider offline' })).toHaveAttribute('href', '/providers/p');
    });
});

describe('overview fail-closed regressions', () => {
    it.each(['', 'idle', 'future_state', null, {}])('does not count malformed or unsupported workflow states: %s', state => {
        show({ workflows: { data: { items: [{ workflow_id: 'w', workflow_state: state }] } } });
        expect(screen.getByText("Couldn't load all workflows, so the execution and blocked counts aren't shown.")).toBeInTheDocument();
        expect(screen.queryByText(/Active: 0/)).not.toBeInTheDocument();
    });
    it('retains distinct conditions for the same provider and does not call approval waits blocked', () => {
        show({
            health: { data: { services: { API: { provider_id: 'p', status: 'offline', message: 'Endpoint offline' } } } },
            providers: { data: [{ id: 'p', name: 'Provider', health: { status: 'warning', message: 'Capacity limited' } }] },
            workflows: { data: { items: [{ workflow_id: 'w', workflow_state: 'awaiting_approval' }] } },
        });
        const attention = within(screen.getByRole('region', { name: 'Needs attention' }));
        expect(attention.getByText('Endpoint offline')).toBeInTheDocument();
        expect(attention.getByText('Capacity limited')).toBeInTheDocument();
        expect(attention.queryByText('Blocked')).not.toBeInTheDocument();
        expect(attention.getByRole('link', { name: 'Workflow' })).toHaveAttribute('href', '/workflows/w');
        expect(attention.getByText('Action needed: Prepare the change for review.')).toBeVisible();
    });
    it('recognizes review, run-ready, and verification-preparation workflow states', () => {
        const items = [
            { workflow_id: 'planned-workflow', workflow_state: 'planned', execution_intent: 'update-compose-stack', last_result_summary: 'Workflow is ready for review.', timeline: [] },
            { workflow_id: 'ready-workflow', workflow_state: 'awaiting_execution', effect_kind: 'operational_action', execution_intent: 'restart-service', last_result_summary: 'Approved and ready to run', timeline: [] },
            { workflow_id: 'patch-workflow', workflow_state: 'patch_applied_pending_verification', execution_intent: 'update-container-image', last_result_summary: 'Implementation is complete. Verification is next.', timeline: [] },
        ];
        show({ workflows: { data: { items, total: items.length, offset: 0, limit: 200 } } });

        const attention = within(screen.getByRole('region', { name: 'Needs attention' }));
        expect(attention.getByRole('link', { name: 'Update Compose Stack' })).toHaveAttribute('href', '/workflows/planned-workflow');
        expect(attention.getByText('Action needed: Review the workflow before continuing.')).toBeVisible();
        expect(attention.getByRole('link', { name: 'Restart Service' })).toHaveAttribute('href', '/workflows/ready-workflow');
        expect(attention.getByText('Action needed: Maintenance is approved. Choose Run approved maintenance when ready.')).toBeVisible();

        fireEvent.click(attention.getByText('Which results are missing?'));
        expect(attention.queryByText('Workflows: workflow results are incomplete.')).not.toBeInTheDocument();
        const activity = within(screen.getByRole('region', { name: 'Work activity' }));
        expect(activity.getByText('No workflows are running or blocked.')).toBeVisible();
        expect(activity.queryByText('Some workflow statuses are not recognized. Execution and blocked counts are hidden.')).not.toBeInTheDocument();
    });
    it('keeps a malformed provider unknown even in the expanded list', () => {
        show({ providers: { data: [...Array.from({ length: 4 }, (_, i) => ({ id: String(i), name: String(i) })), { health: { status: 'healthy' } }] } });
        expect(screen.queryByText('Healthy')).not.toBeInTheDocument();
    });
    it('does not equate configured provider health with local runtime availability', () => {
        show({ ai: { data: { health: { status: 'healthy' } } } });
        const runtime = within(screen.getByRole('region', { name: 'AI provider' }));
        expect(runtime.getByText('Atlas doesn’t report where this provider runs. Its model list doesn’t show which model Atlas will use or whether it can answer requests.')).toBeVisible();
        expect(runtime.getByText('Configured provider: Not reported')).toBeInTheDocument();
    });
});

it('distinguishes running workflows from verification and commit activity', () => {
    show({ workflows: { data: { total: 3, offset: 0, limit: 200, items: ['executing', 'verifying', 'committing'].map((state, i) => ({ workflow_id: String(i), workflow_state: state, last_result_summary: '', timeline: [] })) } } });
    const activity = within(screen.getByRole('region', { name: 'Work activity' }));
    expect(activity.getAllByText('Running workflows')[0].nextElementSibling).toHaveTextContent('1');
    expect(activity.getByText("Shows workflow progress and results. It doesn't show whether a worker is free to take more work.")).toBeInTheDocument();
});

it('preserves the most urgent duplicate condition at equal freshness', () => {
    show({
        health: { data: { services: { API: { provider_id: 'p', status: 'warning', message: 'Pending recovery' } } } },
        providers: { data: [{ id: 'p', name: 'Provider', health: { status: 'blocked', message: 'Pending recovery' } }] },
    });
    const attention = within(screen.getByRole('region', { name: 'Needs attention' }));
    expect(attention.getAllByText('Pending recovery')).toHaveLength(1);
    expect(attention.getByText('Blocked')).toBeInTheDocument();
});

it('includes configured AI failures in attention without asserting local availability', () => {
    show({ ai: { data: { provider: { id: 'runtime', name: 'Runtime' }, health: { status: 'offline', message: 'Endpoint unavailable' } } } });
    const attention = within(screen.getByRole('region', { name: 'Needs attention' }));
    expect(attention.getByText('Unavailable')).toBeInTheDocument();
    expect(attention.getByRole('link', { name: 'Runtime' })).toHaveAttribute('href', '/providers/runtime');
    expect(attention.getByText('Endpoint unavailable')).toBeInTheDocument();
    expect(screen.getByText(/Atlas doesn’t report where this provider runs/)).toBeInTheDocument();
});

it('routes provider warnings without safe detail ids to their overview cards', () => {
    show({
        providers: { data: [{ id: '../legacy', name: 'Legacy provider', health: { status: 'offline', message: 'Provider connection failed' } }] },
        ai: { data: { provider: { id: '../runtime', name: 'Configured AI' }, health: { status: 'offline', message: 'AI connection failed' } } },
        summary: { data: { findings: [
            { id: 'legacy-finding', source: '../legacy', title: 'Legacy provider', message: 'Provider connection failed', severity: 'critical' },
            { id: 'ai-finding', source: '../runtime', title: 'Configured AI', message: 'AI connection failed', severity: 'critical' },
        ] } },
    });
    const attention = within(screen.getByRole('region', { name: 'Needs attention' }));
    expect(attention.getByRole('link', { name: 'Legacy provider' })).toHaveAttribute('href', '#providers');
    expect(attention.getByRole('link', { name: 'Configured AI' })).toHaveAttribute('href', '#ai-provider');
    expect(screen.getByRole('region', { name: 'Providers' })).toHaveAttribute('id', 'providers');
    expect(screen.getByRole('region', { name: 'AI provider' })).toHaveAttribute('id', 'ai-provider');
});

it('deduplicates configured AI and provider evidence and preserves freshness', () => {
    show({
        ai: { stale: true, data: { provider: { id: 'runtime', name: 'Runtime' }, health: { status: 'blocked', message: 'Endpoint unavailable' } } },
        providers: { data: [{ id: 'runtime', name: 'Runtime', health: { status: 'offline', message: 'Endpoint unavailable' } }] },
    });
    const attention = within(screen.getByRole('region', { name: 'Needs attention' }));
    expect(attention.getAllByText('Endpoint unavailable')).toHaveLength(1);
    expect(attention.getByText('Unavailable')).toBeInTheDocument();
    expect(attention.queryByText('Blocked')).not.toBeInTheDocument();
});

it('keeps stale AI conditions explicitly unknown', () => {
    show({ ai: { stale: true, data: { health: { status: 'offline', message: 'Last connection failed' } } } });
    const attention = within(screen.getByRole('region', { name: 'Needs attention' }));
    expect(attention.getByText('Last known report (out of date): Unavailable.')).toBeInTheDocument();
    expect(attention.queryByText(/Last-known condition|current state unknown/)).not.toBeInTheDocument();
});

it('surfaces incomplete attention evidence and rejects uninspectable activity', () => {
    show({ summary: { data: { findings: [null] } }, workflows: { data: { items: [null] } }, activity: { data: { items: [{ id: '..', action_label: 'Restart', status: 'succeeded' }] } } });
    const attention = within(screen.getByRole('region', { name: 'Needs attention' }));
    expect(attention.getByText("Some checks aren't available. This list may be incomplete.")).toBeVisible();
    expect(attention.getByText('Workflows: workflow results are incomplete.')).not.toBeVisible();
    expect(attention.getByText('System findings: finding details are incomplete.')).not.toBeVisible();
    fireEvent.click(attention.getByText('Which results are missing?'));
    expect(attention.getByText('Workflows: workflow results are incomplete.')).toBeVisible();
    expect(attention.getByText('System findings: finding details are incomplete.')).toBeVisible();
    expect(screen.getByText('Some provider action records could not be read.')).toBeInTheDocument();
    expect(screen.queryByText('Succeeded · Restart')).not.toBeInTheDocument();
});

it('keeps a troubled provider visible ahead of routine healthy providers', () => {
    show({ providers: { data: [...Array.from({ length: 4 }, (_, i) => ({ id: String(i), name: `Healthy ${i}`, health: { status: 'healthy' } })), { id: 'offline', name: 'Offline provider', health: { status: 'offline', message: 'Connection failed' } }] } });
    const card = within(screen.getByRole('region', { name: 'Providers' }));
    expect(card.getByRole('link', { name: 'View Offline provider →' })).toBeInTheDocument();
    expect(card.getByText('Connection failed')).toBeInTheDocument();
});

it('deduplicates an AI condition also reported as an operational finding', () => {
    show({
        ai: { data: { provider: { id: 'runtime', name: 'Runtime' }, health: { status: 'offline', message: 'Connection failed' } } },
        summary: { data: { findings: [{ id: 'f', source: 'runtime', title: 'Runtime offline', message: 'Connection failed', severity: 'critical' }] } },
    });
    const attention = within(screen.getByRole('region', { name: 'Needs attention' }));
    expect(attention.getAllByText('Connection failed')).toHaveLength(1);
    expect(attention.getByRole('link', { name: 'Runtime offline' })).toHaveAttribute('href', '/providers/runtime');
});

it('integrates one health summary with independent source freshness and safe reasons', () => {
    show({
        health: { data: { atlas: 'healthy' } },
        summary: { data: { status: 'healthy', summary: 'token=private-credential', findings: [] }, stale: true, unavailable: true },
        policyHealth: { unavailable: true },
    });
    expect(screen.getAllByRole('region', { name: 'System health' })).toHaveLength(1);
    expect(screen.getByTestId('overview-grid').children).toHaveLength(6);
    const core = within(screen.getByRole('article', { name: 'Atlas Core health' }));
    expect(core.getByText('Healthy')).toBeInTheDocument();
    const ace = within(screen.getByRole('article', { name: 'System findings' }));
    expect(ace.queryByText('Healthy', { exact: true })).not.toBeInTheDocument();
    expect(ace.getByText('Last known report (out of date): Healthy.')).toBeInTheDocument();
    expect(ace.getByText('[Sensitive text withheld]')).toBeInTheDocument();
    expect(screen.queryByText(/private-credential/)).not.toBeInTheDocument();
    const policy = within(screen.getByRole('article', { name: 'Policy settings check' }));
    expect(policy.getByText('Current information could not be loaded.')).toBeInTheDocument();
    expect(policy.queryByText('Unknown')).not.toBeInTheDocument();
});

it('does not promote operational success or malformed summary evidence to health', () => {
    show({ health: { data: { atlas: 'success' } }, summary: { data: { status: {}, summary: [] } }, policyHealth: { data: [] } });
    expect(screen.queryByText('Healthy')).not.toBeInTheDocument();
    expect(within(screen.getByRole('region', { name: 'System health' })).getAllByText('Status unknown')).toHaveLength(3);
});

it('integrates execution outcomes and stale attention without duplicating health or workflow state', () => {
    show({
        health: { data: { atlas: 'healthy' } },
        workflows: { stale: true, unavailable: true, data: { total: 1, offset: 0, limit: 200, items: [{
            workflow_id: 'blocked/1', workflow_state: 'blocked', last_result_summary: 'Commit failed',
            timeline: [{ name: 'Execution', status: 'completed' }],
        }] } },
    });
    const worker = within(screen.getByRole('region', { name: 'Work activity' }));
    fireEvent.click(worker.getByText('More workflow details'));
    expect(worker.getByRole('link', { name: 'Workflow · Execution completed' })).toBeVisible();
    expect(worker.queryByText('Commit failed')).not.toBeInTheDocument();
    expect(worker.queryByText('Healthy')).not.toBeInTheDocument();
    expect(worker.getByText("Atlas couldn't load the latest workflow report. The statuses shown may have changed.")).toBeInTheDocument();
    const attention = within(screen.getByRole('region', { name: 'Needs attention' }));
    expect(attention.getAllByRole('link', { name: 'Workflow' })).toHaveLength(1);
    expect(attention.getByText('Last report: this workflow was blocked. Atlas could not confirm its current status.')).toBeVisible();
    expect(attention.queryByText(/Last-known condition|current state unknown/)).not.toBeInTheDocument();
    expect(screen.getAllByRole('region', { name: 'System health' })).toHaveLength(1);
    expect(screen.getByTestId('overview-grid').children).toHaveLength(6);
});
