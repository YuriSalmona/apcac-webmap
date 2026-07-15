# APCAC — Áreas Prioritárias da Conservação de Água do Cerrado

Webmap estático das APCAC. Instituto Cerrados, solicitação IC26017 (apresentação MMA).

## Como funciona

Site estático puro — sem servidor de aplicação. Os dados vêm em **PMTiles**, que o
navegador consulta por **HTTP Range requests**: só os bytes dos tiles visíveis são
baixados. A abertura do mapa custa ~40 KB, não os 41 MB do repositório.

> **O host precisa suportar Range requests.** GitHub Pages suporta. Um host que
> ignore o cabeçalho `Range` e devolva o arquivo inteiro quebra o mapa.

| Arquivo | Zoom | Conteúdo |
|---|---|---|
| `cerrado_raster.pmtiles` | 3–9 | visão geral, ranking contra o Cerrado inteiro |
| `rhi_raster.pmtiles` | 3–9 | visão geral, ranking por Região Hidrográfica |
| `uph_raster.pmtiles` | 3–9 | visão geral, ranking por UPH |
| `apcac_detalhe.pmtiles` | 10 | microbacias clicáveis, com as 3 classificações |
| `legenda.json` | — | 20 classes: cor, prioridade, ação, risco |

**Raster na visão geral, vetor no detalhe:** no zoom 4 cada microbacia tem ~2 pixels;
201 mil polígonos vetoriais custariam ~3 MB por tile (o piso por feição do MVT) e
travariam o navegador. O raster desenha o mesmo por ~15 KB. A partir do z10 o vetor
assume e as feições ficam clicáveis. O z10 tem precisão de ~9 m — sub-pixel até o
z13, então o MapLibre faz overzoom sem perda visível e não há tiles z11+.

## Os três escopos

Os três rasters são a **mesma geometria**. Muda só o recorte contra o qual a
importância hidrológica é ranqueada (quantis 5/5/30/60 → A/B/C/X): o Cerrado inteiro
(limiares globais, cores comparáveis entre regiões — é o padrão), cada uma das 13
Regiões Hidrográficas, ou cada uma das 456 UPHs. Por isso é **um** mapa com seletor,
e não três mapas.

## Recortes aplicados

- **Limite do bioma Cerrado** (`Cerrado_2019`): 201.499 → 122.314 microbacias.
- **Prioridade Regular oculta**, exceto a classe `XC` ("Conjunto de Ações Diversas").
  O filtro é **por escopo** — uma microbacia pode ser Regular no Cerrado e Alta na
  sua UPH. Do dado só saíram as ocultas nos três escopos ao mesmo tempo.

## Regerar

- `gera_legenda.py` — extrai a legenda do QML embutido no GeoPackage, aplica o
  agrupamento por ação prioritária e a terminologia do Instituto. Tem asserções que
  falham alto se o dado de origem mudar.
- `recorta_bioma.py` — recorte pelo bioma via índice espacial (6 min; o
  `ogr2ogr -clipsrc` levaria mais de 8 horas).

## Créditos de terceiros

Mapa de fundo claro © OpenStreetMap © CARTO · Imagens de satélite © Esri, Maxar,
Earthstar Geographics.
