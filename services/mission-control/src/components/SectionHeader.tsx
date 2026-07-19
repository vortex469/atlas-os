type SectionHeaderProps = {
    title: string;
    description?: string;
};

export function SectionHeader({
    title,
    description,
}: SectionHeaderProps) {
    return (
        <div className="mb-4">
            <h2 className="text-sm font-semibold uppercase tracking-[0.15em] text-slate-200">
                {title}
            </h2>

            {description && (
                <p className="mt-1 text-sm text-slate-500">
                    {description}
                </p>
            )}
        </div>
    );
}