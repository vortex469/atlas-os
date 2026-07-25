export type PolicySeverity = "info" | "warning" | "critical";

export type AtlasPolicies = {
    proxmox: {
        guests: Record<
            string,
            { expected: "running" | "stopped" }
        >;
    };
    docker: {
        containers: Record<
            string,
            { expected: "running" | "stopped" }
        >;
    };
    homeassistant: {
        ignored_entities: string[];
    };
    opnsense: {
        pending_update_warning_threshold: number | null;
        reboot_required_severity: PolicySeverity;
    };
    frigate: {
        cameras: Record<
            string,
            {
                expected: "active" | "inactive";
                minimum_camera_fps: number;
                minimum_process_fps: number;
            }
        >;
        stalled_camera_severity: PolicySeverity;
    };
    obsidian: {
        minimum_note_count: number;
        stale_after_days: number | null;
        insufficient_notes_severity: PolicySeverity;
        stale_severity: PolicySeverity;
        scan_truncated_severity: PolicySeverity;
    };
    qdrant: {
        expected_collections: string[];
        missing_collection_severity: PolicySeverity;
        empty_instance_severity: PolicySeverity;
    };
    n8n: {
        expected_active_workflows: string[];
        inactive_workflow_severity: PolicySeverity;
        scan_truncated_severity: PolicySeverity;
        empty_instance_severity: PolicySeverity;
    };
    intelligence: {
        providers: Record<
            string,
            {
                maximum_collection_duration_ms: number;
                severity: PolicySeverity;
            }
        >;
    };
};

export type PolicyReloadHealth = {
    status: "healthy" | "degraded";
    source_exists: boolean;
    checked_at: string;
    loaded_at: string | null;
    duration_ms: number;
    error: string | null;
    diagnostics: PolicyValidationDiagnostic[];
};

export type PolicyValidationDiagnostic = {
    path: string;
    error_type: string;
    message: string;
    line: number | null;
    column: number | null;
};
