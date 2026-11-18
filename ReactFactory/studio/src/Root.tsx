import React from "react";
import { Composition } from "remotion";
import { GtaStudioScene, SceneProps } from "./GtaStudioComp";

const defaultProps: SceneProps = {
  sceneType: "map_zoom",
  badgeType: "OFICIAL",
  sourceLabel: "Rockstar Games Official / rockstargames.com/VI",
  actNum: 1,
  totalActs: 5,
  actTitle: "O MAPA DE LEONIDA E VICE CITY",
  headline: "6 REGIÕES CONFIRMADAS EM LEONIDA",
  subheadline: "Do arquipélago de Leonida Keys às montanhas de Mount Kalaga",
  locationKey: "vice_city",
  characterName: "LUCIA & JASON",
  characterRole: "Protagonistas Centrais — Estado de Leonida",
  characterFacts: [
    "Primeiro casal protagonista desde o GTA clássico",
    "Sistema de troca dinâmica e assaltos coordenados",
    "Fuga pelo interior de Leonida após golpe dar errado"
  ],
  statValue: "19 NOV",
  statUnit: "QUINTA-FEIRA • 00:00",
  statLabel: "LANÇAMENTO GLOBAL CONFIRMADO PELA ROCKSTAR",
  comparisonItems: [
    { label: "GTA V (Los Santos - 2013)", value: 45, display: "76 km² • 1 Cidade" },
    { label: "GTA VI (Estado de Leonida - 2026)", value: 100, display: "6 Regiões • Vice City + Interior" }
  ],
  primaryImageUrl: "",
  secondaryImageUrl: "",
  words: [
    { w: "Faltam", s: 0.0, e: 0.5 },
    { w: "menos", s: 0.5, e: 0.9 },
    { w: "de", s: 0.9, e: 1.1 },
    { w: "48", s: 1.1, e: 1.6 },
    { w: "horas", s: 1.6, e: 2.2 }
  ]
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
    </>
  );
};
