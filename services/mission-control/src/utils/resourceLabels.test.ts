import { describe, expect, it } from "vitest";

import { formatProviderLabel, formatResourceReference, formatResourceTargetLabel, formatResourceTypeLabel } from "./resourceLabels";

describe("plain-language resource labels", () => {
    it("names common provider resource types", () => {
        expect(formatResourceTypeLabel("qemu")).toBe("Virtual machine");
        expect(formatResourceTypeLabel("lxc")).toBe("Container");
        expect(formatResourceTypeLabel("docker_container")).toBe("Docker Container");
        expect(formatResourceTypeLabel("unknown")).toBe("Resource");
    });

    it("uses familiar provider names and keeps other identifiers readable", () => {
        expect(formatProviderLabel("proxmox")).toBe("Proxmox");
        expect(formatProviderLabel("homeassistant")).toBe("Home Assistant");
        expect(formatProviderLabel("custom_provider")).toBe("Custom Provider");
        expect(formatProviderLabel("constructor")).toBe("Constructor");
    });

    it("builds readable target names and preserves exact references separately", () => {
        expect(formatResourceTargetLabel("proxmox", "qemu", "110")).toBe("Proxmox virtual machine 110");
        expect(formatResourceReference("proxmox", "qemu", "110")).toBe("proxmox/qemu/110");
    });
});
