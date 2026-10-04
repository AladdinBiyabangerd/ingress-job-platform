import { ImageResponse } from "next/og";

export const alt = "ingress-job — open roles in Azerbaijan";
export const size = { width: 1200, height: 630 };
export const contentType = "image/png";

export default function OpenGraphImage() {
  return new ImageResponse(
    (
      <div
        style={{
          width: "100%",
          height: "100%",
          display: "flex",
          flexDirection: "column",
          justifyContent: "space-between",
          padding: "64px 72px",
          background: "linear-gradient(145deg, #0a1a5c 0%, #001FFF 55%, #0DC6FF 100%)",
          color: "#ffffff",
          fontFamily: "system-ui, sans-serif",
        }}
      >
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: 18,
            fontSize: 36,
            fontWeight: 700,
            letterSpacing: "-0.03em",
          }}
        >
          <div
            style={{
              width: 56,
              height: 56,
              borderRadius: 14,
              transform: "rotate(45deg)",
              background: "rgba(255,255,255,0.22)",
            }}
          />
          ingress-job
        </div>
        <div style={{ display: "flex", flexDirection: "column", gap: 18 }}>
          <div
            style={{
              fontSize: 72,
              fontWeight: 700,
              letterSpacing: "-0.04em",
              lineHeight: 1.05,
              maxWidth: 900,
            }}
          >
            Open roles in Azerbaijan
          </div>
          <div style={{ fontSize: 30, opacity: 0.92, maxWidth: 820, lineHeight: 1.35 }}>
            Browse job listings. Search by title or company. Filter by city and language.
          </div>
        </div>
      </div>
    ),
    { ...size },
  );
}
