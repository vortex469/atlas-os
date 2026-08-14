import {
    useCallback,
    useEffect,
    useMemo,
    useState,
    type ReactNode,
} from "react";
import { isAxiosError } from "axios";

import {
    loginOperator,
    logoutOperator,
    restoreOperatorSession,
} from "../api/operatorAuth";
import type { OperatorPrincipal } from "../types/operatorAuth";
import {
    OperatorSessionContext,
    type OperatorSessionContextValue,
} from "./operatorSessionContext";

export function OperatorSessionProvider({ children }: { children: ReactNode }) {
    const [principal, setPrincipal] = useState<OperatorPrincipal | null>(null);
    const [csrfToken, setCsrfToken] = useState<string | null>(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);

    const invalidate = useCallback(() => {
        setPrincipal(null);
        setCsrfToken(null);
    }, []);

    useEffect(() => {
        let active = true;
        restoreOperatorSession()
            .then((result) => {
                if (!active) return;
                setPrincipal(result.session.principal);
                setCsrfToken(result.csrfToken);
                setError(null);
            })
            .catch((requestError: unknown) => {
                if (!active) return;
                invalidate();
                if (!isAxiosError(requestError) || requestError.response?.status !== 401) {
                    setError("Operator maintenance is currently unavailable.");
                }
            })
            .finally(() => {
                if (active) setLoading(false);
            });
        return () => {
            active = false;
        };
    }, [invalidate]);

    const login = useCallback(async (operatorId: string, password: string) => {
        setError(null);
        try {
            const result = await loginOperator(operatorId, password);
            setPrincipal(result.session.principal);
            setCsrfToken(result.csrfToken);
            return true;
        } catch {
            invalidate();
            setError("Operator authentication failed.");
            return false;
        }
    }, [invalidate]);

    const logout = useCallback(async () => {
        const token = csrfToken;
        invalidate();
        if (token !== null) {
            try {
                await logoutOperator(token);
            } catch {
                setError("Operator logout could not be confirmed.");
            }
        }
    }, [csrfToken, invalidate]);

    const value = useMemo<OperatorSessionContextValue>(() => ({
        authenticated: principal !== null,
        principal,
        csrfToken,
        loading,
        error,
        login,
        logout,
        invalidate,
    }), [principal, csrfToken, loading, error, login, logout, invalidate]);

    return <OperatorSessionContext.Provider value={value}>{children}</OperatorSessionContext.Provider>;
}
