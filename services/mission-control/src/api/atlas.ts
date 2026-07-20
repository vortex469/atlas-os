import axios from "axios";
import { parse } from "yaml";

export const atlas = axios.create({
    baseURL: "/atlas-core",
    timeout: 15000,
});

export async function analyzeCompose(compose: string): Promise<unknown> {
    const response = await atlas.post("/analysis/deployments", {
        source: "compose",
        reference: "forge",
        document: parse(compose),
    });

    return response.data;
}