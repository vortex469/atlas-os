type PlanningStep = "Execution Candidate" | "Planning Session" | "Candidate Plan" | "Workflow";

const steps: { value: PlanningStep; label: string }[] = [
    { value: "Execution Candidate", label: "Proposal" },
    { value: "Planning Session", label: "Planning" },
    { value: "Candidate Plan", label: "Plan" },
    { value: "Workflow", label: "Workflow" },
];

/** Navigation context only; approval and execution state come from the workflow. */
export function PlanningProgress({ current }: { current: PlanningStep | null }) {
    return <section aria-label="Planning progress" className="rounded-xl border border-slate-800 bg-slate-900/70 p-4">
        <ol className="grid grid-cols-2 gap-2 text-sm sm:grid-cols-4">
            {steps.map((step) => <li key={step.value} aria-current={step.value === current ? "step" : undefined}
                className={`rounded-lg border px-3 py-2 ${step.value === current ? "border-blue-400 bg-blue-500/10 text-blue-200" : "border-slate-800 bg-slate-950/50 text-slate-400"}`}>
                <span className="block font-medium">{step.label}</span>
                {step.value === current && <span className="text-xs">Current step</span>}
            </li>)}
        </ol>
        <p className="mt-3 text-xs text-slate-400">Approval and execution are reviewed in the workflow.</p>
    </section>;
}
