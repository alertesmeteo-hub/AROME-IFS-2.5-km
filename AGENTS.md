# Préférences de livraison météo

Instruction utilisateur du 8 septembre 2026 : toujours livrer les nouveaux modules météo sur le modèle du dépôt AROME.

- Dépôt GitHub dédié, workflow Actions avec `workflow_dispatch` et mise à jour programmée.
- Données météo préparées par le workflow et publiées dans une branche `data`.
- Extension WordPress/Avada installable en ZIP avec shortcode, instructions simples et ZIP téléchargeable dans Releases.
- Lancer et vérifier le premier run après mise en place lorsque les accès le permettent.
- Préserver la dernière publication valide en cas de données amont incomplètes.
- Ne pas livrer uniquement une application React nécessitant un terminal local.
