import { createContext, useContext } from "react";

import type { OperatorPrincipal } from "../types/operatorAuth";

export type OperatorSessionContextValue = {
    authenticated: boolean;
    principal: OperatorPrincipal | null;
    csrfToken: string | null;
    loading: boolean;
    error: string | null;
    login: (operatorId: string, password: string) => Promise<boolean>;
    logout: () => Promise<void>;
    invalidate: () => void;
};

export const OperatorSessionContext = createContext<OperatorSessionContextValue | null>(null);

export function useOperatorSession(): OperatorSessionContextValue {
    const value = useContext(OperatorSessionContext);
    if (value === null) {
        throw new Error("useOperatorSession must be used within OperatorSessionProvider.");
    }
    return value;
}
