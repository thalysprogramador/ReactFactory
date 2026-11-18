import React from "react";
import {
  AbsoluteFill,
  Img,
  interpolate,
  spring,
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
  sceneType: "map_zoom" | "character_dossier" | "data_comparison" | "feature_spotlight" | "chapter_card";
  badgeType: "OFICIAL" | "CONFIRMADO" | "RUMOR" | "TEORIA";
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

const BADGE_STYLES: Record<string, { label: string; color: string; bg: string }> = {
  OFICIAL: { label: "FONTE OFICIAL ROCKSTAR", color: "#00E676", bg: "rgba(0, 230, 118, 0.16)" },
  CONFIRMADO: { label: "CONFIRMADO POR FONTES", color: "#00F0FF", bg: "rgba(0, 240, 255, 0.16)" },
  RUMOR: { label: "RUMOR / NÃO OFICIAL", color: "#FF6D00", bg: "rgba(255, 109, 0, 0.18)" },
  TEORIA: { label: "ANÁLISE & TEORIA DA COMUNIDADE", color: "#B388FF", bg: "rgba(179, 136, 255, 0.18)" },
};

const LEONIDA_REGIONS: Record<string, { name: string; coords: string; x: number; y: number; desc: string }> = {
  vice_city: { name: "VICE CITY", coords: "25.7617° N, 80.1918° W", x: 0.72, y: 0.58, desc: "Metrópole neon, Ocean Beach, Vice Beach e centro financeiro" },
  leonida_keys: { name: "LEONIDA KEYS", coords: "24.5551° N, 81.7800° W", x: 0.54, y: 0.84, desc: "Arquipélago tropical sul, pontes oceânicas e recifes" },
  grassrivers: { name: "GRASSRIVERS", coords: "25.8500° N, 80.9300° W", x: 0.52, y: 0.66, desc: "Pântanos indomáveis, aerobarcos e vida selvagem" },
  port_gellhorn: { name: "PORT GELLHORN", coords: "26.6406° N, 81.8723° W", x: 0.30, y: 0.50, desc: "Costa industrial oeste, docas, motéis e comércio" },
  ambrosia: { name: "AMBROSIA", coords: "26.7500° N, 80.6500° W", x: 0.53, y: 0.42, desc: "Refinaria açucareira central e gangues de motociclistas" },
  mount_kalaga: { name: "MOUNT KALAGA", coords: "30.4383° N, 83.2000° W", x: 0.43, y: 0.20, desc: "Parque nacional ao norte, cânions e trilhas off-road" },
};

const RotatingPrism3D: React.FC<{ frame: number; color: string }> = ({ frame, color }) => {
  const rotY = frame * 0.035;
  const rotX = Math.sin(frame * 0.02) * 0.35;
  return (
    <group rotation={[rotX, rotY, 0]}>
      <mesh>
        <octahedronGeometry args={[1.85, 0]} />
        <meshStandardMaterial color={color} wireframe emissive={color} emissiveIntensity={0.6} />
      </mesh>
      <mesh scale={[0.68, 0.68, 0.68]} rotation={[0, -rotY * 1.6, 0]}>
        <icosahedronGeometry args={[1.4, 0]} />
        <meshStandardMaterial color="#00F0FF" wireframe emissive="#00F0FF" emissiveIntensity={0.4} />
      </mesh>
      <ambientLight intensity={1.2} />
      <pointLight position={[5, 5, 5]} intensity={2.5} color="#FF2A85" />
    </group>
  );
};

const TopEditorialHUD: React.FC<{ props: SceneProps; frame: number; fps: number }> = ({ props, frame, fps }) => {
  const badge = BADGE_STYLES[props.badgeType] || BADGE_STYLES.OFICIAL;
  const enter = spring({ frame, fps, config: { damping: 16, stiffness: 120 } });
  const progWidth = ((props.actNum || 1) / Math.max(1, props.totalActs || 5)) * 100;

  return (
    <div style={{ position: "absolute", top: 0, left: 0, right: 0, zIndex: 30 }}>
      {/* Barra de progresso editorial superior */}
      <div style={{ width: "100%", height: 6, background: "rgba(255,255,255,0.08)" }}>
        <div
          style={{
            width: `${progWidth}%`,
            height: "100%",
            background: "linear-gradient(90deg, #FF2A85 0%, #00F0FF 100%)",
            boxShadow: "0 0 16px #FF2A85",
          }}
        />
      </div>

      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          padding: "24px 48px",
          transform: `translateY(${(1 - enter) * -30}px)`,
          opacity: enter,
        }}
      >
        {/* Selo obrigatório de verificação da fonte */}
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: 12,
            background: badge.bg,
            border: `1.5px solid ${badge.color}`,
            backdropFilter: "blur(12px)",
            padding: "8px 18px",
            borderRadius: 8,
          }}
        >
          <div
            style={{
              width: 10,
              height: 10,
              borderRadius: "50%",
              background: badge.color,
              boxShadow: `0 0 10px ${badge.color}`,
            }}
          />
          <span
            style={{
              fontFamily: "JetBrains Mono, Consolas, monospace",
              fontSize: 16,
              fontWeight: 800,
              letterSpacing: "0.08em",
              color: badge.color,
            }}
          >
            {badge.label}
          </span>
          <span
            style={{
              fontFamily: "Montserrat, Segoe UI, sans-serif",
              fontSize: 14,
              color: "#CBD5E1",
              borderLeft: "1px solid rgba(255,255,255,0.2)",
              paddingLeft: 12,
            }}
          >
            {props.sourceLabel}
          </span>
        </div>

        {/* Indicador de Ato Editorial */}
        <div
          style={{
            background: "rgba(9, 11, 18, 0.82)",
            border: "1px solid rgba(255,255,255,0.14)",
            padding: "8px 18px",
            borderRadius: 8,
            fontFamily: "JetBrains Mono, Consolas, monospace",
            fontSize: 15,
            color: "#94A3B8",
            letterSpacing: "0.06em",
          }}
        >
          ATO 0{props.actNum} // <strong style={{ color: "#F8FAFC" }}>{props.actTitle}</strong>
        </div>
      </div>
    </div>
  );
};

const WordByWordCaptions: React.FC<{ words?: WordTiming[]; frame: number; fps: number }> = ({
  words,
  frame,
  fps,
}) => {
  if (!words || words.length === 0) return null;
  const t = frame / fps;

  // Agrupa em janelas de 5 palavras para leitura limpa
  let activeIdx = words.findIndex((w) => t >= w.s && t <= w.e + 0.08);
  if (activeIdx === -1) {
    for (let i = words.length - 1; i >= 0; i--) {
      if (t >= words[i].s) {
        activeIdx = i;
        break;
      }
    }
  }
  if (activeIdx === -1) activeIdx = 0;

  const chunkStart = Math.floor(activeIdx / 5) * 5;
  const chunk = words.slice(chunkStart, chunkStart + 5);

  return (
    <div
      style={{
        position: "absolute",
        bottom: 42,
        left: 0,
        right: 0,
        display: "flex",
        justifyContent: "center",
        zIndex: 40,
      }}
    >
      <div
        style={{
          background: "rgba(9, 11, 18, 0.88)",
          border: "1.5px solid rgba(255, 42, 133, 0.45)",
          boxShadow: "0 16px 40px rgba(0,0,0,0.75)",
          padding: "14px 32px",
          borderRadius: 14,
          display: "flex",
          gap: 14,
          alignItems: "center",
          flexWrap: "wrap",
          maxWidth: 1420,
        }}
      >
        {chunk.map((item, idx) => {
          const globalIdx = chunkStart + idx;
          const isCurrent = globalIdx === activeIdx;
          const pop = isCurrent
            ? spring({
                frame: Math.max(0, Math.round((t - item.s) * fps)),
                fps,
                config: { damping: 12, stiffness: 220 },
              })
            : 0;
          const scale = 1 + pop * 0.12;
          return (
            <span
              key={`${globalIdx}-${item.w}`}
              style={{
                fontFamily: "Montserrat, Arial Black, sans-serif",
                fontWeight: 900,
                fontSize: 40,
                textTransform: "uppercase",
                letterSpacing: "0.02em",
                color: isCurrent ? "#FFB800" : "#F8FAFC",
                transform: `scale(${scale})`,
                textShadow: isCurrent
                  ? "0 0 18px rgba(255,184,0,0.65), 0 3px 6px #000"
                  : "0 2px 6px rgba(0,0,0,0.9)",
                transition: "color 0.08s",
              }}
            >
              {item.w}
            </span>
          );
        })}
      </div>
    </div>
  );
};

const MapZoomView: React.FC<{ props: SceneProps; frame: number; fps: number }> = ({ props, frame, fps }) => {
  const key = (props.locationKey || "vice_city").toLowerCase();
  const target = LEONIDA_REGIONS[key] || LEONIDA_REGIONS.vice_city;

  const zoom = interpolate(frame, [0, 75, 150], [1.0, 1.32, 1.45], { extrapolateRight: "clamp" });
  const offsetX = interpolate(frame, [0, 75], [0, (0.52 - target.x) * 480], { extrapolateRight: "clamp" });
  const offsetY = interpolate(frame, [0, 75], [0, (0.52 - target.y) * 360], { extrapolateRight: "clamp" });
  const cardIn = spring({ frame: Math.max(0, frame - 10), fps, config: { damping: 14, stiffness: 110 } });

  return (
    <AbsoluteFill style={{ background: "radial-gradient(circle at 35% 50%, #10192E 0%, #07090F 100%)" }}>
      {/* Grade cartográfica tática */}
      <div
        style={{
          position: "absolute",
          left: 30,
          top: 96,
          width: 1100,
          height: 820,
          overflow: "hidden",
          borderRadius: 20,
          border: "1px solid rgba(0, 240, 255, 0.22)",
          background: "rgba(8, 12, 22, 0.75)",
          backgroundImage:
            "linear-gradient(rgba(0, 240, 255, 0.07) 1px, transparent 1px), linear-gradient(90deg, rgba(0, 240, 255, 0.07) 1px, transparent 1px)",
          backgroundSize: "48px 48px",
        }}
      >
        {/* Contorno estilizado da península de Leonida */}
        <svg
          width="1100"
          height="820"
          viewBox="0 0 1100 820"
          style={{
            transform: `translate(${offsetX}px, ${offsetY}px) scale(${zoom})`,
            transformOrigin: "center center",
          }}
        >
          <path
            d="M 280 80 L 620 95 L 780 250 L 920 470 L 860 610 L 640 720 L 460 740 L 540 590 L 390 520 L 240 390 L 280 230 Z"
            fill="rgba(0, 240, 255, 0.07)"
            stroke="#00F0FF"
            strokeWidth="2.5"
            strokeDasharray="8 5"
          />
          {/* Lago Leonida central */}
          <ellipse cx="580" cy="365" rx="82" ry="60" fill="rgba(0, 240, 255, 0.15)" stroke="#00F0FF" strokeWidth="1.8" />
          {/* Todos os pontos do mapa */}
          {Object.entries(LEONIDA_REGIONS).map(([rk, reg]) => {
            const cx = 120 + reg.x * 820;
            const cy = 40 + reg.y * 710;
            const isTarget = rk === key;
            return (
              <g key={rk}>
                {isTarget && (
                  <>
                    <circle
                      cx={cx}
                      cy={cy}
                      r={18 + (frame % 36) * 1.4}
                      fill="none"
                      stroke="#FF2A85"
                      strokeWidth="2.5"
                      opacity={1 - (frame % 36) / 36}
                    />
                    <circle cx={cx} cy={cy} r={32} fill="rgba(255, 42, 133, 0.22)" stroke="#FF2A85" strokeWidth="2" />
                  </>
                )}
                <circle cx={cx} cy={cy} r={isTarget ? 9 : 5} fill={isTarget ? "#FFB800" : "#00F0FF"} />
                <text
                  x={cx + 14}
                  y={cy + 5}
                  fill={isTarget ? "#FFB800" : "rgba(248,250,252,0.82)"}
                  fontFamily="JetBrains Mono, monospace"
                  fontWeight="800"
                  fontSize={isTarget ? "19" : "13"}
                >
                  {reg.name}
                </text>
              </g>
            );
          })}
        </svg>
      </div>

      {/* Card de Inspeção da Região + Imagem Oficial 4K */}
      <div
        style={{
          position: "absolute",
          right: 64,
          top: 130,
          width: 680,
          background: "rgba(12, 16, 28, 0.90)",
          border: "1.5px solid #00F0FF",
          borderRadius: 18,
          padding: 28,
          boxShadow: "0 24px 60px rgba(0,0,0,0.8)",
          transform: `translateX(${(1 - cardIn) * 120}px)`,
          opacity: cardIn,
        }}
      >
        <div style={{ fontFamily: "JetBrains Mono, monospace", color: "#00F0FF", fontSize: 16, marginBottom: 6 }}>
          SAT-RECON // {target.coords}
        </div>
        <div
          style={{
            fontFamily: "Bebas Neue, Impact, sans-serif",
            fontSize: 56,
            color: "#F8FAFC",
            letterSpacing: "0.04em",
            lineHeight: 1.0,
          }}
        >
          {props.headline || target.name}
        </div>
        <div style={{ fontFamily: "Montserrat, sans-serif", fontSize: 20, color: "#CBD5E1", marginTop: 8, marginBottom: 18 }}>
          {props.subheadline || target.desc}
        </div>
        {props.primaryImageUrl && (
          <div style={{ borderRadius: 12, overflow: "hidden", border: "1px solid rgba(255,255,255,0.2)", height: 340 }}>
            <Img
              src={props.primaryImageUrl}
              style={{
                width: "100%",
                height: "100%",
                objectFit: "cover",
                transform: `scale(${1 + frame * 0.0012})`,
              }}
            />
          </div>
        )}
      </div>
    </AbsoluteFill>
  );
};

const CharacterDossierView: React.FC<{ props: SceneProps; frame: number; fps: number }> = ({ props, frame, fps }) => {
  const slideIn = spring({ frame, fps, config: { damping: 14, stiffness: 100 } });
  const facts = props.characterFacts && props.characterFacts.length > 0
    ? props.characterFacts
    : [props.subheadline || "Personagem confirmado no universo de Leonida"];

  return (
    <AbsoluteFill style={{ background: "#090B12" }}>
      {/* Fundo em blur escuro da própria arte */}
      {props.primaryImageUrl && (
        <Img
          src={props.primaryImageUrl}
          style={{
            position: "absolute",
            width: "100%",
            height: "100%",
            objectFit: "cover",
            filter: "blur(28px) brightness(0.28)",
            transform: "scale(1.1)",
          }}
        />
      )}

      <div
        style={{
          position: "absolute",
          top: 118,
          left: 64,
          right: 64,
          bottom: 130,
          display: "flex",
          gap: 44,
          alignItems: "stretch",
        }}
      >
        {/* Painel Esquerdo: Retrato 4K com zoom suave */}
        <div
          style={{
            flex: "0 0 880px",
            borderRadius: 20,
            overflow: "hidden",
            border: "2px solid rgba(255, 42, 133, 0.7)",
            boxShadow: "0 20px 60px rgba(0,0,0,0.85)",
            position: "relative",
            transform: `translateX(${(1 - slideIn) * -80}px)`,
            opacity: slideIn,
          }}
        >
          {props.primaryImageUrl && (
            <Img
              src={props.primaryImageUrl}
              style={{
                width: "100%",
                height: "100%",
                objectFit: "cover",
                transform: `scale(${1.02 + frame * 0.001})`,
              }}
            />
          )}
          <div
            style={{
              position: "absolute",
              bottom: 0,
              left: 0,
              right: 0,
              padding: "28px 32px",
              background: "linear-gradient(0deg, rgba(9,11,18,0.96) 0%, transparent 100%)",
            }}
          >
            <div style={{ fontFamily: "JetBrains Mono, monospace", color: "#FF2A85", fontSize: 16, fontWeight: 700 }}>
              DOSSIÊ DE PERSONAGEM // LEONIDA DB
            </div>
            <div style={{ fontFamily: "Bebas Neue, Impact, sans-serif", fontSize: 64, color: "#FFF", lineHeight: 1 }}>
              {props.characterName || props.headline}
            </div>
          </div>
        </div>

        {/* Painel Direito: Ficha Editorial Animada */}
        <div
          style={{
            flex: 1,
            background: "rgba(15, 19, 32, 0.88)",
            border: "1px solid rgba(255,255,255,0.14)",
            borderRadius: 20,
            padding: "36px 40px",
            display: "flex",
            flexDirection: "column",
            justifyContent: "center",
            gap: 22,
          }}
        >
          <div style={{ fontFamily: "JetBrains Mono, monospace", color: "#00F0FF", fontSize: 18, letterSpacing: "0.06em" }}>
            {props.characterRole || "PERFIL OFICIAL"}
          </div>
          <div style={{ fontFamily: "Bebas Neue, Impact, sans-serif", fontSize: 52, color: "#F8FAFC", lineHeight: 1.05 }}>
            {props.headline}
          </div>
          <div style={{ display: "flex", flexDirection: "column", gap: 16, marginTop: 8 }}>
            {facts.map((f, i) => {
              const itemSpring = spring({
                frame: Math.max(0, frame - 12 - i * 10),
                fps,
                config: { damping: 15, stiffness: 120 },
              });
              return (
                <div
                  key={i}
                  style={{
                    background: "rgba(255,255,255,0.05)",
                    borderLeft: "4px solid #FFB800",
                    padding: "16px 20px",
                    borderRadius: "0 12px 12px 0",
                    fontFamily: "Montserrat, sans-serif",
                    fontSize: 22,
                    fontWeight: 600,
                    color: "#E2E8F0",
                    transform: `translateX(${(1 - itemSpring) * 50}px)`,
                    opacity: itemSpring,
                  }}
                >
                  {f}
                </div>
              );
            })}
          </div>
        </div>
      </div>
    </AbsoluteFill>
  );
};

const DataComparison3DView: React.FC<{ props: SceneProps; frame: number; fps: number }> = ({ props, frame, fps }) => {
  const items = props.comparisonItems && props.comparisonItems.length > 0
    ? props.comparisonItems
    : [
        { label: "GTA V (2013)", value: 48, display: "Base de comparação" },
        { label: "GTA VI (2026)", value: 100, display: props.statValue || "Novo padrão Rockstar" },
      ];

  return (
    <AbsoluteFill style={{ background: "radial-gradient(circle at 25% 50%, #1A1030 0%, #090B12 100%)" }}>
      {props.primaryImageUrl && (
        <Img
          src={props.primaryImageUrl}
          style={{
            position: "absolute",
            width: "100%",
            height: "100%",
            objectFit: "cover",
            opacity: 0.16,
            filter: "grayscale(30%) blur(6px)",
          }}
        />
      )}

      {/* Elemento 3D Real via Three.js (@remotion/three) */}
      <div style={{ position: "absolute", left: 40, top: 120, width: 640, height: 780 }}>
        <ThreeCanvas width={640} height={780}>
          <RotatingPrism3D frame={frame} color="#FF2A85" />
        </ThreeCanvas>
        <div
          style={{
            position: "absolute",
            inset: 0,
            display: "flex",
            flexDirection: "column",
            alignItems: "center",
            justifyContent: "center",
            pointerEvents: "none",
          }}
        >
          <div
            style={{
              fontFamily: "Bebas Neue, Impact, sans-serif",
              fontSize: 112,
              color: "#FFB800",
              textShadow: "0 0 32px rgba(255,184,0,0.6), 0 6px 16px #000",
              lineHeight: 0.95,
            }}
          >
            {props.statValue || "GTA VI"}
          </div>
          <div
            style={{
              fontFamily: "JetBrains Mono, monospace",
              fontSize: 22,
              fontWeight: 800,
              color: "#00F0FF",
              background: "rgba(9,11,18,0.85)",
              padding: "6px 18px",
              borderRadius: 8,
              border: "1px solid #00F0FF",
              marginTop: 10,
            }}
          >
            {props.statUnit || "DADO VERIFICADO"}
          </div>
        </div>
      </div>

      {/* Gráfico Comparativo Editorial à Direita */}
      <div
        style={{
          position: "absolute",
          left: 700,
          right: 72,
          top: 150,
          bottom: 150,
          background: "rgba(15, 19, 32, 0.88)",
          border: "1px solid rgba(255,255,255,0.14)",
          borderRadius: 22,
          padding: "42px 48px",
          display: "flex",
          flexDirection: "column",
          justifyContent: "center",
          gap: 28,
        }}
      >
        <div>
          <div style={{ fontFamily: "JetBrains Mono, monospace", color: "#FF2A85", fontSize: 17, fontWeight: 700 }}>
            {props.statLabel || "ANÁLISE COMPARATIVA & TELEMETRIA"}
          </div>
          <div style={{ fontFamily: "Bebas Neue, Impact, sans-serif", fontSize: 58, color: "#F8FAFC", lineHeight: 1.02 }}>
            {props.headline}
          </div>
          <div style={{ fontFamily: "Montserrat, sans-serif", fontSize: 21, color: "#94A3B8", marginTop: 6 }}>
            {props.subheadline}
          </div>
        </div>

        <div style={{ display: "flex", flexDirection: "column", gap: 24 }}>
          {items.map((it, idx) => {
            const p = spring({ frame: Math.max(0, frame - 10 - idx * 12), fps, config: { damping: 16, stiffness: 90 } });
            const wPct = Math.max(12, Math.min(100, it.value * p));
            const isHighlight = idx === items.length - 1;
            return (
              <div key={idx} style={{ display: "flex", flexDirection: "column", gap: 8 }}>
                <div style={{ display: "flex", justifyContent: "space-between", fontFamily: "Montserrat, sans-serif", fontSize: 22, fontWeight: 800 }}>
                  <span style={{ color: isHighlight ? "#FFB800" : "#E2E8F0" }}>{it.label}</span>
                  <span style={{ fontFamily: "JetBrains Mono, monospace", color: isHighlight ? "#00F0FF" : "#94A3B8" }}>
                    {it.display}
                  </span>
                </div>
                <div style={{ width: "100%", height: 28, background: "rgba(255,255,255,0.08)", borderRadius: 14, overflow: "hidden" }}>
                  <div
                    style={{
                      width: `${wPct}%`,
                      height: "100%",
                      borderRadius: 14,
                      background: isHighlight
                        ? "linear-gradient(90deg, #FF2A85 0%, #FFB800 100%)"
                        : "linear-gradient(90deg, #334155 0%, #64748B 100%)",
                      boxShadow: isHighlight ? "0 0 20px rgba(255,42,133,0.6)" : "none",
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

const FeatureSpotlightView: React.FC<{ props: SceneProps; frame: number; fps: number }> = ({ props, frame, fps }) => {
  const zoom = interpolate(frame, [0, 150], [1.0, 1.12], { extrapolateRight: "clamp" });
  const panelIn = spring({ frame: Math.max(0, frame - 8), fps, config: { damping: 16, stiffness: 110 } });

  return (
    <AbsoluteFill style={{ background: "#090B12" }}>
      {props.primaryImageUrl && (
        <Img
          src={props.primaryImageUrl}
          style={{
            width: "100%",
            height: "100%",
            objectFit: "cover",
            transform: `scale(${zoom})`,
          }}
        />
      )}
      {/* Vinheta cinematográfica */}
      <div
        style={{
          position: "absolute",
          inset: 0,
          background:
            "linear-gradient(90deg, rgba(9,11,18,0.88) 0%, rgba(9,11,18,0.22) 52%, rgba(9,11,18,0.65) 100%), linear-gradient(0deg, rgba(9,11,18,0.92) 0%, transparent 35%)",
        }}
      />

      {/* Lower-third / Card lateral de análise técnica */}
      <div
        style={{
          position: "absolute",
          left: 64,
          bottom: 148,
          maxWidth: 780,
          background: "rgba(12, 16, 28, 0.86)",
          borderLeft: "6px solid #FF2A85",
          borderTop: "1px solid rgba(255,255,255,0.15)",
          borderRight: "1px solid rgba(255,255,255,0.15)",
          borderBottom: "1px solid rgba(255,255,255,0.15)",
          backdropFilter: "blur(14px)",
          padding: "26px 36px",
          borderRadius: "0 18px 18px 0",
          transform: `translateX(${(1 - panelIn) * -90}px)`,
          opacity: panelIn,
          boxShadow: "0 20px 50px rgba(0,0,0,0.75)",
        }}
      >
        <div style={{ fontFamily: "JetBrains Mono, monospace", fontSize: 16, color: "#00F0FF", fontWeight: 700, letterSpacing: "0.08em" }}>
          INSPEÇÃO VISUAL // DETALHE EM DESTAQUE
        </div>
        <div style={{ fontFamily: "Bebas Neue, Impact, sans-serif", fontSize: 58, color: "#F8FAFC", lineHeight: 1.02, marginTop: 4 }}>
          {props.headline}
        </div>
        <div style={{ fontFamily: "Montserrat, sans-serif", fontSize: 22, color: "#E2E8F0", marginTop: 8, fontWeight: 500 }}>
          {props.subheadline}
        </div>
      </div>
    </AbsoluteFill>
  );
};

export const GtaStudioScene: React.FC<SceneProps> = (props) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  return (
    <AbsoluteFill style={{ backgroundColor: "#090B12", overflow: "hidden" }}>
      {props.sceneType === "map_zoom" && <MapZoomView props={props} frame={frame} fps={fps} />}
      {props.sceneType === "character_dossier" && <CharacterDossierView props={props} frame={frame} fps={fps} />}
      {props.sceneType === "data_comparison" && <DataComparison3DView props={props} frame={frame} fps={fps} />}
      {(props.sceneType === "feature_spotlight" || props.sceneType === "chapter_card") && (
        <FeatureSpotlightView props={props} frame={frame} fps={fps} />
      )}
      <TopEditorialHUD props={props} frame={frame} fps={fps} />
      <WordByWordCaptions words={props.words} frame={frame} fps={fps} />
    </AbsoluteFill>
  );
};
