import {
    act,
    fireEvent,
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
        <ProviderActions
            provider={{ id: "ollama", name: "Ollama" }}
            onActionCompleted={onActionCompleted}
        />, { wrapper: MemoryRouter },
    );

    return onActionCompleted;
}

function actionResult(patch: Partial<ProviderActionResult> = {}): ProviderActionResult {
    return { provider_id: "ollama", action_id: "run-diagnostics", status: "succeeded", success: true,
        message: "Diagnostics completed.", data: {}, warnings: [], ...patch };
}

describe("ProviderActions", () => {
    it("clears parameters immediately when switching providers", async () => {
        mockedGetProviderActions.mockResolvedValue([unloadAction]);
        const user = userEvent.setup();
        const completed = vi.fn();
        const view = render(<ProviderActions provider={{ id: "ollama", name: "Ollama" }} onActionCompleted={completed} />, { wrapper: MemoryRouter });
        await user.type(await screen.findByLabelText(/model/i), "old-provider-model");
        let resolveNext!: (value: ProviderAction[]) => void;
        mockedGetProviderActions.mockImplementationOnce(() => new Promise((resolve) => { resolveNext = resolve; }));
        view.rerender(<ProviderActions provider={{ id: "other", name: "Other" }} onActionCompleted={completed} />);
        expect(screen.queryByLabelText(/model/i)).not.toBeInTheDocument();
        expect(screen.getByText("Loading provider actions...")).toBeInTheDocument();
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
        const view = render(<ProviderActions provider={{ id: "ollama", name: "Ollama" }} onActionCompleted={completed} />, { wrapper: MemoryRouter });
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
        render(<StrictMode><ProviderActions provider={{ id: "ollama", name: "Ollama" }} onActionCompleted={vi.fn()} /></StrictMode>, { wrapper: MemoryRouter });
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

    it("shows an unknown outcome without replaying or refreshing automatically", async () => {
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
            await screen.findByText("Action outcome not confirmed"),
        ).toBeInTheDocument();
        expect(onActionCompleted).not.toHaveBeenCalled();
    });
    it("preserves a confirmed action result when its follow-up refresh rejects", async () => {
        const user = userEvent.setup();
        const completed = vi.fn().mockRejectedValueOnce(new Error("private refresh canary")).mockResolvedValue(undefined);
        mockedRunProviderAction.mockResolvedValueOnce(actionResult());
        renderActions(completed);
        await user.click(await screen.findByRole("button", { name: "Run Diagnostics" }));
        expect(await screen.findByText("Could not refresh provider status.")).toBeVisible();
        expect(screen.getByText("Action completed")).toBeVisible();
        expect(screen.getByText("Diagnostics completed.")).toBeVisible();
        expect(screen.queryByText("Action list unavailable")).not.toBeInTheDocument();
        expect(screen.queryByText("private refresh canary")).not.toBeInTheDocument();
        await user.click(screen.getByRole("button", { name: "Refresh provider status" }));
        await waitFor(() => expect(completed).toHaveBeenCalledTimes(2));
        await waitFor(() => expect(screen.queryByText(/Could not refresh provider status/)).not.toBeInTheDocument());
        expect(mockedRunProviderAction).toHaveBeenCalledTimes(1);
        expect(screen.getByText("Action completed")).toBeVisible();
    });

    it("pauses actions after a lost response and does not resolve it from a status refresh", async () => {
        const user = userEvent.setup();
        const completed = renderActions();
        mockedRunProviderAction.mockRejectedValueOnce(new Error("private action response canary"));
        await user.click(await screen.findByRole("button", { name: "Run Diagnostics" }));
        expect(await screen.findByText("Action outcome not confirmed")).toBeVisible();
        expect(screen.getByRole("button", { name: "Run Diagnostics" })).toBeDisabled();
        expect(screen.getByRole("link", { name: "Review action history" })).toHaveAttribute("href", "/operations");
        expect(screen.queryByRole("button", { name: "Try again" })).not.toBeInTheDocument();
        expect(screen.queryByText("Action failed")).not.toBeInTheDocument();
        expect(screen.queryByText("private action response canary")).not.toBeInTheDocument();
        expect(completed).not.toHaveBeenCalled();
        await user.click(screen.getByRole("button", { name: "Refresh provider status" }));
        await waitFor(() => expect(completed).toHaveBeenCalledTimes(1));
        expect(screen.getByText("Action outcome not confirmed")).toBeVisible();
        expect(screen.getByRole("button", { name: "Run Diagnostics" })).toBeDisabled();
        expect(mockedRunProviderAction).toHaveBeenCalledTimes(1);
    });

    it("keeps an uncertain outcome separate from a failed status read", async () => {
        const user = userEvent.setup();
        const completed = vi.fn().mockRejectedValue(new Error("private status canary"));
        mockedRunProviderAction.mockRejectedValueOnce(new Error("lost response"));
        renderActions(completed);
        await user.click(await screen.findByRole("button", { name: "Run Diagnostics" }));
        await screen.findByText("Action outcome not confirmed");
        await user.click(screen.getByRole("button", { name: "Refresh provider status" }));
        expect(await screen.findByText(/Could not refresh provider status/)).toBeVisible();
        expect(screen.getByText("Action outcome not confirmed")).toBeVisible();
        expect(screen.getByRole("button", { name: "Run Diagnostics" })).toBeDisabled();
        expect(mockedRunProviderAction).toHaveBeenCalledTimes(1);
    });

    it("shows a reported failure without turning it into an unknown transport outcome", async () => {
        const user = userEvent.setup();
        const completed = renderActions();
        mockedRunProviderAction.mockResolvedValueOnce(actionResult({ status: "failed", success: false, message: "Core reported a failed result." }));
        await user.click(await screen.findByRole("button", { name: "Run Diagnostics" }));
        expect(await screen.findByText("Action failed")).toBeVisible();
        expect(screen.getByText("Core reported a failed result.")).toBeVisible();
        expect(screen.queryByText("Action outcome not confirmed")).not.toBeInTheDocument();
        expect(completed).not.toHaveBeenCalled();
        expect(mockedRunProviderAction).toHaveBeenCalledTimes(1);
    });

    it("submits once when clicks arrive before React renders the running state", async () => {
        let finish!: (value: ProviderActionResult) => void;
        mockedRunProviderAction.mockReturnValueOnce(new Promise((resolve) => { finish = resolve; }));
        renderActions();
        const button = await screen.findByRole("button", { name: "Run Diagnostics" });
        act(() => { fireEvent.click(button); fireEvent.click(button); });
        expect(mockedRunProviderAction).toHaveBeenCalledTimes(1);
        await act(async () => { finish(actionResult()); });
        expect(screen.getByText("Action completed")).toBeVisible();
    });

    it("reads a failed catalog again without running an action", async () => {
        const user = userEvent.setup();
        mockedGetProviderActions.mockRejectedValueOnce(new Error("catalog unavailable")).mockResolvedValue([diagnosticsAction]);
        renderActions();
        expect(await screen.findByText("Action list unavailable")).toBeVisible();
        await user.click(screen.getByRole("button", { name: "Reload action list" }));
        expect(await screen.findByRole("button", { name: "Run Diagnostics" })).toBeEnabled();
        expect(mockedRunProviderAction).not.toHaveBeenCalled();
        expect(mockedGetProviderActions).toHaveBeenCalledTimes(2);
    });

    it("latches uncertainty before a stale event handler can submit again", async () => {
        let reject!: (error: Error) => void;
        mockedRunProviderAction.mockReturnValueOnce(new Promise((_, fail) => { reject = fail; }));
        renderActions();
        const button = await screen.findByRole("button", { name: "Run Diagnostics" });
        fireEvent.click(button);
        await act(async () => {
            reject(new Error("lost response"));
            await Promise.resolve(); await Promise.resolve();
            fireEvent.click(button);
        });
        expect(mockedRunProviderAction).toHaveBeenCalledTimes(1);
        expect(screen.getByText("Action outcome not confirmed")).toBeVisible();
    });

    it("does not overlap explicit status refreshes or submit while one is pending", async () => {
        const user = userEvent.setup();
        let finish!: () => void;
        const completed = vi.fn().mockRejectedValueOnce(new Error("read failed"))
            .mockImplementationOnce(() => new Promise<void>((resolve) => { finish = resolve; }));
        mockedRunProviderAction.mockResolvedValueOnce(actionResult());
        renderActions(completed);
        await user.click(await screen.findByRole("button", { name: "Run Diagnostics" }));
        const retry = await screen.findByRole("button", { name: "Refresh provider status" });
        act(() => { fireEvent.click(retry); fireEvent.click(retry); });
        expect(completed).toHaveBeenCalledTimes(2);
        expect(screen.getByRole("button", { name: "Run Diagnostics" })).toBeDisabled();
        expect(mockedRunProviderAction).toHaveBeenCalledTimes(1);
        await act(async () => finish());
        expect(screen.getByText("Action completed")).toBeVisible();
    });

});
