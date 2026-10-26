from api import createApp, SETTINGS


import os


log_dir_file = f"{os.getcwd()}/logs/app.log"
static_dir = f"{os.getcwd()}/static"
if not os.path.exists(static_dir):
    os.makedirs(static_dir)
if not os.path.exists(f"{os.getcwd()}/logs"):
    os.makedirs(f"{os.getcwd()}/logs")
# Créer le fichier si nécessaire sans effacer les logs des démarrages précédents.
with open(log_dir_file, "a"):
    pass


settings = SETTINGS()
# En production, Alembic prépare le schéma avant le démarrage du serveur.
app = createApp(settings, initialise_database=settings.INITIALISE_DATABASE)
