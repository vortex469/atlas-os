import { fireEvent, render, screen, within } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";
import { Overview } from "./MissionControl";
import { safeText, timestamp, status, detailPath } from "./overviewEvidence";
import type { OverviewEvidence } from "./useOverviewEvidence";
const show = (evidence: OverviewEvidence = {}, loading = false) => render(<MemoryRouter><Overview evidence={evidence} loading={loading} /></MemoryRouter>);
const activity = () => within(screen.getByRole('region', { name: 'Recent provider actions' }));

describe("MC overview evidence", () => {
    it.each(['awaiting_implementation_approval', 'awaiting_verification_approval', 'awaiting_commit_approval'])("shows %s as a workflow decision rather than degraded health", workflow_state => {
        show({ workflows: { data: { items: [{ workflow_id: 'review-me', workflow_state, last_result_summary: 'Review the exact request', timeline: [] }], total: 1, limit: 200, offset: 0 } } });
        const attention = within(screen.getByRole('region', { name: 'Operator Attention' }));
        const expectedStage = workflow_state === 'awaiting_implementation_approval'
            ? 'Waiting for implementation approval'
            : workflow_state === 'awaiting_verification_approval'
                ? 'Waiting for verification approval'
                : 'Waiting for commit approval';
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
        const attention = within(screen.getByRole('region', { name: 'Operator Attention' }));
        expect(attention.getByRole('link', { name: 'Restart Service' })).toHaveAttribute('href', '/workflows/maintenance-review');
        expect(attention.getByText('Action needed: Waiting for maintenance request approval')).toBeVisible();
        expect(attention.queryByText('Action needed: Waiting for implementation approval')).not.toBeInTheDocument();
        expect(attention.queryByText('Waiting for implementation approval', { exact: true })).not.toBeInTheDocument();
    });

    it("keeps stale maintenance approval wording last-known", () => {
        show({ workflows: { stale: true, unavailable: true, data: { items: [{
            workflow_id: 'old-maintenance-review', workflow_state: 'awaiting_implementation_approval',
            effect_kind: 'operational_action', execution_intent: 'restart-service',
            last_result_summary: 'Waiting for implementation approval', timeline: [],
        }], total: 1, limit: 200, offset: 0 } } });
        const attention = within(screen.getByRole('region', { name: 'Operator Attention' }));
        expect(attention.getByText('Last-known status: Waiting for maintenance request approval. Current status unknown.')).toBeVisible();
        expect(attention.queryByText('Waiting for implementation approval', { exact: true })).not.toBeInTheDocument();
    });

    it('names a workflow attention item by its proposed action and keeps its ID in technical details', () => {
        show({ workflows: { data: { items: [{
            workflow_id: 'workflow-123', workflow_state: 'awaiting_verification_approval',
            execution_intent: 'update-compose-stack', last_result_summary: 'Review the exact verification', timeline: [],
        }], total: 1, limit: 200, offset: 0 } } });
        const attention = within(screen.getByRole('region', { name: 'Operator Attention' }));
        expect(attention.getByRole('link', { name: 'Update Compose Stack' })).toHaveAttribute('href', '/workflows/workflow-123');
        expect(attention.getByText('Action needed: Waiting for verification approval')).toBeVisible();
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
        const attention = within(screen.getByRole('region', { name: 'Operator Attention' }));
        expect(attention.getByRole('link', { name: 'Workflow' })).toHaveAttribute('href', '/workflows/review-me');
        expect(attention.getByText('Action needed: Waiting for implementation approval')).toBeVisible();
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

        const attention = within(screen.getByRole('region', { name: 'Operator Attention' }));
        const attentionList = attention.getByRole('list', { name: 'Reported attention conditions' });
        const visibleItems = within(attentionList).getAllByRole('listitem');
        expect(visibleItems).toHaveLength(5);
        expect(within(visibleItems[0]).getByRole('link')).toHaveTextContent('blocked');
        expect(within(visibleItems[1]).getByRole('link', { name: 'Critical condition' })).toBeVisible();
        expect(within(visibleItems[2]).getByRole('link', {
            name: 'Update Compose Stack',
        })).toBeVisible();
        const expand = attention.getByRole('button', { name: 'Show all 9 attention items' });
        expect(expand).toHaveAttribute('aria-expanded', 'false');
        fireEvent.click(expand);
        expect(within(attentionList).getAllByRole('listitem')).toHaveLength(9);
        expect(attention.getByRole('link', { name: 'service-5' })).toBeVisible();
        const collapse = attention.getByRole('button', { name: 'Show fewer conditions' });
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
        expect(checks.getAllByRole('listitem')).toHaveLength(4);
        expect(checks.queryByText('service-5')).not.toBeInTheDocument();

        const expand = checks.getByRole('button', { name: 'Show all 6 service checks' });
        expect(expand).toHaveAttribute('aria-expanded', 'false');
        fireEvent.click(expand);
        expect(checks.getAllByRole('listitem')).toHaveLength(6);
        expect(checks.getByText('service-5')).toBeVisible();

        const collapse = checks.getByRole('button', { name: 'Show fewer service checks' });
        expect(collapse).toHaveAttribute('aria-expanded', 'true');
        fireEvent.click(collapse);
        expect(checks.getAllByRole('listitem')).toHaveLength(4);
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
        const visibleNames = checks.getAllByRole("listitem")
            .map(item => item.querySelector("p")?.textContent);

        expect(visibleNames).toEqual(["Blocked", "Offline", "Degraded", "Unknown"]);
        expect(checks.queryByText("Healthy", { exact: true })).not.toBeInTheDocument();
    });

    it("shows the Core-side check location on demand without exposing URL secrets", () => {
        show({ health: { data: { atlas: "degraded", services: { iFileshare: {
            status: "offline",
            message: "No route to host",
            details: { url: "http://operator:password@10.10.60.30:8080/?token=private" },
        } } } } });
        const checks = within(screen.getByRole("region", { name: "Service checks" }));
        const location = checks.getByText("Where Atlas checked");
        const disclosure = location.closest("details");

        expect(disclosure).not.toHaveAttribute("open");
        fireEvent.click(location);

        expect(disclosure).toHaveTextContent("http://10.10.60.30:8080/?…");
        expect(disclosure).toHaveTextContent("Run a reachability test on the Atlas host.");
        expect(disclosure).toHaveTextContent("use the Compose file on that host to run the test inside the atlas-core container.");
        expect(disclosure).toHaveTextContent("A test from the service host, browser, or another machine checks a different network path.");
        expect(disclosure).toHaveTextContent("A Docker container marked “Up” can still be unreachable.");
        expect(disclosure).toHaveTextContent("Check that the app listens on its configured port and that its Docker network or published port lets Atlas Core reach it.");
        expect(disclosure).toHaveTextContent("HTTP response: No response received");
        expect(disclosure).toHaveTextContent("Next check: Check the target address and the network or firewall route from Atlas Core to the service host.");
        expect(disclosure).not.toHaveTextContent(/password|private/);
    });

    it("keeps the Core connection wording in stale service-check evidence", () => {
        show({ health: { stale: true, data: { services: { iFileshare: {
            status: "offline",
            message: "Connection refused",
        } } } } });
        const checks = within(screen.getByRole("region", { name: "Service checks" }));

        expect(checks.getByText("Status unknown")).toBeInTheDocument();
        expect(checks.getByText("Last report: Atlas Core could not connect.")).toBeInTheDocument();
    });

    it.each([
        ["[Errno 111] Connection refused", "Check that the service is listening on this port and that Atlas Core can reach it."],
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
        const location = checks.getByText("Where Atlas checked");
        const disclosure = location.closest("details");
        fireEvent.click(location);

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
        const location = checks.getByText("Where Atlas checked");
        const disclosure = location.closest("details");
        fireEvent.click(location);

        expect(disclosure).toHaveTextContent("HTTP response: 503");
        expect(disclosure).toHaveTextContent("Response time: 42 ms");
    });

    it('keeps the workflow action and approval stage on separate lines without repeating the result', () => {
        show({ workflows: { data: { items: [{
            workflow_id: 'review-me', workflow_state: 'awaiting_implementation_approval',
            execution_intent: 'update-compose-stack', last_result_summary: 'Waiting for implementation approval', timeline: [],
        }], total: 1, limit: 200, offset: 0 } } });
        const attention = within(screen.getByRole('region', { name: 'Operator Attention' }));
        expect(attention.getByRole('link', { name: 'Update Compose Stack' })).toBeVisible();
        expect(attention.getByText('Action needed: Waiting for implementation approval')).toBeVisible();
        expect(attention.queryByText('Waiting for implementation approval', { exact: true })).not.toBeInTheDocument();
        expect(attention.queryByText('Human action required', { exact: true })).not.toBeInTheDocument();
        expect(attention.queryByText('Review each item and use its link to see the details.')).not.toBeInTheDocument();
    });

    it('keeps a stale approval requirement explicitly last-known', () => {
        show({ workflows: { stale: true, unavailable: true, data: { items: [{ workflow_id: 'old-review', workflow_state: 'awaiting_implementation_approval', last_result_summary: 'Previous review request', timeline: [] }], total: 1, limit: 200, offset: 0 } } });
        const attention = within(screen.getByRole('region', { name: 'Operator Attention' }));
        expect(attention.getByText('Last-known status: Waiting for implementation approval. Current status unknown.')).toBeVisible();
        expect(attention.getByRole('link', { name: 'Last known · Workflow' })).toBeVisible();
        expect(attention.queryByText('Human action required', { exact: true })).not.toBeInTheDocument();
        expect(attention.queryByText('Degraded', { exact: true })).not.toBeInTheDocument();
    });

    it('does not repeat the stale warning for a blocked workflow', () => {
        show({ workflows: { stale: true, unavailable: true, data: { items: [{ workflow_id: 'old-blocked', workflow_state: 'blocked', last_result_summary: 'Previous failure', timeline: [] }], total: 1, limit: 200, offset: 0 } } });
        const attention = within(screen.getByRole('region', { name: 'Operator Attention' }));
        expect(attention.getByText('Last-known workflow blocked; current state unknown.')).toBeVisible();
        expect(attention.queryByText('Last-known condition; current state unknown.')).not.toBeInTheDocument();
    });

    it.each([['healthy','healthy'], ['online','healthy'], ['warning','degraded'], ['critical','degraded'], ['offline','unavailable'], ['blocked','blocked'], ['idle','unknown'], ['executing','unknown'], [null,'unknown'], [{},'unknown'], [true,'unknown']])("maps %s without granting authority", (input, expected) => expect(status(input)).toBe(expected));
    it("keeps all six cards and unknown evidence visible", () => {
        show();
        for (const name of ['System health','Service checks','Work activity','Agent details','AI provider','Providers','Operator Attention','Recent provider actions']) expect(screen.getByRole('region', { name })).toBeInTheDocument();
        expect(screen.queryByText('Healthy')).not.toBeInTheDocument();
        expect(screen.getByTestId('overview-grid')).toHaveClass('grid-cols-1', 'md:grid-cols-2', 'xl:grid-cols-3');
        expect(screen.getByText("Could not confirm the full workflow list, so running and blocked counts are hidden.")).toBeInTheDocument();
    });
    it('keeps health source limitations available without crowding the dashboard scan', () => {
        show({ health: { data: { atlas: 'healthy', services: { api: { status: 'healthy' } } } } });
        const health = within(screen.getByRole('region', { name: 'System health' }));
        const report = health.getByRole('article', { name: 'Overall service status' });
        const guidance = health.getByText('How to read health');
        expect(report).toBeVisible();
        expect(report.compareDocumentPosition(guidance) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
        expect(health.queryByText(/overall check time/)).not.toBeVisible();
        fireEvent.click(health.getByText('How to read health'));
        expect(health.getByText(/Core does not supply an overall check time/)).toBeVisible();
        expect(health.getByText(/does not calculate one overall score/)).toBeVisible();

        const checks = within(screen.getByRole('region', { name: 'Service checks' }));
        const coreLimit = checks.getByText(/do not measure Atlas Core’s own process health/);
        expect(coreLimit).not.toBeVisible();
        fireEvent.click(checks.getByText('About service checks'));
        expect(coreLimit).toBeVisible();
    });
    it('keeps Atlas Doctor under a collapsed health disclosure', () => {
        show();
        const health = within(screen.getByRole('region', { name: 'System health' }));
        const summary = health.getByText('Use Atlas Doctor');
        const disclosure = summary.closest('details') as HTMLDetailsElement;
        expect(disclosure.open).toBe(false);
        const runButton = within(disclosure).getByText('Run Doctor').closest('button') as HTMLButtonElement;
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
        const attention = within(screen.getByRole('region', { name: 'Operator Attention' }));
        expect(attention.getByText('Checking current information…')).toBeVisible();
        expect(attention.queryByText('The current reports show no items needing attention.')).not.toBeInTheDocument();
        expect(attention.queryByText('System findings: Evidence unknown.')).not.toBeInTheDocument();
        expect(within(screen.getByRole('region', { name: 'Service checks' })).getByText('Checking configured services…')).toBeVisible();
        expect(activity().getByText('Checking recent provider actions…')).toBeVisible();
        expect(screen.queryByText('No current information is available.')).not.toBeInTheDocument();
    });
    it("describes partial first-load evidence as still checking, not missing", () => {
        show({ summary: { data: { findings: [] } } }, true);

        const attention = within(screen.getByRole('region', { name: 'Operator Attention' }));
        expect(attention.getByRole('status')).toHaveTextContent("Checking current reports. The attention list may change when the remaining checks finish.");
        expect(attention.queryByText('Some information is missing. Atlas cannot confirm this list includes everything that needs attention.')).not.toBeInTheDocument();
        expect(attention.queryByText('Checking current information…')).not.toBeInTheDocument();
        expect(attention.queryByText('Source status')).not.toBeInTheDocument();
    });
    it("reports no attention only after all current sources are checked", () => {
        show({
            summary: { data: { findings: [] } },
            health: { data: { atlas: 'healthy', services: {} } },
            providers: { data: [] },
            ai: { data: { health: { status: 'healthy' } } },
            workflows: { data: { items: [], total: 0, offset: 0, limit: 200 } },
        });
        const attention = within(screen.getByRole('region', { name: 'Operator Attention' }));
        expect(attention.getByText('The current reports show no items needing attention.')).toBeVisible();
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
        const attention = within(screen.getByRole('region', { name: 'Operator Attention' }));
        expect(attention.getByText('Some information is missing. Atlas cannot confirm this list includes everything that needs attention.')).toBeVisible();
        expect(attention.getByText('System health: health details are incomplete.')).not.toBeVisible();
        fireEvent.click(attention.getByText('Source status'));
        expect(attention.getByText('System health: health details are incomplete.')).toBeVisible();
        expect(attention.queryByText('The current reports show no items needing attention.')).not.toBeInTheDocument();
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
        const attention = within(screen.getByRole('region', { name: 'Operator Attention' }));
        expect(attention.getByText('Some information is missing. Atlas cannot confirm this list includes everything that needs attention.')).toBeVisible();
        expect(attention.getByText('Workflows: current information could not be loaded.')).not.toBeVisible();
        fireEvent.click(attention.getByText('Source status'));
        expect(attention.getByText('Workflows: current information could not be loaded.')).toBeVisible();
        expect(attention.queryByText('Workflow results are incomplete.')).not.toBeInTheDocument();
    });
    it("warns that other attention may be hidden when a source is missing", () => {
        show({
            workflows: { data: { items: [{ workflow_id: "known", workflow_state: "blocked", last_result_summary: "Needs review", timeline: [] }], total: 1, limit: 200, offset: 0 } },
            health: { unavailable: true },
        });
        const attention = within(screen.getByRole('region', { name: 'Operator Attention' }));
        expect(attention.getByRole('link', { name: 'Workflow · Blocked' })).toBeVisible();
        expect(attention.getByText('Some information is missing. Atlas cannot confirm this list includes everything that needs attention.')).toBeVisible();
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
        expect(within(screen.getByRole('region', { name: 'Operator Attention' })).getAllByText('Beta')).toHaveLength(1);
        expect(screen.getByText("Could not confirm the full workflow list, so running and blocked counts are hidden.")).toBeInTheDocument();
        expect(screen.queryByText(/private-credential/)).not.toBeInTheDocument();
    });
    it.each(['healthy','unavailable','unknown'])('shows configured AI %s without asserting locality', (value) => {
        show({ ai: { data: { provider: { id: 'runtime', name: 'Runtime' }, health: { status: value } } } });
        const card = screen.getByRole('region', { name: 'AI provider' });
        const label = value === "unknown" ? "Status unknown" : value[0].toUpperCase() + value.slice(1);
        expect(within(card).getAllByText(label).length).toBeGreaterThan(0);
        expect(within(card).getByText(/Atlas does not report where this provider runs/)).toBeInTheDocument();
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
    it('shows failed outcomes and their existing audit route without treating success as health', () => {
        show({ activity: { data: { items: [{ id: 'audit/1', action_label: 'Inspect resource', status: 'failed', message: 'Provider unavailable', completed_at: 'invalid' }] } }, ai: { data: { models: { running: [{ name: 'model-a' }] }, errors: {} } } });
        expect(screen.getByText('Failed · Inspect resource')).toBeInTheDocument();
        expect(screen.getByRole('link', { name: 'Inspect action →' })).toHaveAttribute('href', '/operations/actions/audit%2F1');
        expect(screen.getByText('Completion time unknown.')).toBeInTheDocument();
        expect(screen.getByText('Running models: model-a')).toBeInTheDocument();
        expect(screen.queryByText('Healthy')).not.toBeInTheDocument();
    });
    it('deduplicates an identical finding and provider condition', () => {
        show({ providers: { data: [{ id: 'p', name: 'Provider', health: { status: 'offline', message: 'No connection' } }] }, summary: { data: { findings: [{ id: 'f', source: 'p', title: 'Provider offline', message: 'No connection', severity: 'critical' }] } } });
        expect(within(screen.getByRole('region', { name: 'Operator Attention' })).getAllByText('No connection')).toHaveLength(1);
    });
});

describe('overview fail-closed regressions', () => {
    it.each(['', 'idle', 'future_state', null, {}])('does not count malformed or unsupported workflow states: %s', state => {
        show({ workflows: { data: { items: [{ workflow_id: 'w', workflow_state: state }] } } });
        expect(screen.getByText("Could not confirm the full workflow list, so running and blocked counts are hidden.")).toBeInTheDocument();
        expect(screen.queryByText(/Active: 0/)).not.toBeInTheDocument();
    });
    it('retains distinct conditions for the same provider and does not call approval waits blocked', () => {
        show({
            health: { data: { services: { API: { provider_id: 'p', status: 'offline', message: 'Endpoint offline' } } } },
            providers: { data: [{ id: 'p', name: 'Provider', health: { status: 'warning', message: 'Capacity limited' } }] },
            workflows: { data: { items: [{ workflow_id: 'w', workflow_state: 'awaiting_approval' }] } },
        });
        const attention = within(screen.getByRole('region', { name: 'Operator Attention' }));
        expect(attention.getByText('Endpoint offline')).toBeInTheDocument();
        expect(attention.getByText('Capacity limited')).toBeInTheDocument();
        expect(attention.queryByText('Blocked')).not.toBeInTheDocument();
        expect(attention.getByRole('link', { name: 'Workflow' })).toHaveAttribute('href', '/workflows/w');
        expect(attention.getByText('Action needed: Waiting for approval')).toBeVisible();
    });
    it('keeps a malformed provider unknown even in the expanded list', () => {
        show({ providers: { data: [...Array.from({ length: 4 }, (_, i) => ({ id: String(i), name: String(i) })), { health: { status: 'healthy' } }] } });
        expect(screen.queryByText('Healthy')).not.toBeInTheDocument();
    });
    it('does not equate configured provider health with local runtime availability', () => {
        show({ ai: { data: { health: { status: 'healthy' } } } });
        const runtime = within(screen.getByRole('region', { name: 'AI provider' }));
        expect(runtime.getByText('Atlas does not report where this provider runs or which model is selected or ready to use.')).toBeVisible();
        expect(runtime.getByText('Configured provider: Unknown')).toBeInTheDocument();
    });
});

it('distinguishes running workflows from verification and commit activity', () => {
    show({ workflows: { data: { total: 3, offset: 0, limit: 200, items: ['executing', 'verifying', 'committing'].map((state, i) => ({ workflow_id: String(i), workflow_state: state, last_result_summary: '', timeline: [] })) } } });
    const activity = within(screen.getByRole('region', { name: 'Work activity' }));
    expect(activity.getAllByText('Running workflows')[0].nextElementSibling).toHaveTextContent('1');
    expect(activity.getByText('Atlas does not report whether a worker is available.')).toBeInTheDocument();
});

it('preserves the most urgent duplicate condition at equal freshness', () => {
    show({
        health: { data: { services: { API: { provider_id: 'p', status: 'warning', message: 'Pending recovery' } } } },
        providers: { data: [{ id: 'p', name: 'Provider', health: { status: 'blocked', message: 'Pending recovery' } }] },
    });
    const attention = within(screen.getByRole('region', { name: 'Operator Attention' }));
    expect(attention.getAllByText('Pending recovery')).toHaveLength(1);
    expect(attention.getByText('Blocked')).toBeInTheDocument();
});

it('includes configured AI failures in attention without asserting local availability', () => {
    show({ ai: { data: { provider: { id: 'runtime', name: 'Runtime' }, health: { status: 'offline', message: 'Endpoint unavailable' } } } });
    const attention = within(screen.getByRole('region', { name: 'Operator Attention' }));
    expect(attention.getByText('Unavailable')).toBeInTheDocument();
    expect(attention.getByRole('link', { name: 'Runtime' })).toHaveAttribute('href', '/providers/runtime');
    expect(attention.getByText('Endpoint unavailable')).toBeInTheDocument();
    expect(screen.getByText(/Atlas does not report where this provider runs/)).toBeInTheDocument();
});

it('deduplicates configured AI and provider evidence and preserves freshness', () => {
    show({
        ai: { stale: true, data: { provider: { id: 'runtime', name: 'Runtime' }, health: { status: 'blocked', message: 'Endpoint unavailable' } } },
        providers: { data: [{ id: 'runtime', name: 'Runtime', health: { status: 'offline', message: 'Endpoint unavailable' } }] },
    });
    const attention = within(screen.getByRole('region', { name: 'Operator Attention' }));
    expect(attention.getAllByText('Endpoint unavailable')).toHaveLength(1);
    expect(attention.getByText('Unavailable')).toBeInTheDocument();
    expect(attention.queryByText('Blocked')).not.toBeInTheDocument();
});

it('keeps stale AI conditions explicitly unknown', () => {
    show({ ai: { stale: true, data: { health: { status: 'offline', message: 'Last connection failed' } } } });
    const attention = within(screen.getByRole('region', { name: 'Operator Attention' }));
    expect(attention.getByText('Last report: Unavailable.')).toBeInTheDocument();
    expect(attention.getByText('Last-known condition; current state unknown.')).toBeInTheDocument();
});

it('surfaces incomplete attention evidence and rejects uninspectable activity', () => {
    show({ summary: { data: { findings: [null] } }, workflows: { data: { items: [null] } }, activity: { data: { items: [{ id: '..', action_label: 'Restart', status: 'succeeded' }] } } });
    const attention = within(screen.getByRole('region', { name: 'Operator Attention' }));
    expect(attention.getByText('Some information is missing. Atlas cannot confirm this list includes everything that needs attention.')).toBeVisible();
    expect(attention.getByText('Workflows: workflow results are incomplete.')).not.toBeVisible();
    expect(attention.getByText('System findings: finding details are incomplete.')).not.toBeVisible();
    fireEvent.click(attention.getByText('Source status'));
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
    expect(within(screen.getByRole('region', { name: 'Operator Attention' })).getAllByText('Connection failed')).toHaveLength(1);
});

it('integrates one health summary with independent source freshness and safe reasons', () => {
    show({
        health: { data: { atlas: 'healthy' } },
        summary: { data: { status: 'healthy', summary: 'token=private-credential', findings: [] }, stale: true, unavailable: true },
        policyHealth: { unavailable: true },
    });
    expect(screen.getAllByRole('region', { name: 'System health' })).toHaveLength(1);
    expect(screen.getByTestId('overview-grid').children).toHaveLength(6);
    const core = within(screen.getByRole('article', { name: 'Overall service status' }));
    expect(core.getByText('Healthy')).toBeInTheDocument();
    const ace = within(screen.getByRole('article', { name: 'System findings' }));
    expect(ace.queryByText('Healthy', { exact: true })).not.toBeInTheDocument();
    expect(ace.getByText('Last report: Healthy.')).toBeInTheDocument();
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
    fireEvent.click(worker.getByText('More about execution data'));
    expect(worker.getByRole('link', { name: 'Workflow · Execution completed' })).toBeVisible();
    expect(worker.queryByText('Commit failed')).not.toBeInTheDocument();
    expect(worker.queryByText('Healthy')).not.toBeInTheDocument();
    expect(worker.getByText(/Current status is unknown/)).toBeInTheDocument();
    const attention = within(screen.getByRole('region', { name: 'Operator Attention' }));
    expect(attention.getAllByRole('link', { name: 'Last known · Workflow · Blocked' })).toHaveLength(1);
    expect(attention.getByText('Last-known workflow blocked; current state unknown.')).toBeVisible();
    expect(attention.queryByText('Last-known condition; current state unknown.')).not.toBeInTheDocument();
    expect(screen.getAllByRole('region', { name: 'System health' })).toHaveLength(1);
    expect(screen.getByTestId('overview-grid').children).toHaveLength(6);
});
