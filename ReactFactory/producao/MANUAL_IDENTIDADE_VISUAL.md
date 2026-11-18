# Manual de Identidade Visual & Direção Editorial — *Dossiê Leonida (GTA 6)*

## 1. Conceito Editorial: *Vice Pulse Editorial*
A identidade visual deixa de lado caixas genéricas e templates amadores para assumir a estética de um **documentário investigativo e tecnológico de games** (inspirado no rigor gráfico de canais como *Digital Foundry*, *IGN Specials*, *Vox* e *GTA Series Videos*, adaptado ao universo solar e noturno do estado de **Leonida**).

---

## 2. Paleta de Cores Oficial
| Papel | Nome | Hex | Uso obrigatório |
| :--- | :--- | :--- | :--- |
| Fundo Principal | **Deep Leonida Night** | `#090B12` | Fundo de infográficos, letterbox e painéis |
| Painel Translúcido | **Tactical Slate Glass** | `rgba(15,19,32,0.86)` | Lower-thirds, dossiês de personagens e cards |
| Destaque Primário | **Vice Sunset Magenta** | `#FF2A85` | Barras de energia, acentos principais, cortes |
| Destaque Técnico | **Ocean Drive Cyan** | `#00F0FF` | Telemetria, mapas, coordenadas e dados |
| Destaque de Retenção | **Leonida Amber** | `#FFB800` | Palavras-chave ativas na legenda e números |
| Selo Oficial | **Verified Emerald** | `#00E676` | Tag `[FONTE OFICIAL ROCKSTAR]` |
| Selo Rumor | **Alert Orange** | `#FF6D00` | Tag `[RUMOR / NÃO OFICIAL]` |
| Selo Teoria | **Speculation Violet** | `#B388FF` | Tag `[ANÁLISE & TEORIA DA COMUNIDADE]` |

---

## 3. Tipografia
1. **Títulos de Impacto e Capítulos:** `Bebas Neue` / `Anton` (Caixa alta, tracking `+0.04em`, sombra projetada suave).
2. **Legendas Sincronizadas e Infográficos:** `Montserrat ExtraBold` / `Inter Black` (Leitura instantânea em telas móveis e TVs).
3. **Telemetria, Datas, Coordenadas e Selos de Fonte:** `JetBrains Mono` (Estética de dossiê tático e precisão jornalística).

---

## 4. Sistema Obrigatório de Classificação de Informação (Anti-Fake News)
Todo bloco narrativo exibe no canto superior um selo de verificação gerado automaticamente pelo **Agente 2 (Pesquisador)** e renderizado pelo **Agente 3 (Editor)**:
- 🟢 **`[FONTE OFICIAL ROCKSTAR]`** — Trailers oficiais, Rockstar Newswire, site oficial `rockstargames.com/VI`.
- 🔵 **`[CONFIRMADO POR FONTES]`** — Relatórios financeiros da Take-Two, entrevistas oficiais, classificações indicativas.
- 🟠 **`[RUMOR / NÃO OFICIAL]`** — Vazamentos não confirmados (sempre narrados no condicional).
- 🟣 **`[ANÁLISE & TEORIA DA COMUNIDADE]`** — Hipóteses de fãs, mapeamento colaborativo e especulações.

---

## 5. Linguagem de Motion Graphics & 3D (Remotion + Three.js)
As animações nunca são decorativas; elas respondem ao tipo semântico de cada trecho do roteiro (`scene_type`):
1. **`map_zoom` (Localização citada):** Mapa tático 2.5D/3D de Leonida com câmera viajando até a região citada (`Vice City`, `Leonida Keys`, `Grassrivers`, `Port Gellhorn`, `Ambrosia`, `Mount Kalaga`), radar pulsante, coordenadas GPS e janela PiP com imagem real da região.
2. **`character_dossier` (Personagem citado):** Composição split-screen com retrato 4K em parallax (`Lucia`, `Jason`, `Raul Bautista`, `Boobie Ike`, `Dre'Quan Priest`, `Cal Hampton`, `Bae-Luxe`), ficha criminal/biográfica animada e atributos.
3. **`data_comparison` / `stat_counter` (Números, datas ou comparações):** Gráfico comparativo animado + objeto 3D em Three.js (`@remotion/three`) + contador numérico progressivo com física `spring()`.
4. **`cinematic_broll` (Cena de gameplay/trailer):** Vídeo real 1080p dos trailers oficiais da Rockstar ou screenshot 4K com câmera virtual suave, lower-third contextual, selo da fonte e color grading cinematográfico.
5. **Legendas Palavra-por-Palavra (`faster-whisper`):** Sincronizadas em milissegundos com o áudio real da narração, destacando a palavra exata falada no instante atual com animação `spring()`.
