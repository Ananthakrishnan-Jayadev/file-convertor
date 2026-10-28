import { useRef, useState } from "react";

type Props = {
  title: string;
  accept: string[];
  multiple?: boolean;
  disabled?: boolean;
  onFiles: (files: File[]) => void;
};

export default function DropZone({ title, accept, multiple = true, disabled = false, onFiles }: Props) {
  const [over, setOver] = useState(false);
  const input = useRef<HTMLInputElement>(null);

  function take(list: FileList | null) {
    if (disabled || !list?.length) return;
    const files = Array.from(list);
    onFiles(multiple ? files : files.slice(0, 1));
  }

  return (
    <div
      className={`dropzone${over ? " is-over" : ""}${disabled ? " is-disabled" : ""}`}
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
      <p className="dropzone-title">{title}</p>
      <p className="dropzone-hint">or</p>
      <button className="btn btn-primary" disabled={disabled} onClick={() => input.current?.click()}>
        {multiple ? "Choose files" : "Choose a file"}
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
      {accept.length > 0 && <p className="dropzone-formats">{accept.map((e) => e.toUpperCase()).join(" ")}</p>}
    </div>
  );
}
