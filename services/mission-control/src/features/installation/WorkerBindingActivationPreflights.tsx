import { useEffect, useState } from "react";

import { listWorkerBindingActivationPreflights } from "../../api/workerBindingActivationPreflight";
import type { FingerprintV1 } from "../../types/installationReadinessReview";
import type { WorkerBindingActivationPreflightV1 } from "../../types/workerBindingActivationPreflight";
import { WorkerBindingActivationEvidences } from "./WorkerBindingActivationEvidences";

const BLOCKERS: Record<string, string> = {
    worker_binding_activation_not_defined: "Worker binding activation is not defined",
    store_contact_not_defined: "Store contact is not defined",
    runtime_contact_not_defined: "Runtime contact is not defined",
    queue_claim_not_defined: "Queue claim is not defined",
    queue_lease_not_defined: "Queue lease is not defined",
    queue_ack_not_defined: "Queue acknowledgement is not defined",
    worker_start_not_defined: "Worker start is not defined",
    agent_invocation_not_defined: "Agent invocation is not defined",
    execution_start_boundary_not_defined: "Execution start boundary is not defined",
};

export function WorkerBindingActivationPreflights({ candidateId, bindingId }: { candidateId: string; bindingId: string }) {
    const [items, setItems] = useState<WorkerBindingActivationPreflightV1[] | null>(null);
    const [error, setError] = useState(false);

    useEffect(() => {
        let current = true;
        listWorkerBindingActivationPreflights(candidateId)
            .then((value) => { if (current) setItems(value.items.filter((item) => item.one_shot_dequeue_worker_binding.binding_id === bindingId)); })
            .catch(() => { if (current) setError(true); });
        return () => { current = false; };
    }, [candidateId, bindingId]);

    return <section className="mt-3 rounded border border-slate-800 p-3" aria-label="Worker binding activation preflight evidence">
        <h6 className="font-semibold">Worker binding activation preflight</h6>
        <p className="mt-2 text-sm">Mission Control shows v0.47 activation preflight evidence inside the existing installation workflow. It is readiness evidence only and does not activate a binding, contact a store or runtime, claim work, lease work, acknowledge work, start a worker, invoke Agent, or start execution.</p>
        <p className="mt-1 text-sm">No activation, store contact, runtime contact, queue claim, queue lease, queue acknowledgement, worker-start, Agent invocation, execution, installation, deployment, rollback, retry, or resend control is available here.</p>
        {items === null && !error && <p role="status" className="mt-3">Loading worker binding activation preflight evidence...</p>}
        {error && <div role="alert" className="mt-3 rounded border border-red-500/40 p-3"><p>Worker binding activation preflight evidence is unavailable.</p><p className="text-xs text-slate-400">The error is redacted; no credential, endpoint, command, payload, queue detail, worker address, store, runtime, broker, log, or internal path is shown.</p></div>}
        {items?.length === 0 && <p role="status" className="mt-3">No worker binding activation preflight evidence has been recorded. Activation, worker start, Agent invocation, and execution remain blocked.</p>}
        {items && items.length > 0 && <ol className="mt-3 space-y-3" aria-label="Worker binding activation preflights">{items.map((item) => <Preflight key={item.preflight_id} item={item} />)}</ol>}
    </section>;
}

function Preflight({ item }: { item: WorkerBindingActivationPreflightV1 }) {
    const binding = item.one_shot_dequeue_worker_binding;
    const worker = binding.worker_intake_admission.worker_identity;
    const intake = binding.worker_intake_admission.worker_intake_reference;
    const limits = binding.worker_intake_admission.inherited_limits;
    return <li className="rounded border border-slate-800 p-3 text-sm">
        <p className="font-semibold">Recorded worker binding activation preflight evidence</p>
        <p className="mt-1">State: eligible for later activation consideration; activation: not defined; blocked: yes. Store contacted: false; runtime contacted: false; queue claimed: false; worker started: false; Agent invoked: false; execution started: false.</p>
        <p className="mt-1">Recorded {item.recorded_at}; valid until {item.valid_until}. Expiry is passive and never activates the binding, contacts a worker, starts execution, or retries delivery.</p>
        <details className="mt-3">
            <summary>Advanced details</summary>
            <dl className="mt-2 grid gap-2 sm:grid-cols-2">
                <Value name="Preflight ID" value={item.preflight_id} />
                <Value name="Authenticated operator" value={item.operator_id} />
                <Value name="Eligibility" value={item.eligibility} />
                <Value name="Lifecycle" value={item.lifecycle} />
                <Value name="Preflight state" value={item.preflight_state} />
                <Value name="Preflight fingerprint" value={item.preflight_record_fingerprint.value} />
                <Value name="Subject fingerprint" value={item.subject_fingerprint.value} />
                <Value name="Idempotency-key fingerprint" value={item.idempotency_key_fingerprint.value} />
                <Value name="v0.46 binding" value={binding.binding_id} />
                <Value name="v0.46 binding fingerprint" value={binding.binding_record_fingerprint.value} />
                <Value name="v0.46 binding status fingerprint" value={item.one_shot_dequeue_worker_binding_status.status_fingerprint.value} />
                <Value name="v0.45 one-shot dequeue" value={binding.one_shot_controlled_dequeue.dequeue_id} />
                <Value name="v0.40 worker intake admission" value={binding.worker_intake_admission.admission_id} />
                <Value name="Binding subject fingerprint" value={item.binding_subject_fingerprint.value} />
                <Value name="Worker subject fingerprint" value={item.worker_subject_fingerprint.value} />
                <Value name="Worker identity ID" value={worker.worker_identity_id} />
                <Value name="Worker kind" value={worker.worker_kind} />
                <Value name="Worker trust domain" value={worker.trust_domain} />
                <Value name="Worker eligibility" value={worker.eligibility} />
                <Value name="Worker capability fingerprint" value={worker.capability_profile_fingerprint.value} />
                <Value name="Worker intake reference" value={intake.worker_intake_reference_id} />
                <Value name="Worker intake protocol" value={intake.intake_protocol} />
                <Value name="Queue item reference fingerprint" value={item.queue_item_reference_fingerprint.value} />
            </dl>
            <h6 className="mt-3 font-semibold">Blockers</h6>
            <ol aria-label="Ordered worker binding activation preflight blockers" className="mt-2 list-decimal pl-5">
                {item.blockers.map((value) => <li key={value}>{BLOCKERS[value] ?? value} <code className="text-xs text-slate-400">{value}</code></li>)}
            </ol>
            <h6 className="mt-3 font-semibold">Inherited sandbox, resource, network, and filesystem limits</h6>
            <dl className="mt-2 grid gap-2 sm:grid-cols-2">
                <Value name="Sandbox profile" value={limits.sandbox.profile} />
                <Value name="Privileged / escalation / host namespaces / devices" value="false" />
                <Value name="CPU ceiling (millis)" value={String(limits.resources.cpu_millis_max)} />
                <Value name="Memory ceiling (bytes)" value={String(limits.resources.memory_bytes_max)} />
                <Value name="PID ceiling" value={String(limits.resources.pids_max)} />
                <Value name="Network mode" value={limits.network.mode} />
                <Value name="Writable scope" value={limits.filesystem.writable_scope} />
                <Value name="Inherited limits fingerprint" value={item.inherited_limits_fingerprint.value} />
            </dl>
            <p className="mt-3 text-xs">Permanent preflight subject reservation: true · permanent idempotency reservation: true · raw idempotency key persisted: false · credential material present: false · endpoint material present: false · command material present: false · payload material present: false.</p>
            <dl aria-label="Worker binding activation preflight fixed-false authority fields" className="mt-3 grid gap-2 sm:grid-cols-2">
                {["Binding activation allowed", "Caller-supplied credentials allowed", "Caller-supplied endpoint allowed", "Caller-supplied command allowed", "Caller-supplied payload allowed", "Store contact allowed", "Runtime contact allowed", "Queue polling allowed", "Queue claim allowed", "Queue lease allowed", "Queue acknowledgement allowed", "Queue consume allowed", "Queue mutation allowed", "Worker store contact allowed", "Worker runtime contact allowed", "Worker contact allowed", "Worker start allowed", "Worker invocation allowed", "Agent invocation allowed", "Execution authorization allowed", "Execution start allowed", "Process execution allowed", "Dispatch allowed", "Retry allowed", "Resend allowed", "Workflow start allowed", "Shell execution allowed", "Provider mutation allowed", "Repository mutation allowed", "In-guest mutation allowed", "Installation allowed", "Deployment allowed", "Rollback allowed", "Artifact publication allowed", "Tag push allowed", "Release publication allowed", "Replay bypass allowed"].map((name) => <Value key={name} name={name} value="false" />)}
            </dl>
        </details>
        <WorkerBindingActivationEvidences candidateId={item.candidate_record_id} preflightId={item.preflight_id} />
    </li>;
}

function display(value: string | FingerprintV1 | undefined) { return typeof value === "object" ? value.value : String(value ?? "Not available"); }
function Value({ name, value }: { name: string; value: string }) { return <div><dt className="break-all text-xs uppercase tracking-wide text-slate-500">{name}</dt><dd className="mt-1 break-all text-slate-300">{display(value)}</dd></div>; }
