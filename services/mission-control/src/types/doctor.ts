export type DoctorStatus = "healthy" | "degraded" | "critical";

export type DoctorCheck = {
    name: string;
    passed: boolean;
    error: string | null;
};

export type DoctorReport = {
    status: DoctorStatus;
    score: number;
    checked_at: string;
    configuration_ok: boolean;
    checks: DoctorCheck[];
    critical: string[];
    warnings: string[];
    information: string[];
};
