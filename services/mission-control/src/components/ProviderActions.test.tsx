import {
    act,
    render,
    screen,
    waitFor,
} from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { StrictMode } from "react";
import { MemoryRouter } from "react-router-dom";

import {
    getProviderActions,
    runProviderAction,
} from "../api/atlas";
import type { ProviderAction, ProviderActionResult } from "../types/providerAction";
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
        <MemoryRouter>
            <ProviderActions
                provider={{ id: "ollama", name: "Ollama" }}
                onActionCompleted={onActionCompleted}
            />
        </MemoryRouter>,
    );

    return onActionCompleted;
}

describe("ProviderActions", () => {
    it("clears parameters immediately when switching providers", async () => {
        mockedGetProviderActions.mockResolvedValue([unloadAction]);
        const user = userEvent.setup();
        const completed = vi.fn();
        const view = render(<ProviderActions provider={{ id: "ollama", name: "Ollama" }} onActionCompleted={completed} />);
        await user.type(await screen.findByLabelText(/model/i), "old-provider-model");
        let resolveNext!: (value: ProviderAction[]) => void;
        mockedGetProviderActions.mockImplementationOnce(() => new Promise((resolve) => { resolveNext = resolve; }));
        view.rerender(<ProviderActions provider={{ id: "other", name: "Other" }} onActionCompleted={completed} />);
        expect(screen.queryByLabelText(/model/i)).not.toBeInTheDocument();
        expect(screen.getByText("Loading available actions…")).toBeInTheDocument();
        await waitFor(() => expect(mockedGetProviderActions).toHaveBeenCalledWith("other"));
        await act(async () => resolveNext([unloadAction]));
        expect(await screen.findByLabelText(/model/i)).toHaveValue("");
        expect(screen.getByRole("button", { name: "Unload Model" })).toBeDisabled();
        expect(mockedRunProviderAction).not.toHaveBeenCalled();
    });

    it("does not attach a previous provider's action result or refresh the new provider", async () => {
        let resolveAction!: (value: ProviderActionResult) => void;
        mockedRunProviderAction.mockImplementationOnce(() => new Promise((resolve) => { resolveAction = resolve; }));
        const completed = vi.fn();
        const view = render(<ProviderActions provider={{ id: "ollama", name: "Ollama" }} onActionCompleted={completed} />);
        const user = userEvent.setup();
        await user.click(await screen.findByRole("button", { name: "Run Diagnostics" }));
        view.rerender(<ProviderActions provider={{ id: "other", name: "Other" }} onActionCompleted={completed} />);
        await screen.findByRole("button", { name: "Run Diagnostics" });
        await act(async () => resolveAction({ provider_id: "ollama", action_id: "run-diagnostics", status: "succeeded", success: true, message: "Old provider result", data: {}, warnings: [] }));
        expect(screen.queryByText("Old provider result")).not.toBeInTheDocument();
        expect(completed).not.toHaveBeenCalled();
        expect(mockedRunProviderAction).toHaveBeenCalledTimes(1);
    });

    it("reads the action catalog once under Strict Mode without running an action", async () => {
        render(<StrictMode><ProviderActions provider={{ id: "ollama", name: "Ollama" }} onActionCompleted={vi.fn()} /></StrictMode>);
        await screen.findByRole("button", { name: "Run Diagnostics" });
        expect(mockedGetProviderActions).toHaveBeenCalledTimes(1);
        expect(mockedRunProviderAction).not.toHaveBeenCalled();
    });

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

    it("keeps provider actions separate from monitoring policy and maintenance", async () => {
        renderActions();
        expect(await screen.findByRole("heading", { name: "Provider actions" })).toBeInTheDocument();
        expect(screen.getByText(/Monitoring policy does not run these actions/i)).toBeInTheDocument();
        expect(screen.getByText(/Service maintenance uses a separate approval workflow/i)).toBeInTheDocument();
    });

    it("describes an empty action list in plain language", async () => {
        mockedGetProviderActions.mockResolvedValueOnce([]);
        renderActions();
        expect(await screen.findByText("No actions are available for this provider.")).toBeInTheDocument();
    });

    it("retries a failed action-list read without running an action", async () => {
        const user = userEvent.setup();
        mockedGetProviderActions.mockRejectedValueOnce(new Error("Action list unavailable."));
        renderActions();

        expect(await screen.findByRole("heading", { name: "Provider actions are unavailable" })).toBeInTheDocument();
        expect(screen.getByRole("alert")).toHaveTextContent("Action list unavailable.");
        expect(screen.queryByRole("button", { name: "Run Diagnostics" })).not.toBeInTheDocument();
        await user.click(screen.getByRole("button", { name: "Reload actions" }));
        expect(await screen.findByRole("button", { name: "Run Diagnostics" })).toBeInTheDocument();
        expect(mockedGetProviderActions).toHaveBeenCalledTimes(2);
        expect(mockedRunProviderAction).not.toHaveBeenCalled();
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

    it("keeps the action list after a failed request and points to action history", async () => {
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

        const alert = await screen.findByRole("alert");
        expect(alert).toHaveTextContent("Action result unavailable");
        expect(alert).toHaveTextContent("Provider unavailable.");
        expect(alert).toHaveTextContent("Check Action history before trying the action again.");
        expect(screen.getByRole("button", { name: "Run Diagnostics" })).toBeInTheDocument();
        expect(screen.getByRole("link", { name: "Open Action history →" })).toHaveAttribute("href", "/operations");
        expect(screen.queryByRole("button", { name: "Reload actions" })).not.toBeInTheDocument();
        expect(mockedGetProviderActions).toHaveBeenCalledTimes(1);
        expect(onActionCompleted).not.toHaveBeenCalled();
    });
});
