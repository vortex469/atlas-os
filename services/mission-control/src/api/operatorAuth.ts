import { atlas } from "./atlas";
import type {
    OperatorSessionResponse,
    OperatorSessionResult,
} from "../types/operatorAuth";

const CSRF_HEADER = "x-atlas-csrf-token";

export class OperatorSessionProtectionError extends Error {}

function sessionResult(
    session: OperatorSessionResponse,
    headers: Record<string, unknown>,
): OperatorSessionResult {
    const csrfToken = headers[CSRF_HEADER];
    if (typeof csrfToken !== "string" || csrfToken.length === 0) {
        throw new OperatorSessionProtectionError(
            "Operator session response did not include CSRF protection.",
        );
    }
    return { session, csrfToken };
}

export async function loginOperator(
    operatorId: string,
    password: string,
): Promise<OperatorSessionResult> {
    const response = await atlas.post<OperatorSessionResponse>(
        "/operator-auth/login",
        { operator_id: operatorId, password },
        { withCredentials: true },
    );
    return sessionResult(response.data, response.headers);
}

export async function restoreOperatorSession(): Promise<OperatorSessionResult> {
    const response = await atlas.get<OperatorSessionResponse>(
        "/operator-auth/session",
        { withCredentials: true },
    );
    return sessionResult(response.data, response.headers);
}

export async function logoutOperator(csrfToken: string): Promise<void> {
    await atlas.post(
        "/operator-auth/logout",
        {},
        {
            withCredentials: true,
            headers: { "X-Atlas-CSRF-Token": csrfToken },
        },
    );
}
