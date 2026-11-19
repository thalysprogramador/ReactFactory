import React from "react";
import { Composition } from "remotion";
import { GtaStudioScene, SceneProps } from "./GtaStudioComp";
import { GtaThumbnail3D, Thumb3DProps } from "./GtaThumbnail3D";

const defaultProps: SceneProps = {
  sceneType: "map_zoom",
  badgeType: "OFICIAL",
  sourceLabel: "Live Gameplayrj (Davy Jones) & Bistecone • GTA VI",
  actNum: 1,
  totalActs: 5,
  actTitle: "PRIMEIRAS HORAS EM VICE CITY",
  headline: "VICE CITY & LEONIDA KEYS",
  subheadline: "O mapa real de Leonida explorado ao vivo nas primeiras horas de GTA 6",
  locationKey: "vice_city",
  characterName: "LUCIA & JASON",
  characterRole: "Protagonistas Centrais — Estado de Leonida",
  characterFacts: [
    "Início na penitenciária de Leonida e fuga para Vice City",
    "Sistema de troca dinâmica e assaltos coordenados",
    "Celular com redes sociais e apps interativos em tempo real"
  ],
  statValue: "9.4M+",
  statUnit: "VIEWS NAS LIVES DE LANÇAMENTO",
  statLabel: "IMPACTO GLOBAL NAS PRIMEIRAS HORAS",
  comparisonItems: [
    { label: "GTA V (Los Santos - 2013)", value: 42, display: "76 km² • 1 Cidade" },
    { label: "GTA VI (Estado de Leonida - 2026)", value: 100, display: "175 km² • 6 Regiões" }
  ],
  primaryImageUrl: "",
  secondaryImageUrl: "",
  words: []
};

const defaultThumbProps: Thumb3DProps = {
  heroImageUrl: "",
  line1: "BUGS ABSURDOS",
  line2: "NO GTA 6!",
  subline: "O QUE ACABARAM DE DESCOBRIR EM VICE CITY",
  accentColor: "#FFBE0B"
};

export const RemotionRoot: React.FC = () => {
  return (
    <>
      <Composition
        id="GtaStudioScene"
        component={GtaStudioScene}
        durationInFrames={150}
        fps={24}
        width={1920}
        height={1080}
        defaultProps={defaultProps}
      />
      <Composition
        id="GtaShortOverlay"
        component={GtaStudioScene}
        durationInFrames={150}
        fps={24}
        width={1080}
        height={1920}
        defaultProps={{ ...defaultProps, isVertical: true }}
      />
      <Composition
        id="GtaThumbnail3D"
        component={GtaThumbnail3D}
        durationInFrames={2}
        fps={24}
        width={1280}
        height={720}
        defaultProps={defaultThumbProps}
      />
    </>
  );
};
