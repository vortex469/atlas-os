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
            <h2 className="mc-section-heading">
                {title}
            </h2>

            {description && (
                <p className="mc-section-description mt-1">
                    {description}
                </p>
            )}
        </div>
    );
}
