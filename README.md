# Marché FUT : suivi et anticipation

Application qui tourne sur ton PC et suit le marché des transferts d'EA FC Ultimate Team
à partir des données de [FUTBIN](https://www.futbin.com). Plateforme par défaut : **PC**.

Elle ne joue jamais à ta place : **aucun achat ni vente automatique** dans le jeu (risque
de bannissement). Elle relève, analyse et te dit quand c'est le bon moment.

## Ce qu'elle fait

| Onglet | Rôle |
|---|---|
| **Signaux** | Tes joueurs suivis, leur prix, les variations sur 24 h et 7 jours, la position dans la fourchette sur 30 jours, et un avis *Acheter / Vendre / Attendre* avec les raisons. Clique sur un joueur pour voir le graphique et son jour le moins cher. |
| **Plus utilisés** | Les joueurs les plus populaires sur FUTBIN, relevés toutes les 6 h. La colonne « Les plus réguliers » montre ceux qui restent dans le top au fil du temps : les vraies méta-cartes. Un bouton ajoute le top 20 à ton suivi. |
| **Calendrier** | Les cycles de la semaine (vendredi 19 h, récompenses, Weekend League), les grands événements à venir (Black Friday, TOTY, TOTS…) estimés à partir des saisons précédentes, et l'historique FC 24 → FC 26. Tu peux ajouter un événement dès qu'une fuite tombe. |
| **Veille** | Les publications des comptes et forums qui parlent du marché, classées par sujet (fuite, promo, pack, SBC, eSport, crash, hausse). |

La collecte tourne toute seule toutes les 30 minutes tant que l'application est ouverte.

## Installation (Windows)

1. Installe **Python 3.10 ou plus récent** depuis https://www.python.org/downloads/ en cochant
   **« Add python.exe to PATH »**.
2. Télécharge ce dépôt (bouton vert **Code → Download ZIP**) et décompresse-le.
3. Double-clique sur **`lancer.bat`**. Le premier lancement installe ce qu'il faut, puis le
   tableau de bord s'ouvre dans ton navigateur à l'adresse http://127.0.0.1:5050.

Laisse la fenêtre noire ouverte : c'est elle qui fait les relevés.

## Premiers pas

1. Onglet **Plus utilisés** → *Actualiser depuis FUTBIN* → *Suivre le top 20*.
2. Onglet **Signaux** → *Relever les prix maintenant*. Pour chaque joueur, *Importer
   l'historique FUTBIN* récupère ses prix depuis le début de la saison.
3. Pour ajouter un joueur précis, colle son lien FUTBIN (par ex.
   `https://www.futbin.com/27/player/12345/nom-du-joueur`) dans le champ en haut.

Plus l'application tourne longtemps, plus les signaux et le « jour le moins cher »
deviennent fiables.

## La veille des comptes

Les sources se règlent dans `data/sources.json`.

- **Reddit** (r/EASportsFC, r/fut) : lu automatiquement, seuls les messages qui parlent du
  marché sont gardés.
- **Comptes X/Twitter** (FUT Sheriff, FUTBIN, EA SPORTS FC, EA FC Direct…) : X ne permet plus
  de lire les comptes gratuitement. Pour les automatiser, crée un flux RSS du compte
  (par ex. sur https://rss.app, *Twitter/X to RSS*) et colle son adresse dans le champ
  `"flux"` du compte.
- **Chaînes YouTube** : ajoute une source `{"nom": "...", "type": "rss", "flux":
  "https://www.youtube.com/feeds/videos.xml?channel_id=IDENTIFIANT", "actif": true}`.
  L'identifiant `UC…` se trouve dans *À propos → Partager la chaîne → Copier l'ID*.

Les mots-clés et leur poids (`mots_cles`, `poids`) sont modifiables dans le même fichier.

## Le calendrier et les saisons passées

`data/evenements.json` contient les dates des saisons FC 24, FC 25 et FC 26. Elles sont
**approximatives** : corrige-les si tu as mieux. Les dates de la saison en cours sont
**estimées** en décalant la dernière date connue de 52 semaines (EA lance presque toujours
ses promos un vendredi) ; elles sont marquées « estimé » dans l'application.

## Réglages

Variables d'environnement facultatives (à mettre dans `lancer.bat` avec `set NOM=valeur`) :

| Variable | Défaut | Rôle |
|---|---|---|
| `FUT_PLATEFORME` | `pc` | `pc`, `ps` ou `xbox` |
| `FUT_ANNEE` | `27` | Édition suivie sur FUTBIN |
| `FUT_INTERVALLE_MIN` | `30` | Minutes entre deux relevés |
| `FUT_PAUSE_S` | `4` | Pause entre deux requêtes FUTBIN |

## Limites à connaître

- FUTBIN n'a pas d'accès officiel pour les développeurs : l'application lit ses pages. Si
  FUTBIN change son site ou bloque les requêtes, les relevés échouent (l'erreur s'affiche) ;
  tu peux alors saisir les prix à la main dans la fiche d'un joueur.
- Les avis sont des probabilités tirées des cycles habituels du marché, pas des certitudes.

## Développement

```sh
pip install -r requirements.txt pytest
python -m pytest
```
