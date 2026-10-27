import { parse, YAMLParseError } from "yaml";

export class ComposeDocumentError extends Error {
    constructor(message: string) {
        super(message);
        this.name = "ComposeDocumentError";
    }
}

export function parseComposeDocument(source: string): Record<string, unknown> {
    let value: unknown;
    try {
        value = parse(source);
    } catch (error) {
        const position = error instanceof YAMLParseError ? error.linePos?.[0] : undefined;
        const location = position && Number.isSafeInteger(position.line) && position.line > 0
            && Number.isSafeInteger(position.col) && position.col > 0
            ? ` near line ${position.line}, column ${position.col}` : "";
        throw new ComposeDocumentError(`Compose document could not be read. Check YAML formatting${location}.`);
    }
    const prototype = value !== null && typeof value === "object" ? Object.getPrototypeOf(value) : undefined;
    if (value === null || typeof value !== "object" || Array.isArray(value)
        || (prototype !== Object.prototype && prototype !== null)) {
        throw new ComposeDocumentError('Use a Compose document with named sections, such as "services:".');
    }
    return value as Record<string, unknown>;
}
