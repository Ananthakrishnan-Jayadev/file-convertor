import { type ReactNode, useRef, useState } from "react";
import type { FormatGroup } from "./format";

type Props = {
  title: string;
  accept: string[];
  /** Accepted formats sorted by kind; without it, the plain extension list is shown. */
  groups?: FormatGroup[];
  multiple?: boolean;
  disabled?: boolean;
  /** Once files are listed, shrink to a quiet "Add more files" bar so the tool's own action leads. */
  compact?: boolean;
  /** Extra controls for the compact bar, such as Clear list. */
  extra?: ReactNode;
  onFiles: (files: File[]) => void;
};

export default function DropZone({
  title,
  accept,
  groups,
  multiple = true,
  disabled = false,
  compact = false,
  extra,
  onFiles,
}: Props) {
  const [over, setOver] = useState(false);
  const input = useRef<HTMLInputElement>(null);

  function take(list: FileList | null) {
    if (disabled || !list?.length) return;
    const files = Array.from(list);
    onFiles(multiple ? files : files.slice(0, 1));
  }

  const showFormats = !compact && accept.length > 0;

  // The children keep the same positions in both sizes, so the button that was just used keeps keyboard focus.
  return (
    <div
      className={`dropzone${compact ? " is-compact" : ""}${over ? " is-over" : ""}${disabled ? " is-disabled" : ""}`}
      onDragOver={(e) => {
        e.preventDefault();
        setOver(true);
      }}
      onDragLeave={() => setOver(false)}
      onDrop={(e) => {
        e.preventDefault();
        setOver(false);
        take(e.dataTransfer.files);
      }}
    >
      <p className="dropzone-title">{compact ? "Drop more files here" : title}</p>
      <button
        className={compact ? "btn" : "btn btn-primary"}
        disabled={disabled}
        onClick={() => input.current?.click()}
      >
        {compact ? "Add more files" : multiple ? "Choose files" : "Choose a file"}
      </button>
      <input
        ref={input}
        type="file"
        multiple={multiple}
        hidden
        accept={accept.map((e) => `.${e}`).join(",")}
        onChange={(e) => {
          take(e.target.files);
          e.target.value = "";
        }}
      />
      {compact && extra}
      {showFormats &&
        (groups && groups.length > 0 ? (
          <dl className="dropzone-formats format-groups">
            {groups.map((g) => (
              <div key={g.name} className="format-group">
                <dt>{g.name}</dt>
                <dd>{g.exts.map((e) => e.toUpperCase()).join(" ")}</dd>
              </div>
            ))}
          </dl>
        ) : (
          <p className="dropzone-formats">{accept.map((e) => e.toUpperCase()).join(" ")}</p>
        ))}
    </div>
  );
}
