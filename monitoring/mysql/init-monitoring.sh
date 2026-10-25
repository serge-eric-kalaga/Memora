#!/bin/bash
# Utilisateur dédié à l’exporteur, jamais le compte root ni le compte applicatif.
# Relançable sur une base existante, depuis le conteneur MySQL (connexion locale).
set -eu
if [ -z "${MYSQL_MONITORING_PASSWORD:-}" ]; then
  echo "MYSQL_MONITORING_PASSWORD est requise pour préparer le monitoring." >&2
  exit 1
fi
# QUOTE protège aussi les mots de passe personnalisés contenant des caractères SQL.
password_hex=$(printf '%s' "$MYSQL_MONITORING_PASSWORD" | od -An -v -tx1 | tr -d ' \n')
MYSQL_PWD="$MYSQL_ROOT_PASSWORD" mysql --protocol=socket -uroot <<SQL
SET @password = CONVERT(0x${password_hex} USING utf8mb4);
SET @statement = CONCAT('CREATE USER IF NOT EXISTS ''monitoring''@''%'' IDENTIFIED BY ', QUOTE(@password), ' WITH MAX_USER_CONNECTIONS 3');
PREPARE monitoring_statement FROM @statement;
EXECUTE monitoring_statement;
DEALLOCATE PREPARE monitoring_statement;
SET @statement = CONCAT('ALTER USER ''monitoring''@''%'' IDENTIFIED BY ', QUOTE(@password), ' WITH MAX_USER_CONNECTIONS 3');
PREPARE monitoring_statement FROM @statement;
EXECUTE monitoring_statement;
DEALLOCATE PREPARE monitoring_statement;
GRANT PROCESS, REPLICATION CLIENT, SELECT ON *.* TO 'monitoring'@'%';
SQL
