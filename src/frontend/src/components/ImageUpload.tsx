import { useState, useRef, useCallback } from "react";
import { Upload, X, Image as ImageIcon } from "lucide-react";

interface Props {
  onFileSelected: (file: File) => void;
  disabled?: boolean;
}

export default function ImageUpload({ onFileSelected, disabled }: Props) {
  const [preview, setPreview] = useState<string | null>(null);
  const [dragging, setDragging] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  const handleFile = useCallback(
    (file: File) => {
      if (!file.type.startsWith("image/")) return;
      setPreview(URL.createObjectURL(file));
      onFileSelected(file);
    },
    [onFileSelected]
  );

  const handleDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      setDragging(false);
      const file = e.dataTransfer.files[0];
      if (file) handleFile(file);
    },
    [handleFile]
  );

  const clear = (e: React.MouseEvent) => {
    e.stopPropagation();
    setPreview(null);
    if (inputRef.current) inputRef.current.value = "";
  };

  return (
    <div>
      <div
        className={`upload-area ${dragging ? "dragging" : ""}`}
        onClick={() => inputRef.current?.click()}
        onDragOver={(e) => {
          e.preventDefault();
          setDragging(true);
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={handleDrop}
      >
        <input
          ref={inputRef}
          type="file"
          accept="image/*"
          onChange={(e) => {
            const f = e.target.files?.[0];
            if (f) handleFile(f);
          }}
          disabled={disabled}
        />
        {preview ? (
          <div style={{ position: "relative" }}>
            <img src={preview} alt="Upload preview" className="upload-preview" />
          </div>
        ) : (
          <>
            <div
              style={{
                width: 48,
                height: 48,
                borderRadius: 12,
                background: "var(--accent-glow)",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                color: "var(--accent)",
              }}
            >
              <Upload size={24} />
            </div>
            <div style={{ textAlign: "center" }}>
              <div style={{ fontWeight: 600, color: "var(--text)" }}>
                Drop image here or click to browse
              </div>
              <div style={{ fontSize: "0.78rem", color: "var(--text-dim)", marginTop: 4 }}>
                Supports JPG, PNG with clear face visibility
              </div>
            </div>
          </>
        )}
      </div>

      {preview && (
        <button
          className="btn btn-outline"
          style={{ marginTop: 10, width: "100%", justifyContent: "center" }}
          onClick={clear}
        >
          <X size={15} /> Remove Photo
        </button>
      )}
    </div>
  );
}
