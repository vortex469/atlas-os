import {
    act,
    render,
    screen,
    waitFor,
    within,
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

    it("keeps a confirmed action result separate from a failed provider refresh", async () => {
        const user = userEvent.setup();
        const refreshProvider = vi.fn()
            .mockRejectedValueOnce(new Error("Provider refresh unavailable."))
            .mockResolvedValueOnce(undefined);
        mockedRunProviderAction.mockResolvedValue({
            provider_id: "ollama",
            action_id: "run-diagnostics",
            status: "succeeded",
            success: true,
            message: "Diagnostics completed.",
            data: {},
            warnings: [],
        });
        renderActions(refreshProvider);

        await user.click(await screen.findByRole("button", { name: "Run Diagnostics" }));

        expect(await screen.findByText("Action completed")).toBeInTheDocument();
        const alert = await screen.findByRole("alert");
        expect(alert).toHaveTextContent("Action completed, but Mission Control could not refresh provider information.");
        expect(alert).toHaveTextContent("Refresh the provider information before running another action.");
        expect(screen.getByRole("button", { name: "Run Diagnostics" })).toBeDisabled();
        expect(mockedRunProviderAction).toHaveBeenCalledOnce();
        const technicalDetails = within(alert).getByText("Technical details").closest("details");
        expect(technicalDetails).not.toHaveAttribute("open");
        expect(within(technicalDetails as HTMLDetailsElement).getByText("Provider refresh unavailable.")).not.toBeVisible();

        await user.click(within(alert).getByRole("button", { name: "Refresh provider information" }));

        expect(screen.queryByRole("alert")).not.toBeInTheDocument();
        expect(screen.getByRole("button", { name: "Run Diagnostics" })).toBeEnabled();
        expect(refreshProvider).toHaveBeenCalledTimes(2);
        expect(mockedRunProviderAction).toHaveBeenCalledOnce();
    });

    it("keeps provider actions separate from monitoring policy and maintenance", async () => {
        renderActions();
        expect(await screen.findByRole("heading", { name: "Direct provider actions" })).toBeInTheDocument();
        expect(screen.getByText(/These buttons run actions directly on this provider/i)).toBeInTheDocument();
        expect(screen.getByText(/planned maintenance, submit a request for review and approval/i)).toBeInTheDocument();
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

        expect(await screen.findByRole("heading", { name: "Direct provider actions are unavailable" })).toBeInTheDocument();
        const alert = screen.getByRole("alert");
        expect(alert).toHaveTextContent("Mission Control could not load the available actions. No action was run.");
        const technicalDetails = within(alert).getByText("Technical details").closest("details");
        expect(technicalDetails).not.toHaveAttribute("open");
        expect(within(technicalDetails as HTMLDetailsElement).getByText("Action list unavailable.")).not.toBeVisible();
        expect(screen.queryByRole("button", { name: "Run Diagnostics" })).not.toBeInTheDocument();
        await user.click(within(technicalDetails as HTMLDetailsElement).getByText("Technical details"));
        expect(within(technicalDetails as HTMLDetailsElement).getByText("Action list unavailable.")).toBeVisible();
        await user.click(screen.getByRole("button", { name: "Try again" }));
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

    it("shows readable parameter labels and preserves the original request key", async () => {
        const user = userEvent.setup();
        mockedGetProviderActions.mockResolvedValue([{
            ...diagnosticsAction,
            id: "inspect-resource",
            label: "Inspect Resource",
            parameters: {
                resource_id: {
                    type: "string",
                    required: true,
                    description: "Provider resource to inspect.",
                    example: "110",
                },
            },
        }]);
        mockedRunProviderAction.mockResolvedValue({
            provider_id: "ollama",
            action_id: "inspect-resource",
            status: "succeeded",
            success: true,
            message: "Resource inspected.",
            data: {},
            warnings: [],
        });
        renderActions();

        const resourceId = await screen.findByLabelText(/Resource ID/);
        expect(resourceId).toHaveAttribute("placeholder", "110");
        await user.type(resourceId, "guest-110");
        await user.click(screen.getByRole("button", { name: "Inspect Resource" }));

        await waitFor(() => expect(mockedRunProviderAction).toHaveBeenCalledWith(
            "ollama",
            "inspect-resource",
            { confirmed: false, parameters: { resource_id: "guest-110" } },
        ));
        expect(await screen.findByText("Resource inspected.")).toBeInTheDocument();
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

        expect(window.confirm).toHaveBeenCalledOnce();
        expect(window.confirm).toHaveBeenCalledWith(expect.stringContaining("Unload Model on Ollama requires confirmation."));
        expect(window.confirm).toHaveBeenCalledWith(expect.stringContaining("Unload a model from memory."));
        expect(window.confirm).toHaveBeenCalledWith(expect.stringContaining("Model: gemma4:12b"));
        expect(mockedRunProviderAction).not.toHaveBeenCalled();
    });

    it("keeps the action list after a failed request and points to action history", async () => {
        const user = userEvent.setup();
        mockedGetProviderActions.mockResolvedValue([
            diagnosticsAction,
            { ...diagnosticsAction, id: "run-healthcheck", label: "Run Healthcheck" },
            unloadAction,
        ]);
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
        expect(alert).toHaveTextContent("Direct provider actions are paused here to prevent a duplicate.");
        expect(alert).toHaveTextContent("Check Action history, then reload this provider page before deciding whether to try again.");
        expect(screen.getByRole("button", { name: "Run Diagnostics" })).toBeDisabled();
        expect(screen.getByRole("button", { name: "Run Healthcheck" })).toBeDisabled();
        expect(screen.getByLabelText(/model/i)).toBeDisabled();
        expect(screen.getByRole("link", { name: "Open Action history →" })).toHaveAttribute("href", "/operations");
        expect(screen.queryByRole("button", { name: "Try again" })).not.toBeInTheDocument();
        expect(mockedGetProviderActions).toHaveBeenCalledTimes(1);
        expect(onActionCompleted).not.toHaveBeenCalled();
        await user.click(screen.getByRole("button", { name: "Run Diagnostics" }));
        expect(mockedRunProviderAction).toHaveBeenCalledOnce();
        const technicalDetails = within(alert).getByText("Technical details").closest("details");
        expect(technicalDetails).not.toHaveAttribute("open");
        expect(within(technicalDetails as HTMLDetailsElement).getByText("Provider unavailable.")).not.toBeVisible();
        await user.click(within(technicalDetails as HTMLDetailsElement).getByText("Technical details"));
        expect(within(technicalDetails as HTMLDetailsElement).getByText("Provider unavailable.")).toBeVisible();
    });
});
