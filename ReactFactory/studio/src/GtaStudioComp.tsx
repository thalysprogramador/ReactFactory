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
  OFICIAL: { label: "FONTE OFICIAL ROCKSTAR", color: "#10B981", bg: "rgba(16, 185, 129, 0.14)" },
  CONFIRMADO: { label: "CONFIRMADO POR FONTES", color: "#38BDF8", bg: "rgba(56, 189, 248, 0.14)" },
  RUMOR: { label: "RUMOR • NÃO OFICIAL", color: "#F59E0B", bg: "rgba(245, 158, 11, 0.16)" },
  TEORIA: { label: "ANÁLISE TÉCNICA & COMUNIDADE", color: "#A78BFA", bg: "rgba(167, 139, 250, 0.16)" },
};

const LEONIDA_REGIONS: Record<string, { name: string; coords: string; x: number; y: number; desc: string }> = {
  vice_city: { name: "VICE CITY", coords: "25.7617° N • 80.1918° W", x: 0.72, y: 0.58, desc: "Metrópole costeira, Ocean Beach, Vice Beach e centro financeiro" },
  leonida_keys: { name: "LEONIDA KEYS", coords: "24.5551° N • 81.7800° W", x: 0.54, y: 0.84, desc: "Arquipélago tropical sul, pontes oceânicas e recifes" },
  grassrivers: { name: "GRASSRIVERS", coords: "25.8500° N • 80.9300° W", x: 0.52, y: 0.66, desc: "Bioma de pântanos, manguezais e fauna selvagem" },
  port_gellhorn: { name: "PORT GELLHORN", coords: "26.6406° N • 81.8723° W", x: 0.30, y: 0.50, desc: "Zona portuária industrial na costa oeste de Leonida" },
  ambrosia: { name: "AMBROSIA", coords: "26.7500° N • 80.6500° W", x: 0.53, y: 0.42, desc: "Polo industrial central e refinarias do interior" },
  mount_kalaga: { name: "MOUNT KALAGA", coords: "30.4383° N • 83.2000° W", x: 0.43, y: 0.20, desc: "Parque nacional montanhoso na fronteira norte" },
};

const EditorialGlobe3D: React.FC<{ frame: number }> = ({ frame }) => {
  const rotY = frame * 0.018;
  const rotX = Math.sin(frame * 0.015) * 0.22;
  return (
    <group rotation={[rotX, rotY, 0]}>
      <mesh>
        <icosahedronGeometry args={[1.95, 1]} />
        <meshStandardMaterial color="#F59E0B" wireframe emissive="#F59E0B" emissiveIntensity={0.35} />
      </mesh>
      <mesh scale={[0.72, 0.72, 0.72]} rotation={[0, -rotY * 1.4, 0]}>
        <octahedronGeometry args={[1.5, 0]} />
        <meshStandardMaterial color="#38BDF8" wireframe emissive="#38BDF8" emissiveIntensity={0.25} />
      </mesh>
      <ambientLight intensity={1.1} />
      <pointLight position={[6, 6, 6]} intensity={2.0} color="#F59E0B" />
    </group>
  );
};

const TopEditorialHUD: React.FC<{ props: SceneProps; frame: number; fps: number }> = ({ props, frame, fps }) => {
  const badge = BADGE_STYLES[props.badgeType] || BADGE_STYLES.OFICIAL;
  const enter = spring({ frame, fps, config: { damping: 20, stiffness: 110 } });
  const progWidth = ((props.actNum || 1) / Math.max(1, props.totalActs || 5)) * 100;

  return (
    <div style={{ position: "absolute", top: 0, left: 0, right: 0, zIndex: 30 }}>
      <div style={{ width: "100%", height: 4, background: "rgba(255,255,255,0.06)" }}>
        <div
          style={{
            width: `${progWidth}%`,
            height: "100%",
            background: "linear-gradient(90deg, #F59E0B 0%, #38BDF8 100%)",
          }}
        />
      </div>

      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          padding: "22px 52px",
          transform: `translateY(${(1 - enter) * -24}px)`,
          opacity: enter,
        }}
      >
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: 12,
            background: "rgba(10, 12, 18, 0.86)",
            border: "1px solid rgba(255,255,255,0.14)",
            borderLeft: `3px solid ${badge.color}`,
            backdropFilter: "blur(16px)",
            padding: "8px 16px",
            borderRadius: 6,
          }}
        >
          <div
            style={{
              width: 8,
              height: 8,
              borderRadius: "50%",
              background: badge.color,
            }}
          />
          <span
            style={{
              fontFamily: "JetBrains Mono, Consolas, monospace",
              fontSize: 14,
              fontWeight: 700,
              letterSpacing: "0.08em",
              color: badge.color,
            }}
          >
            {badge.label}
          </span>
          <span
            style={{
              fontFamily: "Montserrat, Segoe UI, sans-serif",
              fontSize: 13,
              color: "#94A3B8",
              borderLeft: "1px solid rgba(255,255,255,0.14)",
              paddingLeft: 12,
            }}
          >
            {props.sourceLabel}
          </span>
        </div>

        <div
          style={{
            background: "rgba(10, 12, 18, 0.84)",
            border: "1px solid rgba(255,255,255,0.12)",
            padding: "8px 16px",
            borderRadius: 6,
            fontFamily: "JetBrains Mono, Consolas, monospace",
            fontSize: 13,
            color: "#94A3B8",
            letterSpacing: "0.06em",
          }}
        >
          CAPÍTULO 0{props.actNum} • <strong style={{ color: "#F8FAFC" }}>{props.actTitle}</strong>
        </div>
      </div>
    </div>
  );
};

const MapZoomView: React.FC<{ props: SceneProps; frame: number; fps: number }> = ({ props, frame, fps }) => {
  const key = (props.locationKey || "vice_city").toLowerCase();
  const target = LEONIDA_REGIONS[key] || LEONIDA_REGIONS.vice_city;

  const camProgress = spring({ frame, fps, config: { damping: 24, stiffness: 45 } });
  const zoom = interpolate(camProgress, [0, 1], [1.0, 1.38]);
  const offsetX = interpolate(camProgress, [0, 1], [0, (0.52 - target.x) * 460]);
  const offsetY = interpolate(camProgress, [0, 1], [0, (0.52 - target.y) * 340]);
  const cardIn = spring({ frame: Math.max(0, frame - 8), fps, config: { damping: 18, stiffness: 90 } });

  return (
    <AbsoluteFill style={{ background: "radial-gradient(circle at 35% 50%, #111827 0%, #07090E 100%)" }}>
      <div
        style={{
          position: "absolute",
          left: 48,
          top: 96,
          width: 1060,
          height: 820,
          overflow: "hidden",
          borderRadius: 14,
          border: "1px solid rgba(255, 255, 255, 0.12)",
          background: "rgba(9, 13, 22, 0.85)",
          backgroundImage:
            "linear-gradient(rgba(255, 255, 255, 0.04) 1px, transparent 1px), linear-gradient(90deg, rgba(255, 255, 255, 0.04) 1px, transparent 1px)",
          backgroundSize: "48px 48px",
        }}
      >
        <svg
          width="1060"
          height="820"
          viewBox="0 0 1100 820"
          style={{
            transform: `translate(${offsetX}px, ${offsetY}px) scale(${zoom})`,
            transformOrigin: "center center",
          }}
        >
          <path
            d="M 280 80 L 620 95 L 780 250 L 920 470 L 860 610 L 640 720 L 460 740 L 540 590 L 390 520 L 240 390 L 280 230 Z"
            fill="rgba(56, 189, 248, 0.05)"
            stroke="rgba(56, 189, 248, 0.45)"
            strokeWidth="2"
          />
          <ellipse cx="580" cy="365" rx="82" ry="60" fill="rgba(56, 189, 248, 0.09)" stroke="rgba(56, 189, 248, 0.35)" strokeWidth="1.5" />
          {Object.entries(LEONIDA_REGIONS).map(([rk, reg]) => {
            const cx = 120 + reg.x * 820;
            const cy = 40 + reg.y * 710;
            const isTarget = rk === key;
            const pulseR = 14 + (frame % 48) * 1.1;
            const pulseOp = Math.max(0, 1 - (frame % 48) / 48);
            return (
              <g key={rk}>
                {isTarget && (
                  <>
                    <circle cx={cx} cy={cy} r={pulseR} fill="none" stroke="#F59E0B" strokeWidth="2" opacity={pulseOp} />
                    <circle cx={cx} cy={cy} r={24} fill="rgba(245, 158, 11, 0.15)" stroke="#F59E0B" strokeWidth="1.5" />
                  </>
                )}
                <circle cx={cx} cy={cy} r={isTarget ? 7 : 4.5} fill={isTarget ? "#F59E0B" : "#64748B"} />
                <text
                  x={cx + 14}
                  y={cy + 5}
                  fill={isTarget ? "#F8FAFC" : "rgba(148,163,184,0.75)"}
                  fontFamily="JetBrains Mono, monospace"
                  fontWeight="700"
                  fontSize={isTarget ? "17" : "12"}
                >
                  {reg.name}
                </text>
              </g>
            );
          })}
        </svg>
      </div>

      <div
        style={{
          position: "absolute",
          right: 52,
          top: 124,
          width: 700,
          background: "rgba(12, 15, 24, 0.92)",
          border: "1px solid rgba(255,255,255,0.14)",
          borderTop: "3px solid #F59E0B",
          borderRadius: 12,
          padding: 32,
          boxShadow: "0 24px 60px rgba(0,0,0,0.75)",
          transform: `translateX(${(1 - cardIn) * 80}px)`,
          opacity: cardIn,
        }}
      >
        <div style={{ fontFamily: "JetBrains Mono, monospace", color: "#F59E0B", fontSize: 14, letterSpacing: "0.08em", marginBottom: 8 }}>
          CARTOMETRIA OFICIAL • {target.coords}
        </div>
        <div
          style={{
            fontFamily: "Bebas Neue, Impact, sans-serif",
            fontSize: 52,
            color: "#F8FAFC",
            letterSpacing: "0.03em",
            lineHeight: 1.02,
          }}
        >
          {props.headline || target.name}
        </div>
        <div style={{ fontFamily: "Montserrat, sans-serif", fontSize: 18, color: "#94A3B8", marginTop: 10, marginBottom: 22, lineHeight: 1.4 }}>
          {props.subheadline || target.desc}
        </div>
        {props.primaryImageUrl && (
          <div style={{ borderRadius: 10, overflow: "hidden", border: "1px solid rgba(255,255,255,0.14)", height: 350 }}>
            <Img
              src={props.primaryImageUrl}
              style={{
                width: "100%",
                height: "100%",
                objectFit: "cover",
                transform: `scale(${1 + frame * 0.0008})`,
              }}
            />
          </div>
        )}
      </div>
    </AbsoluteFill>
  );
};

const CharacterDossierView: React.FC<{ props: SceneProps; frame: number; fps: number }> = ({ props, frame, fps }) => {
  const slideIn = spring({ frame, fps, config: { damping: 18, stiffness: 90 } });
  const facts = props.characterFacts && props.characterFacts.length > 0
    ? props.characterFacts
    : [props.subheadline || "Personagem confirmado no estado de Leonida"];

  return (
    <AbsoluteFill style={{ background: "#07090E" }}>
      {props.primaryImageUrl && (
        <Img
          src={props.primaryImageUrl}
          style={{
            position: "absolute",
            width: "100%",
            height: "100%",
            objectFit: "cover",
            filter: "blur(36px) brightness(0.24)",
            transform: "scale(1.08)",
          }}
        />
      )}

      <div
        style={{
          position: "absolute",
          top: 112,
          left: 56,
          right: 56,
          bottom: 112,
          display: "flex",
          gap: 40,
          alignItems: "stretch",
        }}
      >
        <div
          style={{
            flex: "0 0 880px",
            borderRadius: 14,
            overflow: "hidden",
            border: "1px solid rgba(255, 255, 255, 0.16)",
            boxShadow: "0 24px 60px rgba(0,0,0,0.8)",
            position: "relative",
            transform: `translateX(${(1 - slideIn) * -60}px)`,
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
                transform: `scale(${1.01 + frame * 0.0007})`,
              }}
            />
          )}
          <div
            style={{
              position: "absolute",
              bottom: 0,
              left: 0,
              right: 0,
              padding: "32px 36px",
              background: "linear-gradient(0deg, rgba(7,9,14,0.95) 0%, transparent 100%)",
            }}
          >
            <div style={{ fontFamily: "JetBrains Mono, monospace", color: "#F59E0B", fontSize: 14, fontWeight: 700, letterSpacing: "0.08em" }}>
              PERFIL EDITORIAL • GRAND THEFT AUTO VI
            </div>
            <div style={{ fontFamily: "Bebas Neue, Impact, sans-serif", fontSize: 60, color: "#F8FAFC", lineHeight: 1.02, marginTop: 4 }}>
              {props.characterName || props.headline}
            </div>
          </div>
        </div>

        <div
          style={{
            flex: 1,
            background: "rgba(12, 15, 24, 0.90)",
            border: "1px solid rgba(255,255,255,0.12)",
            borderRadius: 14,
            padding: "38px 42px",
            display: "flex",
            flexDirection: "column",
            justifyContent: "center",
            gap: 20,
          }}
        >
          <div style={{ fontFamily: "JetBrains Mono, monospace", color: "#38BDF8", fontSize: 15, letterSpacing: "0.08em" }}>
            {props.characterRole || "ARQUIVO DE PERSONAGEM"}
          </div>
          <div style={{ fontFamily: "Bebas Neue, Impact, sans-serif", fontSize: 48, color: "#F8FAFC", lineHeight: 1.05 }}>
            {props.headline}
          </div>
          <div style={{ display: "flex", flexDirection: "column", gap: 14, marginTop: 6 }}>
            {facts.map((f, i) => {
              const itemSpring = spring({
                frame: Math.max(0, frame - 10 - i * 8),
                fps,
                config: { damping: 18, stiffness: 100 },
              });
              return (
                <div
                  key={i}
                  style={{
                    background: "rgba(255,255,255,0.03)",
                    borderLeft: "3px solid #F59E0B",
                    padding: "14px 18px",
                    borderRadius: "0 8px 8px 0",
                    fontFamily: "Montserrat, sans-serif",
                    fontSize: 20,
                    fontWeight: 500,
                    color: "#E2E8F0",
                    transform: `translateX(${(1 - itemSpring) * 36}px)`,
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
        { label: "GTA V (2013)", value: 45, display: "Escopo Base" },
        { label: "GTA VI (2026)", value: 100, display: props.statValue || "Nova Geração Rockstar" },
      ];

  return (
    <AbsoluteFill style={{ background: "radial-gradient(circle at 25% 50%, #111827 0%, #07090E 100%)" }}>
      {props.primaryImageUrl && (
        <Img
          src={props.primaryImageUrl}
          style={{
            position: "absolute",
            width: "100%",
            height: "100%",
            objectFit: "cover",
            opacity: 0.14,
            filter: "grayscale(40%) blur(10px)",
          }}
        />
      )}

      <div style={{ position: "absolute", left: 48, top: 120, width: 620, height: 780 }}>
        <ThreeCanvas width={620} height={780}>
          <EditorialGlobe3D frame={frame} />
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
              fontSize: 104,
              color: "#F8FAFC",
              textShadow: "0 8px 24px rgba(0,0,0,0.9)",
              lineHeight: 0.95,
            }}
          >
            {props.statValue || "GTA VI"}
          </div>
          <div
            style={{
              fontFamily: "JetBrains Mono, monospace",
              fontSize: 18,
              fontWeight: 700,
              color: "#F59E0B",
              background: "rgba(10,12,18,0.90)",
              padding: "6px 16px",
              borderRadius: 6,
              border: "1px solid rgba(245,158,11,0.45)",
              marginTop: 10,
            }}
          >
            {props.statUnit || "DADO VERIFICADO"}
          </div>
        </div>
      </div>

      <div
        style={{
          position: "absolute",
          left: 700,
          right: 64,
          top: 140,
          bottom: 140,
          background: "rgba(12, 15, 24, 0.90)",
          border: "1px solid rgba(255,255,255,0.12)",
          borderRadius: 14,
          padding: "42px 48px",
          display: "flex",
          flexDirection: "column",
          justifyContent: "center",
          gap: 26,
        }}
      >
        <div>
          <div style={{ fontFamily: "JetBrains Mono, monospace", color: "#F59E0B", fontSize: 15, fontWeight: 700, letterSpacing: "0.08em" }}>
            {props.statLabel || "COMPARATIVO TÉCNICO & ESCALA"}
          </div>
          <div style={{ fontFamily: "Bebas Neue, Impact, sans-serif", fontSize: 54, color: "#F8FAFC", lineHeight: 1.04, marginTop: 4 }}>
            {props.headline}
          </div>
          <div style={{ fontFamily: "Montserrat, sans-serif", fontSize: 19, color: "#94A3B8", marginTop: 6 }}>
            {props.subheadline}
          </div>
        </div>

        <div style={{ display: "flex", flexDirection: "column", gap: 22 }}>
          {items.map((it, idx) => {
            const p = spring({ frame: Math.max(0, frame - 8 - idx * 10), fps, config: { damping: 18, stiffness: 80 } });
            const wPct = Math.max(10, Math.min(100, it.value * p));
            const isHighlight = idx === items.length - 1;
            return (
              <div key={idx} style={{ display: "flex", flexDirection: "column", gap: 8 }}>
                <div style={{ display: "flex", justifyContent: "space-between", fontFamily: "Montserrat, sans-serif", fontSize: 20, fontWeight: 700 }}>
                  <span style={{ color: isHighlight ? "#F8FAFC" : "#94A3B8" }}>{it.label}</span>
                  <span style={{ fontFamily: "JetBrains Mono, monospace", color: isHighlight ? "#F59E0B" : "#64748B" }}>
                    {it.display}
                  </span>
                </div>
                <div style={{ width: "100%", height: 20, background: "rgba(255,255,255,0.06)", borderRadius: 10, overflow: "hidden" }}>
                  <div
                    style={{
                      width: `${wPct}%`,
                      height: "100%",
                      borderRadius: 10,
                      background: isHighlight
                        ? "linear-gradient(90deg, #F59E0B 0%, #38BDF8 100%)"
                        : "linear-gradient(90deg, #334155 0%, #475569 100%)",
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
    <AbsoluteFill style={{ backgroundColor: "#07090E", overflow: "hidden" }}>
      {props.sceneType === "map_zoom" && <MapZoomView props={props} frame={frame} fps={fps} />}
      {props.sceneType === "character_dossier" && <CharacterDossierView props={props} frame={frame} fps={fps} />}
      {(props.sceneType === "data_comparison" || props.sceneType === "feature_spotlight" || props.sceneType === "chapter_card") && (
        <DataComparison3DView props={props} frame={frame} fps={fps} />
      )}
      <TopEditorialHUD props={props} frame={frame} fps={fps} />
    </AbsoluteFill>
  );
};
