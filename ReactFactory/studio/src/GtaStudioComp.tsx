import React from "react";
import {
  AbsoluteFill,
  Img,
  interpolate,
  spring,
  staticFile,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";
import { ThreeCanvas } from "@remotion/three";

export interface WordTiming {
  w: string;
  s: number;
  e: number;
}

export interface ComparisonItem {
  label: string;
  value: number;
  display: string;
}

export interface SceneProps {
  sceneType: "map_zoom" | "character_dossier" | "data_comparison" | "feature_spotlight" | "cinema_broll";
  badgeType: "OFICIAL" | "CONFIRMADO" | "RUMOR" | "TEORIA" | "ANALISE";
  sourceLabel: string;
  actNum: number;
  totalActs: number;
  actTitle: string;
  headline: string;
  subheadline: string;
  locationKey?: string;
  characterName?: string;
  characterRole?: string;
  characterFacts?: string[];
  statValue?: string;
  statUnit?: string;
  statLabel?: string;
  comparisonItems?: ComparisonItem[];
  primaryImageUrl?: string;
  secondaryImageUrl?: string;
  words?: WordTiming[];
  isVertical?: boolean;
}

// Coordenadas exatas (em %) sobre o mapa de satélite real de Leonida (leonida_satellite_map.jpg)
const LEONIDA_REGIONS: Record<string, { name: string; xPct: number; yPct: number; coords: string; desc: string }> = {
  vice_city: {
    name: "VICE CITY",
    xPct: 79,
    yPct: 40,
    coords: "25.7617° N • 80.1918° W",
    desc: "Metrópole costeira, praias de Vice Beach e ilhas barreira",
  },
  leonida_keys: {
    name: "LEONIDA KEYS",
    xPct: 51,
    yPct: 87,
    coords: "24.5551° N • 81.7800° W",
    desc: "Arquipélago tropical conectado por pontes oceânicas",
  },
  grassrivers: {
    name: "GRASSRIVERS & LAGO LEONIDA",
    xPct: 50,
    yPct: 52,
    coords: "26.1200° N • 80.9800° W",
    desc: "Pântanos extensos, vida selvagem e lago central",
  },
  port_gellhorn: {
    name: "PORT GELLHORN",
    xPct: 18,
    yPct: 46,
    coords: "26.4100° N • 82.0500° W",
    desc: "Porto industrial na costa oeste e rodovias costeiras",
  },
  ambrosia: {
    name: "AMBROSIA",
    xPct: 28,
    yPct: 47,
    coords: "26.6800° N • 81.2500° W",
    desc: "Polo industrial e refinarias no coração de Leonida",
  },
  mount_kalaga: {
    name: "MOUNT KALAGA",
    xPct: 46,
    yPct: 14,
    coords: "27.4500° N • 81.5500° W",
    desc: "Serras florestais, trilhas off-road e reservas do norte",
  },
};

const studioFontStyles = `
@font-face {
  font-family: 'AntonStudio';
  src: url('${staticFile("fonts/Anton-Regular.ttf")}') format('truetype');
}
@font-face {
  font-family: 'PoppinsStudioBlack';
  src: url('${staticFile("fonts/Poppins-Black.ttf")}') format('truetype');
}
@font-face {
  font-family: 'PoppinsStudioBold';
  src: url('${staticFile("fonts/Poppins-ExtraBold.ttf")}') format('truetype');
}
`;

const BADGE_STYLE: Record<string, { dot: string; label: string }> = {
  OFICIAL: { dot: "#10B981", label: "GAMEPLAY OFICIAL • GTA VI" },
  CONFIRMADO: { dot: "#38BDF8", label: "CONFIRMADO NAS LIVES" },
  RUMOR: { dot: "#F59E0B", label: "RUMOR EM ANÁLISE" },
  TEORIA: { dot: "#A855F7", label: "ANÁLISE EDITORIAL" },
  ANALISE: { dot: "#38BDF8", label: "ANÁLISE TÉCNICA" },
};

const Studio3DCore: React.FC<{ frame: number }> = ({ frame }) => {
  const rotY = frame * 0.022;
  const rotX = Math.sin(frame * 0.018) * 0.25;
  return (
    <>
      <ambientLight intensity={0.6} />
      <pointLight position={[8, 8, 8]} intensity={2.6} color="#FFBE0B" />
      <pointLight position={[-8, -5, 6]} intensity={2.0} color="#38BDF8" />
      <mesh rotation={[rotX, rotY, 0.12]}>
        <icosahedronGeometry args={[2.0, 1]} />
        <meshStandardMaterial color="#1E293B" metalness={0.85} roughness={0.18} wireframe />
      </mesh>
      <mesh rotation={[-rotX * 0.7, -rotY * 1.15, 0.4]}>
        <octahedronGeometry args={[1.15, 0]} />
        <meshStandardMaterial color="#FFBE0B" emissive="#D97706" emissiveIntensity={0.45} metalness={0.9} roughness={0.12} />
      </mesh>
    </>
  );
};

// ============================================================================
// 1. MAPA DE SATÉLITE REAL EM VOO 3D DE CÂMERA (LEONIDA SATELLITE FLYOVER V4)
// ============================================================================
const MapZoomView: React.FC<{ props: SceneProps; frame: number; fps: number }> = ({ props, frame, fps }) => {
  const loc = LEONIDA_REGIONS[props.locationKey || "vice_city"] || LEONIDA_REGIONS.vice_city;
  const fly = spring({ frame, fps, config: { damping: 24, stiffness: 52, mass: 1.25 } });
  const cardIn = spring({ frame: Math.max(0, frame - 8), fps, config: { damping: 20, stiffness: 90 } });

  // Câmera de satélite 3D começa aberta (1.12x) e faz mergulho suave até 2.05x direto sobre a região!
  const camScale = interpolate(fly, [0, 1], [1.14, 2.05]);
  const tiltX = interpolate(fly, [0, 1], [16, 32]);
  const targetOffsetX = (50 - loc.xPct) * 0.92;
  const targetOffsetY = (50 - loc.yPct) * 0.85;
  const tx = interpolate(fly, [0, 1], [0, targetOffsetX]);
  const ty = interpolate(fly, [0, 1], [0, targetOffsetY]);

  const pulse1 = (frame % 36) / 36;
  const pulse2 = ((frame + 18) % 36) / 36;

  return (
    <AbsoluteFill style={{ backgroundColor: "#060911", overflow: "hidden" }}>
      {/* PALCO 3D DO MAPA DE SATÉLITE REAL DE LEONIDA */}
      <div
        style={{
          position: "absolute",
          inset: -60,
          perspective: "1500px",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
        }}
      >
        <div
          style={{
            position: "relative",
            width: 1920,
            height: 1080,
            transformStyle: "preserve-3d",
            transform: `rotateX(${tiltX}deg) scale(${camScale}) translate(${tx}%, ${ty}%)`,
            transformOrigin: "center center",
          }}
        >
          <Img
            src={staticFile("leonida_satellite_map.jpg")}
            style={{
              width: "100%",
              height: "100%",
              objectFit: "cover",
              filter: "contrast(1.12) saturate(1.18) brightness(0.92)",
            }}
          />

          {/* Pins sutis de todas as outras regiões no mapa real */}
          {Object.entries(LEONIDA_REGIONS).map(([key, reg]) => {
            const isTarget = key === (props.locationKey || "vice_city");
            if (isTarget) return null;
            return (
              <div
                key={key}
                style={{
                  position: "absolute",
                  left: `${reg.xPct}%`,
                  top: `${reg.yPct}%`,
                  transform: "translate(-50%, -50%)",
                  display: "flex",
                  alignItems: "center",
                  gap: 6,
                }}
              >
                <div style={{ width: 8, height: 8, borderRadius: "50%", background: "rgba(255,255,255,0.85)", boxShadow: "0 0 10px rgba(0,0,0,0.9)" }} />
                <span
                  style={{
                    fontFamily: "PoppinsStudioBold",
                    fontSize: 13,
                    color: "rgba(255,255,255,0.82)",
                    letterSpacing: 1.5,
                    textShadow: "0 2px 8px rgba(0,0,0,0.98)",
                    whiteSpace: "nowrap",
                  }}
                >
                  {reg.name}
                </span>
              </div>
            );
          })}

          {/* BEACON 3D VOLUMÉTRICO NA REGIÃO ALVO */}
          <div
            style={{
              position: "absolute",
              left: `${loc.xPct}%`,
              top: `${loc.yPct}%`,
              transform: "translate(-50%, -50%)",
            }}
          >
            {/* Ondas de sonar sobre o terreno real */}
            <div
              style={{
                position: "absolute",
                left: "50%",
                top: "50%",
                width: 30 + pulse1 * 130,
                height: 30 + pulse1 * 130,
                transform: "translate(-50%, -50%)",
                borderRadius: "50%",
                border: "2.5px solid #FFBE0B",
                opacity: (1 - pulse1) * 0.9,
              }}
            />
            <div
              style={{
                position: "absolute",
                left: "50%",
                top: "50%",
                width: 30 + pulse2 * 130,
                height: 30 + pulse2 * 130,
                transform: "translate(-50%, -50%)",
                borderRadius: "50%",
                border: "2px solid #38BDF8",
                opacity: (1 - pulse2) * 0.75,
              }}
            />
            {/* Ponto luminoso central */}
            <div
              style={{
                width: 20,
                height: 20,
                borderRadius: "50%",
                background: "#FFBE0B",
                border: "3px solid #FFFFFF",
                boxShadow: "0 0 28px #FFBE0B, 0 0 12px #FFFFFF",
              }}
            />
            {/* Etiqueta flutuante centralizada ACIMA do pino (nunca colide com o card direito) */}
            <div
              style={{
                position: "absolute",
                left: "50%",
                top: -48,
                transform: "translateX(-50%)",
                padding: "6px 14px",
                borderRadius: 8,
                background: "rgba(8, 11, 18, 0.90)",
                border: "1.5px solid #FFBE0B",
                boxShadow: "0 10px 26px rgba(0,0,0,0.85)",
                whiteSpace: "nowrap",
              }}
            >
              <span style={{ fontFamily: "PoppinsStudioBlack", fontSize: 16, color: "#FFBE0B", letterSpacing: 1.5 }}>
                {loc.name}
              </span>
            </div>
          </div>
        </div>
      </div>

      {/* Atmosfera e vinheta cinematográfica de profundidade */}
      <div
        style={{
          position: "absolute",
          inset: 0,
          background:
            "radial-gradient(circle at 38% 50%, transparent 32%, rgba(6,9,17,0.72) 85%, rgba(6,9,17,0.92) 100%)",
          pointerEvents: "none",
        }}
      />

      {/* CARD EDITORIAL GLASS FLUTUANTE À DIREITA (FOTO REAL DO LOCAL + DADOS) */}
      <div
        style={{
          position: "absolute",
          right: 58,
          top: 108,
          width: 590,
          borderRadius: 20,
          padding: 28,
          background: "rgba(9, 13, 22, 0.84)",
          backdropFilter: "blur(20px)",
          border: "1px solid rgba(255,255,255,0.16)",
          borderTop: "4px solid #FFBE0B",
          boxShadow: "0 30px 70px rgba(0,0,0,0.78)",
          transform: `translateX(${interpolate(cardIn, [0, 1], [65, 0])}px)`,
          opacity: cardIn,
        }}
      >
        <div style={{ fontFamily: "PoppinsStudioBold", fontSize: 14, color: "#FFBE0B", letterSpacing: 2.5 }}>
          SATÉLITE LEONIDA • {loc.coords}
        </div>
        <div
          style={{
            fontFamily: "AntonStudio",
            fontSize: 52,
            color: "#FFFFFF",
            lineHeight: 1.04,
            letterSpacing: 1,
            marginTop: 8,
            textTransform: "uppercase",
          }}
        >
          {props.headline}
        </div>
        <div style={{ fontFamily: "PoppinsStudioBold", fontSize: 18, color: "#CBD5E1", marginTop: 10, lineHeight: 1.4 }}>
          {props.subheadline || loc.desc}
        </div>
        {props.primaryImageUrl ? (
          <div
            style={{
              marginTop: 22,
              borderRadius: 14,
              overflow: "hidden",
              border: "1px solid rgba(255,255,255,0.18)",
              height: 300,
              boxShadow: "0 16px 36px rgba(0,0,0,0.65)",
            }}
          >
            <Img
              src={props.primaryImageUrl}
              style={{ width: "100%", height: "100%", objectFit: "cover", transform: `scale(${1.0 + frame * 0.0008})` }}
            />
          </div>
        ) : null}
      </div>
    </AbsoluteFill>
  );
};

// ============================================================================
// 2. DOSSIÊ DE PERSONAGEM ESTILO DOCUMENTÁRIO NETFLIX / IGN V4
// ============================================================================
const CharacterDossierView: React.FC<{ props: SceneProps; frame: number; fps: number }> = ({ props, frame, fps }) => {
  const enter = spring({ frame, fps, config: { damping: 22, stiffness: 80 } });
  const imgScale = interpolate(frame, [0, 120], [1.02, 1.08], { extrapolateRight: "clamp" });

  return (
    <AbsoluteFill style={{ backgroundColor: "#070A12", overflow: "hidden" }}>
      {props.primaryImageUrl ? (
        <Img
          src={props.primaryImageUrl}
          style={{
            position: "absolute",
            inset: 0,
            width: "100%",
            height: "100%",
            objectFit: "cover",
            filter: "blur(36px) brightness(0.24) saturate(1.3)",
            transform: "scale(1.15)",
          }}
        />
      ) : null}

      {/* Marca d'água editorial gigante no fundo */}
      <div
        style={{
          position: "absolute",
          left: 48,
          top: 76,
          fontFamily: "AntonStudio",
          fontSize: 210,
          color: "rgba(255,255,255,0.035)",
          letterSpacing: 6,
          whiteSpace: "nowrap",
        }}
      >
        {(props.characterName || "LEONIDA").toUpperCase()}
      </div>

      {/* Retrato Cinema 4K à Esquerda */}
      <div
        style={{
          position: "absolute",
          left: 64,
          top: 108,
          width: 820,
          height: 820,
          borderRadius: 22,
          overflow: "hidden",
          border: "1px solid rgba(255,255,255,0.18)",
          boxShadow: "0 32px 80px rgba(0,0,0,0.82)",
          transform: `translateY(${interpolate(enter, [0, 1], [30, 0])}px)`,
          opacity: enter,
        }}
      >
        {props.primaryImageUrl ? (
          <Img src={props.primaryImageUrl} style={{ width: "100%", height: "100%", objectFit: "cover", transform: `scale(${imgScale})` }} />
        ) : null}
        <div
          style={{
            position: "absolute",
            inset: 0,
            background: "linear-gradient(180deg, transparent 58%, rgba(7,10,18,0.92) 100%)",
          }}
        />
        <div style={{ position: "absolute", left: 32, bottom: 28 }}>
          <div style={{ fontFamily: "PoppinsStudioBold", fontSize: 15, color: "#FFBE0B", letterSpacing: 3 }}>
            DOSSIÊ OFICIAL • GTA VI
          </div>
          <div style={{ fontFamily: "AntonStudio", fontSize: 68, color: "#FFF", lineHeight: 1.0, marginTop: 4 }}>
            {(props.characterName || "LUCIA & JASON").toUpperCase()}
          </div>
        </div>
      </div>

      {/* Coluna de Fatos & Inteligência à Direita */}
      <div
        style={{
          position: "absolute",
          left: 940,
          right: 64,
          top: 126,
          display: "flex",
          flexDirection: "column",
          gap: 20,
        }}
      >
        <div style={{ fontFamily: "PoppinsStudioBold", fontSize: 18, color: "#38BDF8", letterSpacing: 2.5, textTransform: "uppercase" }}>
          {props.characterRole || "PROTAGONISTAS • ESTADO DE LEONIDA"}
        </div>
        <div style={{ fontFamily: "AntonStudio", fontSize: 58, color: "#F8FAFC", lineHeight: 1.04, textTransform: "uppercase" }}>
          {props.headline}
        </div>
        <div style={{ height: 3, width: 120, background: "linear-gradient(90deg, #FFBE0B, transparent)", marginBottom: 8 }} />

        {(props.characterFacts && props.characterFacts.length > 0
          ? props.characterFacts
          : ["Análise direta das primeiras horas de gameplay", "Detalhes confirmados nas lives de lançamento"]
        )
          .slice(0, 3)
          .map((fact, idx) => {
            const sp = spring({ frame: Math.max(0, frame - 8 - idx * 8), fps, config: { damping: 20, stiffness: 90 } });
            return (
              <div
                key={idx}
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: 20,
                  padding: "22px 26px",
                  borderRadius: 16,
                  background: "rgba(12, 16, 28, 0.82)",
                  backdropFilter: "blur(16px)",
                  border: "1px solid rgba(255,255,255,0.14)",
                  borderLeft: "4px solid #FFBE0B",
                  transform: `translateX(${interpolate(sp, [0, 1], [40, 0])}px)`,
                  opacity: sp,
                }}
              >
                <span style={{ fontFamily: "AntonStudio", fontSize: 34, color: "#FFBE0B" }}>0{idx + 1}</span>
                <span style={{ fontFamily: "PoppinsStudioBold", fontSize: 23, color: "#F1F5F9", lineHeight: 1.35 }}>
                  {fact}
                </span>
              </div>
            );
          })}
      </div>
    </AbsoluteFill>
  );
};

// ============================================================================
// 3. COMPARATIVO DE DADOS 3D DIGITAL FOUNDRY / VOX V4
// ============================================================================
const DataComparison3DView: React.FC<{ props: SceneProps; frame: number; fps: number }> = ({ props, frame, fps }) => {
  const items =
    props.comparisonItems && props.comparisonItems.length >= 2
      ? props.comparisonItems
      : [
          { label: "GTA V (2013)", value: 42, display: "Física RAGE 7 • 1 Metrópole" },
          { label: "GTA VI (2026)", value: 100, display: "Física RAGE 9 • Estado de Leonida" },
        ];

  return (
    <AbsoluteFill style={{ backgroundColor: "#060912", overflow: "hidden" }}>
      <div
        style={{
          position: "absolute",
          inset: 0,
          background:
            "radial-gradient(circle at 22% 50%, rgba(255,190,11,0.14) 0%, transparent 45%), radial-gradient(circle at 82% 24%, rgba(56,189,248,0.14) 0%, transparent 48%)",
        }}
      />

      {/* Objeto 3D Real Three.js à Esquerda */}
      <div style={{ position: "absolute", left: 30, top: 100, width: 620, height: 820 }}>
        <ThreeCanvas width={620} height={820} camera={{ position: [0, 0, 5.4], fov: 42 }}>
          <Studio3DCore frame={frame} />
        </ThreeCanvas>
      </div>

      {/* Painel Comparativo Editorial à Direita */}
      <div
        style={{
          position: "absolute",
          left: 690,
          right: 76,
          top: 120,
          padding: 48,
          borderRadius: 24,
          background: "rgba(10, 14, 24, 0.86)",
          backdropFilter: "blur(20px)",
          border: "1px solid rgba(255,255,255,0.14)",
          boxShadow: "0 30px 80px rgba(0,0,0,0.72)",
        }}
      >
        <div style={{ fontFamily: "PoppinsStudioBold", fontSize: 16, color: "#38BDF8", letterSpacing: 3 }}>
          COMPARATIVO TÉCNICO • GTA VI
        </div>
        <div style={{ fontFamily: "AntonStudio", fontSize: 64, color: "#FFFFFF", lineHeight: 1.04, marginTop: 10, textTransform: "uppercase" }}>
          {props.headline}
        </div>
        <div style={{ display: "flex", alignItems: "baseline", gap: 18, marginTop: 22 }}>
          <span style={{ fontFamily: "AntonStudio", fontSize: 96, color: "#FFBE0B", lineHeight: 1 }}>
            {props.statValue || "9.4M+"}
          </span>
          <span style={{ fontFamily: "PoppinsStudioBold", fontSize: 24, color: "#CBD5E1" }}>
            {props.statUnit || "VIEWS NAS LIVES DE LANÇAMENTO"}
          </span>
        </div>

        <div style={{ marginTop: 34, display: "flex", flexDirection: "column", gap: 26 }}>
          {items.slice(0, 3).map((it, idx) => {
            const fill = spring({ frame: Math.max(0, frame - 8 - idx * 10), fps, config: { damping: 20, stiffness: 65 } });
            const wPct = Math.max(12, Math.min(100, it.value * fill));
            const isHero = idx === items.length - 1;
            return (
              <div key={idx}>
                <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 10 }}>
                  <span style={{ fontFamily: "PoppinsStudioBold", fontSize: 22, color: isHero ? "#FFFFFF" : "#94A3B8" }}>
                    {it.label}
                  </span>
                  <span style={{ fontFamily: "PoppinsStudioBlack", fontSize: 22, color: isHero ? "#FFBE0B" : "#64748B" }}>
                    {it.display}
                  </span>
                </div>
                <div style={{ width: "100%", height: 22, borderRadius: 11, background: "rgba(255,255,255,0.08)", overflow: "hidden" }}>
                  <div
                    style={{
                      width: `${wPct}%`,
                      height: "100%",
                      borderRadius: 11,
                      background: isHero ? "linear-gradient(90deg, #F59E0B, #FFE047)" : "#475569",
                      boxShadow: isHero ? "0 0 22px rgba(255,190,11,0.55)" : "none",
                    }}
                  />
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </AbsoluteFill>
  );
};

export const GtaStudioScene: React.FC<SceneProps> = (props) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  return (
    <AbsoluteFill style={{ backgroundColor: "#060911", fontFamily: "PoppinsStudioBold, sans-serif" }}>
      <style>{studioFontStyles}</style>

      {props.sceneType === "map_zoom" && <MapZoomView props={props} frame={frame} fps={fps} />}
      {props.sceneType === "character_dossier" && <CharacterDossierView props={props} frame={frame} fps={fps} />}
      {(props.sceneType === "data_comparison" || props.sceneType === "feature_spotlight" || props.sceneType === "cinema_broll") && (
        <DataComparison3DView props={props} frame={frame} fps={fps} />
      )}
    </AbsoluteFill>
  );
};
