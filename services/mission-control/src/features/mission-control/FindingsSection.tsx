import { FindingCard } from "../../components/FindingCard";
import { SectionHeader } from "../../components/SectionHeader";
import type { AceFinding } from "../../types/ace";

type FindingsSectionProps = {
    findings: AceFinding[];
};

const severityOrder: Record<string, number> = {
    critical: 0,
    warning: 1,
    info: 2,
};

export function FindingsSection({
    findings,
}: FindingsSectionProps) {
    if (findings.length === 0) {
        return null;
    }

    const sortedFindings = [...findings].sort((first, second) => {
        const severityDifference =
            (severityOrder[first.severity.toLowerCase()] ?? 99) -
            (severityOrder[second.severity.toLowerCase()] ?? 99);

        if (severityDifference !== 0) {
            return severityDifference;
        }

        return first.title.localeCompare(second.title);
    });

    return (
        <section>
            <SectionHeader
                title="Recent Findings"
                description="Evidence collected and evaluated by the Atlas Cognitive Engine."
            />

            <div className="grid gap-4 xl:grid-cols-2">
                {sortedFindings.map((finding) => (
                    <div
                        key={finding.id}
                        className={
                            Array.isArray(
                                finding.details.unavailable_entities,
                            )
                                ? "xl:col-span-2"
                                : ""
                        }
                    >
                        <FindingCard finding={finding} />
                    </div>
                ))}
            </div>
        </section>
    );
}
