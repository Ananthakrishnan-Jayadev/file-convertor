import { useEffect, useState } from "react";
import { downloadUrl, Job } from "./api";
import { extensionOf, humanSize } from "./format";
import { BROWSER_IMAGES } from "./Thumb";

export function canCompare(file: File, job: Job | undefined): boolean {
  return (
    !!job?.output_name &&
    BROWSER_IMAGES.has(extensionOf(file.name)) &&
    BROWSER_IMAGES.has(extensionOf(job.output_name))
  );
}

/** Original and result side by side, so quality loss from shrinking is easy to judge. */
export default function Compare({ file, job }: { file: File; job: Job }) {
  const [original, setOriginal] = useState<string | null>(null);

  useEffect(() => {
    const url = URL.createObjectURL(file);
    setOriginal(url);
    return () => URL.revokeObjectURL(url);
  }, [file]);

  return (
    <div className="compare">
      <figure>
        {original && <img src={original} alt={`Original ${file.name}`} />}
        <figcaption>Original, {humanSize(file.size)}</figcaption>
      </figure>
      <figure>
        <img src={downloadUrl(job.id)} alt={`Result ${job.output_name}`} />
        <figcaption>Result, {humanSize(job.output_size ?? 0)}</figcaption>
      </figure>
    </div>
  );
}
