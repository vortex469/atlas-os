import { RecommendationCard } from "../../components/RecommendationCard";
import { SectionHeader } from "../../components/SectionHeader";
import type { AceRecommendation } from "../../types/ace";

type RecommendationsSectionProps = {
    recommendations: AceRecommendation[];
};

const priorityOrder: Record<string, number> = {
    critical: 0,
    high: 1,
    medium: 2,
    low: 3,
};

export function RecommendationsSection({
    recommendations,
}: RecommendationsSectionProps) {
    if (recommendations.length === 0) {
        return null;
    }

    const sortedRecommendations = [...recommendations].sort(
        (first, second) =>
            (priorityOrder[first.priority.toLowerCase()] ?? 99) -
            (priorityOrder[second.priority.toLowerCase()] ?? 99),
    );

    return (
        <section>
            <SectionHeader
                title="Recommendations"
                description="Actions ACE recommends based on the current situation report."
            />

            <div className="grid gap-4 lg:grid-cols-2">
                {sortedRecommendations.map((recommendation, index) => (
                    <RecommendationCard
                        key={`${recommendation.component}-${recommendation.title}-${index}`}
                        recommendation={recommendation}
                    />
                ))}
            </div>
        </section>
    );
}
