import React from "react";
import { AbsoluteFill, Img, staticFile } from "remotion";

export interface Thumb3DProps {
  heroImageUrl: string;
  line1: string;
  line2: string;
  subline?: string;
  accentColor?: string;
}

const fontStyles = `
@font-face {
  font-family: 'AntonCinema';
  src: url('${staticFile("fonts/Anton-Regular.ttf")}') format('truetype');
  font-weight: 400;
}
@font-face {
  font-family: 'PoppinsBlack';
  src: url('${staticFile("fonts/Poppins-Black.ttf")}') format('truetype');
  font-weight: 900;
}
`;

export const GtaThumbnail3D: React.FC<Thumb3DProps> = ({
  heroImageUrl,
  line1 = "BUGS ABSURDOS",
  line2 = "NO GTA 6!",
  subline = "",
  accentColor = "#FFBE0B",
}) => {
  const build3DExtrusion = (depth: number, color: string) =>
    Array.from({ length: depth }, (_, i) => `${(i + 1) * 0.9}px ${(i + 1) * 1.4}px 0px ${color}`).join(", ");

  const depthGold = `${build3DExtrusion(10, "#140D02")}, 0px 22px 44px rgba(0,0,0,0.94), 0px 0px 36px rgba(255,190,11,0.28)`;
  const depthWhite = `${build3DExtrusion(8, "#090D16")}, 0px 18px 34px rgba(0,0,0,0.92)`;

  return (
    <AbsoluteFill style={{ backgroundColor: "#06080F", overflow: "hidden", position: "relative" }}>
      <style>{fontStyles}</style>

      {/* 1. CENA REAL DO JOGO (PROTAGONISTA 100% — SEM STREAMER, SEM SELOS ARTIFICIAIS) */}
      {heroImageUrl ? (
        <Img
          src={heroImageUrl}
          style={{
            position: "absolute",
            inset: -16,
            width: "calc(100% + 32px)",
            height: "calc(100% + 32px)",
            objectFit: "cover",
            objectPosition: "58% 42%",
            filter: "contrast(1.14) saturate(1.22) brightness(0.98)",
            transform: "scale(1.03)",
          }}
        />
      ) : null}

      {/* 2. SOMBREAMENTO NATURAL CINEMATOGRÁFICO APENAS NO CANTO DO TEXTO */}
      <div
        style={{
          position: "absolute",
          inset: 0,
          background:
            "linear-gradient(96deg, rgba(6,8,14,0.86) 0%, rgba(6,8,14,0.52) 38%, rgba(6,8,14,0.06) 70%, rgba(6,8,14,0.18) 100%)",
        }}
      />
      <div
        style={{
          position: "absolute",
          inset: 0,
          background:
            "linear-gradient(180deg, rgba(0,0,0,0.0) 52%, rgba(6,8,14,0.82) 100%)",
        }}
      />

      {/* 3. TIPOGRAFIA 3D DE IMPACTO LIMPA E HUMANIZADA (ZERO SELOS "AO VIVO" / "LIVES" / CAIXAS DE IA) */}
      <div
        style={{
          position: "absolute",
          left: 56,
          bottom: 54,
          width: 860,
          display: "flex",
          flexDirection: "column",
          justifyContent: "flex-end",
        }}
      >
        <div style={{ transform: "skewX(-5deg) rotate(-1.5deg)", transformOrigin: "left bottom" }}>
          <div style={{ position: "relative", lineHeight: 0.94 }}>
            <div
              style={{
                fontFamily: "AntonCinema",
                fontSize: 122,
                color: "transparent",
                textShadow: depthWhite,
                position: "absolute",
                inset: 0,
                letterSpacing: 1.5,
                WebkitTextStroke: "3px #090D16",
              }}
            >
              {line1}
            </div>
            <div
              style={{
                fontFamily: "AntonCinema",
                fontSize: 122,
                letterSpacing: 1.5,
                background: "linear-gradient(180deg, #FFFFFF 0%, #F1F5F9 66%, #CBD5E1 100%)",
                WebkitBackgroundClip: "text",
                WebkitTextFillColor: "transparent",
                position: "relative",
              }}
            >
              {line1}
            </div>
          </div>

          <div style={{ position: "relative", lineHeight: 0.96, marginTop: 6 }}>
            <div
              style={{
                fontFamily: "AntonCinema",
                fontSize: 148,
                color: "transparent",
                textShadow: depthGold,
                position: "absolute",
                inset: 0,
                letterSpacing: 1.5,
                WebkitTextStroke: "4px #140D02",
              }}
            >
              {line2}
            </div>
            <div
              style={{
                fontFamily: "AntonCinema",
                fontSize: 148,
                letterSpacing: 1.5,
                background: "linear-gradient(180deg, #FFFCE0 0%, #FFE047 36%, #FFAE00 74%, #E85D04 100%)",
                WebkitBackgroundClip: "text",
                WebkitTextFillColor: "transparent",
                position: "relative",
              }}
            >
              {line2}
            </div>
          </div>
        </div>

        {subline ? (
          <div style={{ marginTop: 18 }}>
            <span
              style={{
                fontFamily: "PoppinsBlack",
                fontSize: 30,
                color: "#F8FAFC",
                letterSpacing: 1.2,
                textShadow: "0 4px 18px rgba(0,0,0,0.98), 0 0 4px rgba(0,0,0,0.95)",
                borderBottom: `4px solid ${accentColor}`,
                paddingBottom: 4,
              }}
            >
              {subline}
            </span>
          </div>
        ) : null}
      </div>
    </AbsoluteFill>
  );
};
