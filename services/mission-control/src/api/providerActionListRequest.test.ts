import { afterEach, expect, it, vi } from "vitest";
import { atlas, getProviderActions } from "./atlas";

const action = { id: "unload-model", label: "Unload Model", description: "Unload a model", icon: "power",
    requires_confirmation: true, destructive: false, enabled: true, parameters: {} };
afterEach(() => vi.restoreAllMocks());
it.each([
    { name: "nonboolean enabled flag", value: [{ ...action, enabled: "false" }] },
    { name: "nonboolean confirmation flag", value: [{ ...action, requires_confirmation: null }] },
    { name: "unreadable parameter description", value: [{ ...action, parameters: { model: { required: true, description: { private: "PRIVATE-ACTION-CANARY" } } } }] },
])("rejects $name at the read boundary", async ({ value }) => {
    vi.spyOn(atlas, "get").mockResolvedValue({ data: value });
    await expect(getProviderActions("ollama")).rejects.toThrow();
});
it("reads only the requested provider action list", async () => {
    const get = vi.spyOn(atlas, "get").mockResolvedValue({ data: [action] });
    expect(await getProviderActions("provider/name")).toEqual([action]);
    expect(get).toHaveBeenCalledExactlyOnceWith("/providers/provider%2Fname/actions");
});
