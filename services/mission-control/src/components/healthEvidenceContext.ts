import { createContext } from "react";

// A failed dashboard refresh retains the previous snapshot, never current success.
export const HealthEvidenceContext = createContext({ stale: false });
