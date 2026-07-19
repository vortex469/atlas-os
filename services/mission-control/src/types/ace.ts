export type FindingSeverity =
    | "info"
    | "warning"
    | "critical"
    | string;

export type RecommendationPriority =
    | "low"
    | "medium"
    | "high"
    | "critical"
    | string;

export type AceFinding = {
    id: string;
    severity: FindingSeverity;
    category: string;
    source: string;
    title: string;
    message: string;
    recommendation: string | null;
    component: string | null;
    metric: Record<string, unknown>;
    details: Record<string, unknown>;
    affects_health: boolean;
    score_penalty: number;
};

export type AceAssessment = {
    title: string;
    priority: string;
    component: string | null;
    details: Record<string, unknown>;
};

export type AceRecommendation = {
    title: string;
    reason: string;
    priority: RecommendationPriority;
    confidence: number;
    estimated_effort: string;
    component: string | null;
};

export type AceSummary = {
    score: number;
    status: string;
    summary: string;
    findings: AceFinding[];
    assessments: AceAssessment[];
    recommendations: AceRecommendation[];
};
