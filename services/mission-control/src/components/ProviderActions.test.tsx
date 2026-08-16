import {
    render,
    screen,
    waitFor,
} from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import {
    getProviderActions,
    runProviderAction,
} from "../api/atlas";
import type { ProviderAction } from "../types/providerAction";
import { ProviderActions } from "./ProviderActions";

vi.mock("../api/atlas", () => ({
    getAtlasErrorMessage: (
        error: unknown,
        fallback: string,
    ) => (error instanceof Error ? error.message : fallback),
    getProviderActions: vi.fn(),
    runProviderAction: vi.fn(),
}));

const mockedGetProviderActions = vi.mocked(
    getProviderActions,
);
const mockedRunProviderAction = vi.mocked(
    runProviderAction,
);

const diagnosticsAction: ProviderAction = {
    id: "run-diagnostics",
    label: "Run Diagnostics",
    description: "Collect current provider diagnostics.",
    icon: "stethoscope",
    requires_confirmation: false,
    destructive: false,
    enabled: true,
    parameters: {},
};

const unloadAction: ProviderAction = {
    id: "unload-model",
    label: "Unload Model",
    description: "Unload a model from memory.",
    icon: "power",
    requires_confirmation: true,
    destructive: false,
    enabled: true,
    parameters: {
        model: {
            type: "string",
            required: true,
            description: "Loaded Ollama model name.",
            example: "gemma4:12b",
        },
    },
};

function renderActions(
    onActionCompleted = vi.fn(),
) {
    render(
        <ProviderActions
            provider={{ id: "ollama", name: "Ollama" }}
            onActionCompleted={onActionCompleted}
        />,
    );

    return onActionCompleted;
}

describe("ProviderActions", () => {
    beforeEach(() => {
        vi.clearAllMocks();
        mockedGetProviderActions.mockResolvedValue([
            diagnosticsAction,
        ]);
    });

    it("runs an action and refreshes provider state", async () => {
        const user = userEvent.setup();
        const onActionCompleted = renderActions();

        mockedRunProviderAction.mockResolvedValue({
            provider_id: "ollama",
            action_id: "run-diagnostics",
            status: "succeeded",
            success: true,
            message: "Diagnostics completed.",
            data: {},
            warnings: [],
        });

        await user.click(
            await screen.findByRole("button", {
                name: "Run Diagnostics",
            }),
        );

        await waitFor(() =>
            expect(mockedRunProviderAction).toHaveBeenCalledWith(
                "ollama",
                "run-diagnostics",
                {
                    confirmed: false,
                    parameters: {},
                },
            ),
        );
        expect(onActionCompleted).toHaveBeenCalledOnce();
        expect(
            screen.getByText("Diagnostics completed."),
        ).toBeInTheDocument();
    });

    it("labels existing provider actions as compatibility mechanisms", async () => {
        renderActions();
        expect(await screen.findByRole("heading", { name: "Compatibility actions" })).toBeInTheDocument();
        expect(screen.getByText(/Monitoring expectations do not invoke these actions/i)).toBeInTheDocument();
        expect(screen.getByText(/operational maintenance is a separate workflow/i)).toBeInTheDocument();
    });

    it("requires advertised parameters before execution", async () => {
        const user = userEvent.setup();
        mockedGetProviderActions.mockResolvedValue([
            unloadAction,
        ]);
        renderActions();

        const actionButton = await screen.findByRole("button", {
            name: "Unload Model",
        });

        expect(actionButton).toBeDisabled();

        await user.type(
            screen.getByLabelText(/model/i),
            "gemma4:12b",
        );

        expect(actionButton).toBeEnabled();
    });

    it("does not execute when confirmation is declined", async () => {
        const user = userEvent.setup();
        mockedGetProviderActions.mockResolvedValue([
            unloadAction,
        ]);
        vi.spyOn(window, "confirm").mockReturnValue(false);
        renderActions();

        await user.type(
            await screen.findByLabelText(/model/i),
            "gemma4:12b",
        );
        await user.click(
            screen.getByRole("button", {
                name: "Unload Model",
            }),
        );

        expect(mockedRunProviderAction).not.toHaveBeenCalled();
    });

    it("shows API failures without refreshing state", async () => {
        const user = userEvent.setup();
        const onActionCompleted = renderActions();
        mockedRunProviderAction.mockRejectedValue(
            new Error("Provider unavailable."),
        );

        await user.click(
            await screen.findByRole("button", {
                name: "Run Diagnostics",
            }),
        );

        expect(
            await screen.findByText("Provider unavailable."),
        ).toBeInTheDocument();
        expect(onActionCompleted).not.toHaveBeenCalled();
    });
});
