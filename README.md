# AROME-IFS 2,5 km — Alertes Météo

Prévisions Météo-France pour les communes de France métropolitaine et de Corse, avec **le même JSON départemental v3 que le module AROME existant** : communes, points et 33 valeurs dans le même ordre.

## Lancer la mise à jour

Dans **Actions → Mise à jour AROME-IFS 2,5 km → Run workflow**, choisir `main` et lancer. Cocher `force` pour reconstruire un calcul déjà publié. Une vérification automatique est programmée chaque heure ; GitHub peut retarder son exécution.

Le workflow sélectionne un seul calcul complet, décode les paquets officiels SP1 et SP2, vérifie les 96 départements, puis publie la branche [`data`](https://github.com/alertesmeteo-hub/AROME-IFS-2.5-km/tree/data). Un téléchargement incomplet ou un échec de validation conserve la publication précédente. Aucune clé Météo-France n'est nécessaire pour ces paquets publics.

## Format identique aux autres modules

- `index.json` : modèle, date du calcul, couverture et fichiers départementaux.
- `departements/66.json`, etc. : `schema_version: 3`, `columns`, `points`, `communes`, `forecast`.
- `communes` : `[code_insee, name, postal_codes, population, latitude, longitude, point_id]`.
- `points` : `[model_index, latitude, longitude, altitude_m]`.
- `forecast` : `[[date_iso, [valeurs_point_0, valeurs_point_1, ...]], ...]`.

Le `point_id` est un index **local au département**. Les communes proches peuvent partager le même point de grille. La ligne de valeurs d'une commune à une échéance se lit ainsi :

```javascript
const commune = department.communes.find(c => c[0] === '66005');
const pointId = commune[6];
const [date, valuesByPoint] = department.forecast[0];
const values = valuesByPoint[pointId];
const temperature = values[department.columns.values.indexOf('temperature_c')];
```

Les noms et l'ordre des **33 colonnes** sont conservés dans [`tests/reference-schema.json`](tests/reference-schema.json). Référence : `alertesmeteo-hub/arome-meteofrance`, commit `fcace746879935fa8c5087eac85ab5cbb11abfdf`. Le modèle fournit 52 échéances horaires, de +0 à +51 h. Les données absentes restent `null` : aucun décalage de colonne et aucune substitution par zéro.

Température en °C, vent et rafales en km/h, pression en hPa, précipitations horaires et cumulées en mm. Les cumuls GRIB partant du début du calcul sont différenciés pour obtenir les quantités horaires. La neige en mm représente l'équivalent en eau ; les centimètres sont estimés. Comme dans le contrat historique, `snow_depth_cm` cumule la neige fraîche estimée sans fonte ni tassement : ce n'est pas une hauteur de neige observée au sol.

Le risque orage est un indicateur dérivé de CAPE et des rafales, pas une probabilité ni une vigilance officielle. Réflectivité, visibilité, foudre, grêle, précipitations convectives et type d'orage restent indisponibles dans ces paquets. La nébulosité totale est estimée à partir des trois étages. À +0 h, certains champs horaires ne sont pas fournis.

## WordPress / Avada

Télécharger le ZIP WordPress dans [Releases](https://github.com/alertesmeteo-hub/AROME-IFS-2.5-km/releases), puis **Extensions → Ajouter → Téléverser une extension → Activer**. Dans Avada, placer le shortcode dans un bloc de texte :

```text
[arome_ifs_meteo]
[arome_ifs_meteo code="75056" departement="75" ville="Paris" heures="51"]
```

Recherche de commune, tableaux généraux, orages, neige et graphiques. Les données sont lues depuis la branche `data`. Les cartes ne sont pas incluses dans cette version. Les préfixes WordPress sont distincts des modules AROME et ICON, pour permettre leur coexistence.

## Sources et validation

[Catalogue officiel des paquets AROME-IFS 0,025°](https://www.data.gouv.fr/api/1/datasets/6a3294c7190dd2ab81bef620/), Météo-France, Licence Ouverte 2.0. AROME-IFS a une maille native de 1,3 km ; ce module utilise la grille de diffusion 0,025° dite 2,5 km, couplée au modèle IFS. Les coordonnées des communes proviennent de l'API Découpage administratif.

```bash
pip install -r requirements.txt
python -m unittest discover -s tests -v
python scripts/update_arome_ifs.py --force
```

Le workflow contrôle aussi les syntaxes PHP/JavaScript. Les tests vérifient le contrat commun, les références aux points, les conversions, les cumuls, les valeurs absentes et la sélection d'un calcul complet.
