# Workflow pour démarrer un scraping manuel

Ce guide propose un flux simple pour collecter des données **manuellement** (sans automatisation), afin de structurer l'information et pouvoir ensuite l'exploiter proprement.

## 1) Définir le besoin
- **Objectif** : quelles données voulez-vous récupérer (ex. catalogue produits, prix, avis) ?
- **Périmètre** : quels sites/pages précises ?
- **Contraintes** : délais, volume, format final.

## 2) Préparer le modèle de collecte
- Créer un **tableur** (Google Sheets/Excel) ou un fichier CSV avec des colonnes claires.
- Exemple de colonnes : `source_url`, `nom`, `prix`, `date`, `commentaire`, `notes`, `capture`.
- Définir des **règles de saisie** (format de date, devise, unités, etc.).

## 3) Organiser la session de scraping manuel
- Ouvrir les pages cibles dans des onglets dédiés.
- Suivre un **ordre fixe** (ex. pagination ou catégories) pour éviter les doublons.
- Noter un **identifiant unique** par entrée si possible (ex. SKU, ID, titre + URL).

## 4) Collecter et valider
- Copier les données dans le tableur selon les règles de saisie.
- Vérifier **à chaque ligne** : cohérence des formats et complétude des champs.
- Utiliser un statut (ex. `à vérifier`, `ok`) pour contrôler la qualité.

## 5) Nettoyer et normaliser
- Corriger les valeurs incohérentes (devise, espaces, formats).
- Dédupliquer sur la base de `source_url` ou d'un identifiant.
- Ajouter des notes en cas d'ambiguïté.

## 6) Exporter pour usage futur
- Exporter en **CSV** ou **JSON**.
- Conserver une copie datée (ex. `scraping-2024-04-21.csv`).

## 7) Vérifier la conformité
- Lire les **CGU** du site et s'assurer du respect des règles.
- Éviter les pages sensibles ou protégées.

## Exemple de checklist rapide
- [ ] Objectif clair
- [ ] Colonnes définies
- [ ] Règles de saisie prêtes
- [ ] Sources ouvertes et listées
- [ ] Collecte + validation
- [ ] Nettoyage + export

---

Si vous souhaitez aller plus loin (semi-automatisation ou scraping assisté), je peux proposer un workflow adapté aux outils que vous utilisez.
