# Thalie — Le nuancier des fleurs suisses

## Description

Visualisation scrollytelling de la flore suisse organisée par altitude et par mois de floraison. Le site se compose de deux vues : un écran d'accueil avec une grille de couleurs (mode aléatoire ou organisée par altitude et mois), et une section d'exploration interactive avec trois paysages SVG illustrés (montagne, plaine, ville). En faisant défiler la page, l'altitude change progressivement et les formes du paysage se colorent avec les teintes des espèces qui fleurissent à ce niveau. Un filtre par mois permet d'affiner la sélection. Cliquer sur une forme ou sur une couleur dominante ouvre une fiche détaillée de la fleur correspondante.

## Contexte

Les données des espèces de fleurs proviennent d'Info Flora via GBIF (téléchargement d'occurrences filtrées sur la Suisse). Les altitudes minimum et maximum ont été calculées grâce aux longitudes et latitudes des espèces de GBIF et l'aide de l'API de SwissTopo. Les images sont libres de droit et récupérées depuis Wikimedia Commons et iNaturalist. Les couleurs et floraisons viennent de Wikidata et vérifiées à la main. Claude a été utilisé pour la rédaction des descriptions et "fun facts", puis vérifiées à la main.

## But

Ce projet est un projet exploratoire permettant de découvrir la biodiversité suisse à travers la couleur. Les fleurs changent selon l’altitude et le moment de l’année. Notre but principal était traduire les données en paysage visuel et de transformer des données scientifiques en expérience immersive.

## Planches et prototype

<ul>
<li>
<a href="https://www.figma.com/design/75HxPTTM8YXUpJtecaTIjy/VisualDon---Projet?node-id=78-213&t=2Z7AEFECnkqlfLTj-1](https://www.figma.com/design/75HxPTTM8YXUpJtecaTIjy/VisualDon---Projet?node-id=0-1&t=2Z7AEFECnkqlfLTj-1)">Planches Figma</a>
</li><li>
<a href="https://www.figma.com/proto/75HxPTTM8YXUpJtecaTIjy/VisualDon---Projet?page-id=0%3A1&node-id=38-1265&viewport=-1214%2C175%2C0.31&t=fhLXxFiaLW7x77w3-1&scaling=min-zoom&content-scaling=fixed&starting-point-node-id=34%3A30">Prototype Figma</a></li>
</ul>

## Références

### Graphiques

<ul>
<li><a href="https://pudding.cool/2021/03/foundation-names/">The Naked Truth</a></li>
<li><a href="https://www.huedata.ai/#!/">Hue Data</a></li>
  <li><a href="https://movies-palettes.adriencarpentier.com/">Movies Palettes</a></li>
  <li><a href="https://pudding.cool/2024/09/courts/">Every Outdoor Basketball Court in the U.S.A.</a></li>
  <li><a href="https://plantica.net/en/">Plantica</a></li>
</ul>
<h3>Données</h3>
<ul>
<li><a href="https://www.infoflora.ch/fr/">Info Flora</a> - Crédits : GBIF.org (26 March 2026) GBIF Occurrence Download  <a href="https://doi.org/10.15468/dl.2a3ar3">https://doi.org/10.15468/dl.2a3ar3</a></li>
  <li><a href='https://entrepot.recherche.data.gouv.fr/dataset.xhtml%3Bjsessionid%3De0c12d34ff0227753206ff44a48b?fileAccess=&fileSortField=size&fileTypeGroupFacet="Other"&persistentId=doi%3A10.15454%2FADCQHT&q=&version'>FlorealData</a></li>
  <li><a href="https://commons.wikimedia.org/">Wikimedia Commons</a> - Images des fleurs</li>
  <li><a href="https://www.swisstopo.admin.ch/">Swiss Topo</a> - Altitudes</li>
  <li><a href="https://www.wikidata.org/">Wikidata</a> - Couleurs et floraisons des espèces, puis vérifiées à la main</li>
  <li><a href="https://www.inaturalist.org/">iNaturalist</a> - Images des fleurs</li>
  <li><a href="https://www.anthropic.com/claude">Claude (Anthropic)</a> - Rédaction des descriptions et fun facts, vérifiés à la main</li>
</ul>
