import { describe, expect, it } from "vitest";

import api from "../api/installationDestination.ts?raw";
import ui from "../features/discovery/ProspectiveDestinationReview.tsx?raw";

describe("prospective destination authority isolation", () => {
    it("uses only frozen installation routes and contains no authority navigation", () => {
        expect(api).not.toMatch(/execution-candidates|workflow|approval|agent|provider.*mutation|dispatch/i);
        expect(ui).not.toMatch(/href=|<Link|navigate\(/);
        expect(api.match(/"\/installation\//g)).toHaveLength(3);
        expect(api).toContain("/installation/destinations");
        expect(api).toContain("/installation/destination-selections");
        expect(api).toContain("/installation/admission-assessments");
    });
});
