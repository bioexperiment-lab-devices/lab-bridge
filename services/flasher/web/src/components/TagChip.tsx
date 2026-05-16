import { Tag } from "../types";

interface Props {
  tag: Tag;
  onRemove?: (id: string) => void;
  selected?: boolean;
  onClick?: () => void;
}

export function TagChip({ tag, onRemove, selected, onClick }: Props) {
  return (
    <span
      className={`tag-chip ${selected ? "selected" : ""}`}
      onClick={onClick}
      role={onClick ? "button" : undefined}
    >
      {tag.name}
      {onRemove ? (
        <button className="tag-chip-remove" onClick={(e) => { e.stopPropagation(); onRemove(tag.id); }}>
          ×
        </button>
      ) : null}
    </span>
  );
}
