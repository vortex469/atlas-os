import { useState } from "react";

export function CopyCommandButton({ command }: { command: string }) {
    const [copyMessage, setCopyMessage] = useState<string | null>(null);
    return <span className="inline-flex flex-wrap items-center gap-2">
        <button
            type="button"
            onClick={() => {
                const clipboard = navigator.clipboard;
                if (!clipboard?.writeText) {
                    setCopyMessage("Copy unavailable. Select and copy the command above.");
                    return;
                }
                void clipboard.writeText(command)
                    .then(() => setCopyMessage("Command copied."))
                    .catch(() => setCopyMessage("Copy unavailable. Select and copy the command above."));
            }}
            className="shrink-0 rounded border border-mc-border-subtle px-2 py-1 text-xs font-medium text-mc-text-primary hover:bg-mc-surface-muted"
        >
            Copy command
        </button>
        {copyMessage && <span role="status" className="text-xs">{copyMessage}</span>}
    </span>;
}
