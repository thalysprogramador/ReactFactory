import React from "react";
import { AbsoluteFill, Img, staticFile } from "remotion";

export interface Thumb3DProps {
  heroImageUrl: string;
  livePipUrl?: string;
  topKicker: string;
  line1: string;
  line2: string;
  subline: string;
  liveLabel?: string;
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
@font-face {
  font-family: 'PoppinsExtra';
  src: url('${staticFile("fonts/Poppins-ExtraBold.ttf")}') format('truetype');
  font-weight: 800;
}
`;

export const GtaThumbnail3D: React.FC<Thumb3DProps> = ({
  heroImageUrl,
  livePipUrl,
  topKicker = "GTA VI • GAMEPLAY REAL",
  line1 = "ELES TRAVARAM",
  line2 = "AO VIVO!",
  subline = "DAVY JONES & BISTECONE EM VICE CITY",
  liveLabel = "AO VIVO • PS5 PRO",
  accentColor = "#FFBE0B",
}) => {
  // Camadas de extrusão 3D real em profundidade (efeito Cinema 4D / Photoshop 3D)
  const build3DExtrusion = (depth: number, color: string) =>
    Array.from({ length: depth }, (_, i) => `${(i + 1) * 0.9}px ${(i + 1) * 1.4}px 0px ${color}`).join(", ");

  const depthGold = `${build3DExtrusion(10, "#140D02")}, 0px 22px 44px rgba(0,0,0,0.92), 0px 0px 38px rgba(255,190,11,0.32)`;
  const depthWhite = `${build3DExtrusion(8, "#090D16")}, 0px 18px 34px rgba(0,0,0,0.90)`;

  return (
    <AbsoluteFill style={{ backgroundColor: "#06080F", overflow: "hidden", position: "relative" }}>
      <style>{fontStyles}</style>

      {/* 1. CENA HERO 1080P/4K COM COLOR GRADING CINEMA & ZOOM DE IMPACTO */}
      {heroImageUrl ? (
        <Img
          src={heroImageUrl}
          style={{
            position: "absolute",
            inset: -24,
            width: "calc(100% + 48px)",
            height: "calc(100% + 48px)",
            objectFit: "cover",
            objectPosition: "62% 35%",
            filter: "contrast(1.18) saturate(1.28) brightness(0.96)",
            transform: "scale(1.04)",
          }}
        />
      ) : null}

      {/* 2. ILUMINAÇÃO VOLUMÉTRICA DIRECIONAL (SEM ESCURECER A CENA PRINCIPAL) */}
      <div
        style={{
          position: "absolute",
          inset: 0,
          background:
            "linear-gradient(100deg, rgba(5,7,13,0.92) 0%, rgba(5,7,13,0.64) 40%, rgba(5,7,13,0.12) 72%, rgba(5,7,13,0.28) 100%)",
        }}
      />
      <div
        style={{
          position: "absolute",
          inset: 0,
          background:
            "radial-gradient(circle at 82% 18%, rgba(255,130,40,0.32) 0%, rgba(255,42,133,0.14) 32%, transparent 62%)",
          mixBlendMode: "screen",
        }}
      />
      <div
        style={{
          position: "absolute",
          inset: 0,
          background:
            "radial-gradient(circle at 18% 88%, rgba(255,190,11,0.22) 0%, transparent 50%)",
          mixBlendMode: "screen",
        }}
      />

      {/* 3. MONITOR 3D FLUTUANTE EM PERSPECTIVA DA LIVE (DAVY JONES / BISTECONE) */}
      {livePipUrl ? (
        <div
          style={{
            position: "absolute",
            top: 30,
            right: 34,
            width: 344,
            height: 196,
            transform: "perspective(1100px) rotateY(-12deg) rotateX(4deg)",
            borderRadius: 18,
            padding: 4,
            background: "linear-gradient(135deg, rgba(255,255,255,0.55) 0%, rgba(255,190,11,0.65) 45%, rgba(255,255,255,0.12) 100%)",
            boxShadow: "0 28px 60px rgba(0,0,0,0.82), 0 0 32px rgba(255,190,11,0.22)",
          }}
        >
          <div style={{ position: "relative", width: "100%", height: "100%", borderRadius: 14, overflow: "hidden", background: "#000" }}>
            <Img
              src={livePipUrl}
              style={{ width: "100%", height: "100%", objectFit: "cover", filter: "contrast(1.12) saturate(1.16)" }}
            />
            {/* Brilho especular diagonal de tela de vidro */}
            <div
              style={{
                position: "absolute",
                inset: 0,
                background: "linear-gradient(125deg, rgba(255,255,255,0.20) 0%, transparent 38%, transparent 100%)",
              }}
            />
            {/* Badge minimalista AO VIVO */}
            <div
              style={{
                position: "absolute",
                top: 12,
                left: 12,
                display: "flex",
                alignItems: "center",
                gap: 8,
                padding: "6px 14px",
                borderRadius: 99,
                background: "rgba(215, 22, 34, 0.94)",
                boxShadow: "0 4px 16px rgba(220,20,30,0.6)",
              }}
            >
              <div style={{ width: 9, height: 9, borderRadius: "50%", background: "#FFF", boxShadow: "0 0 8px #FFF" }} />
              <span style={{ fontFamily: "PoppinsBlack", fontSize: 15, color: "#FFF", letterSpacing: 1.2 }}>
                {liveLabel}
              </span>
            </div>
          </div>
        </div>
      ) : null}

      {/* 4. BLOCO EDITORIAL & TIPOGRAFIA 3D EXTRUDADA (ESQUERDA — ALTO CONTRASTE MOBILE/DESKTOP) */}
      <div
        style={{
          position: "absolute",
          left: 56,
          bottom: 58,
          top: 52,
          width: 780,
          display: "flex",
          flexDirection: "column",
          justifyContent: "space-between",
        }}
      >
        {/* Kicker Editorial Superior */}
        <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
          <div
            style={{
              width: 6,
              height: 36,
              borderRadius: 4,
              background: `linear-gradient(180deg, ${accentColor}, #FF5400)`,
              boxShadow: `0 0 18px ${accentColor}`,
            }}
          />
          <span
            style={{
              fontFamily: "PoppinsExtra",
              fontSize: 24,
              color: "#F8FAFC",
              letterSpacing: 3.5,
              textTransform: "uppercase",
              textShadow: "0 4px 16px rgba(0,0,0,0.95)",
            }}
          >
            {topKicker}
          </span>
        </div>

        {/* Manchete 3D Principal em 2 linhas inclinadas */}
        <div style={{ transform: "skewX(-5deg) rotate(-1.5deg)", transformOrigin: "left center", marginTop: 40 }}>
          {/* Linha 1: Branco 3D Extrudado */}
          <div style={{ position: "relative", lineHeight: 0.94 }}>
            <div
              style={{
                fontFamily: "AntonCinema",
                fontSize: 118,
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
                fontSize: 118,
                letterSpacing: 1.5,
                background: "linear-gradient(180deg, #FFFFFF 0%, #F1F5F9 62%, #CBD5E1 100%)",
                WebkitBackgroundClip: "text",
                WebkitTextFillColor: "transparent",
                position: "relative",
              }}
            >
              {line1}
            </div>
          </div>

          {/* Linha 2: Ouro Metálico 3D Extrudado (Imã de Clique!) */}
          <div style={{ position: "relative", lineHeight: 0.96, marginTop: 6 }}>
            <div
              style={{
                fontFamily: "AntonCinema",
                fontSize: 146,
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
                fontSize: 146,
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

        {/* Subtítulo limpo com barra de luz (sem caixa vermelha amadora!) */}
        <div style={{ display: "flex", alignItems: "center", gap: 16, marginTop: 18 }}>
          <div
            style={{
              padding: "10px 24px",
              borderRadius: 10,
              background: "rgba(9, 12, 20, 0.78)",
              backdropFilter: "blur(14px)",
              borderLeft: `5px solid ${accentColor}`,
              borderTop: "1px solid rgba(255,255,255,0.16)",
              borderRight: "1px solid rgba(255,255,255,0.08)",
              borderBottom: "1px solid rgba(255,255,255,0.08)",
              boxShadow: "0 14px 30px rgba(0,0,0,0.65)",
            }}
          >
            <span
              style={{
                fontFamily: "PoppinsBlack",
                fontSize: 27,
                color: "#F8FAFC",
                letterSpacing: 1.2,
                textShadow: "0 2px 10px rgba(0,0,0,0.8)",
              }}
            >
              {subline}
            </span>
          </div>
        </div>
      </div>
    </AbsoluteFill>
  );
};
