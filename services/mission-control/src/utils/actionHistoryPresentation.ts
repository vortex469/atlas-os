import type { ActionHistoryStatus } from "../types/actionHistory";

export function actionHistoryStatusLabel(status: ActionHistoryStatus): string {
    return status === "succeeded" ? "Succeeded" : "Failed";
}
