/** Exemples documentaires : ces routes ne sont pas installées dans l’API. */
export const backendExamples = [
  {
    id: "rate-limiting",
    nav: "Rate limiting",
    title: "Limiter les requêtes par route, par compte ou globalement",
    intro:
      "Activez Redis et le rate limiting dans le fichier d’environnement racine. Le middleware global est déjà branché par configure_cache ; les dépendances ci-dessous ajoutent des quotas aux nouvelles routes. Elles peuvent aussi être placées sur un APIRouter.",
    label: "backend/api/views/examples/limits.py · exemple à créer",
    code: 'from fastapi import APIRouter, Depends\nfrom api.services.authorization import CurrentUser\nfrom api.services.rate_limiting import rate_limit, user_rate_limit\n\nrouter = APIRouter()\n\n@router.get("/public-status", dependencies=[\n    Depends(rate_limit(20, seconds=60, scope="public-status")),\n])\ndef public_status():\n    return {"data": {"available": True}, "message": "OK"}\n\n@router.get("/my-usage", dependencies=[\n    Depends(user_rate_limit(10, seconds=60, scope="my-usage")),\n])\ndef my_usage(user: CurrentUser):\n    return {"data": {"user_id": user.id}, "message": "OK"}\n\n# Pour tout un groupe de routes :\nprivate_router = APIRouter(dependencies=[\n    Depends(user_rate_limit(30, seconds=60, scope="private-tools")),\n])',
    note: "Les quotas globaux et locaux se cumulent. Un scope explicite partage le quota entre les routes qui l’utilisent. rate_limit identifie le pair réseau : derrière Next.js, plusieurs visiteurs peuvent partager cette IP. Utilisez user_rate_limit pour les comptes authentifiés, sans faire confiance à un X-Forwarded-For client. 429 signifie quota dépassé ; Redis indisponible produit 503 si FAIL_CLOSED=true, sinon les requêtes passent. Lisez Retry-After lorsqu’il est présent et ne relancez pas immédiatement une écriture. RATE_LIMIT_ENABLED=false désactive les quotas ; GLOBAL_LIMIT=0 désactive seulement le quota global. Les sondes de santé, /metrics, OPTIONS et les routes /ws sont exclues du quota global.",
    examples: [
      {
        label: ".env.dev ou .env.prod · racine du dépôt",
        language: "bash",
        code: 'REDIS_URL="redis://redis:6379/0"\nRATE_LIMIT_ENABLED="true"\nRATE_LIMIT_GLOBAL_LIMIT="300"\nRATE_LIMIT_GLOBAL_WINDOW_SECONDS="60"\nRATE_LIMIT_FAIL_CLOSED="true"\n# Configuration de l’application déjà présente :\n# configure_cache(app, config) configure aussi le rate limiting.',
      },
    ],
  },
  {
    id: "storage",
    nav: "Stockage local / S3",
    title: "Utiliser le même service pour stocker vos fichiers",
    intro:
      "LocalStorage et S3Storage acceptent tous types de fichiers via put, read et delete. profile_storage reste la sélection dédiée aux photos. Pour vos documents, créez votre propre dépendance, puis utilisez-la dans vos routes. Cet exemple conserve des PDF privés de 2 Mio maximum dans un espace séparé pour chaque compte.",
    label: "backend/api/views/examples/documents.py · exemple à créer",
    code: 'from pathlib import Path\nfrom typing import Annotated\nfrom uuid import UUID, uuid4\nfrom fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile\nfrom fastapi.responses import Response\nfrom api.services.authorization import CurrentUser\nfrom api.services.storage import LocalStorage, S3Storage\n\nrouter = APIRouter()\nMAX_BYTES = 2 * 1024 * 1024\n\ndef document_storage(request: Request):\n    config = request.app.state.config\n    return (S3Storage(config) if config.STORAGE_BACKEND == "s3"\n            else LocalStorage(Path("static/uploads/documents")))\n\nStorage = Annotated[LocalStorage | S3Storage, Depends(document_storage)]\n\n@router.post("/documents", status_code=201)\ndef upload_document(user: CurrentUser, storage: Storage,\n                    file: Annotated[UploadFile, File()]):\n    content = file.file.read(MAX_BYTES + 1)\n    if len(content) > MAX_BYTES:\n        raise HTTPException(413, "Fichier trop volumineux")\n    if not content.startswith(b"%PDF-"):\n        raise HTTPException(415, "Un PDF est attendu")\n    document_id = uuid4()\n    key = f"documents/{user.id}/{document_id}.pdf"\n    storage.put(key, content, "application/pdf")\n    return {"data": {"id": str(document_id)}, "message": "OK"}\n\n@router.get("/documents/{document_id}")\ndef read_document(document_id: UUID, user: CurrentUser, storage: Storage):\n    key = f"documents/{user.id}/{document_id}.pdf"\n    try:\n        content = storage.read(key)\n    except FileNotFoundError:\n        raise HTTPException(404, "Document introuvable") from None\n    return Response(content, media_type="application/pdf", headers={\n        "Content-Disposition": f\'attachment; filename="{document_id}.pdf"\',\n        "Cache-Control": "private, no-store",\n        "X-Content-Type-Options": "nosniff",\n    })\n\n@router.delete("/documents/{document_id}")\ndef delete_document(document_id: UUID, user: CurrentUser, storage: Storage):\n    storage.delete(f"documents/{user.id}/{document_id}.pdf")\n    return {"data": None, "message": "OK"}',
    note: "La clé est générée par le serveur et contient l’ID authentifié ; le nom fourni par le client n’est jamais utilisé comme chemin. Ajoutez un modèle SQL et une migration si vous voulez lister les fichiers et conserver nom, taille, type et propriétaire. La signature PDF est un contrôle minimal d’exemple : adaptez la validation et l’analyse des fichiers à votre usage. Les classes actuelles lisent les objets en mémoire ; prévoyez du streaming pour les gros fichiers. Ne publiez pas le dossier privé avec StaticFiles. En développement, les documents apparaissent dans backend/static/uploads/documents ; en production, le volume backend_uploads couvre ce chemin. Un changement local → S3 ne transfère pas les fichiers existants : prévoyez leur migration.",
    examples: [
      {
        label: ".env.dev ou .env.prod · stockage local",
        language: "bash",
        code: 'STORAGE_BACKEND="local"\n# Photos uniquement ; les documents utilisent leur propre racine ci-dessus.\nPROFILE_PHOTO_DIR="static/uploads/profile_photos"',
      },
      {
        label: ".env.dev ou .env.prod · bucket S3 privé existant",
        language: "bash",
        code: 'STORAGE_BACKEND="s3"\nS3_BUCKET="mon-bucket-prive"\nS3_REGION="us-east-1"\n# Vide pour AWS ; URL du service pour MinIO ou autre compatible S3.\nS3_ENDPOINT_URL=""\nS3_ADDRESSING_STYLE="auto"\n# Laisser les deux vides avec un rôle IAM ; sinon renseigner les deux.\nS3_ACCESS_KEY_ID=""\nS3_SECRET_ACCESS_KEY=""\n# Le bucket doit exister. Accès requis : PutObject, GetObject, DeleteObject.\n# MinIO utilise souvent S3_ADDRESSING_STYLE="path".',
      },
      {
        label: "Service navigateur · après ajout de la route au proxy",
        language: "typescript",
        code: 'import { apiRequest } from "@/lib/api/client";\n\nexport function uploadDocument(file: File) {\n  const body = new FormData();\n  body.set("file", file);\n  return apiRequest<{ id: string }>("/documents", {\n    method: "POST", body,\n  });\n}\n// Ne pas fixer Content-Type : le navigateur ajoute la frontière multipart.\n// Le proxy actuel n’autorise pas /documents automatiquement.\n// Pour le GET binaire, suivre le proxy existant des photos de profil.',
      },
    ],
  },
  {
    id: "emails",
    nav: "Envoi d’e-mails",
    title: "Envoyer un e-mail depuis une route",
    intro:
      "send_email accepte une adresse ou une liste et renvoie un booléen. La route ci-dessous envoie un message au compte connecté et confirme uniquement l’acceptation par le serveur SMTP. Les schémas restent dans api/schemas.",
    label: "backend/api/views/examples/notifications.py · exemple à créer",
    code: 'from html import escape\nfrom fastapi import APIRouter, Depends, HTTPException\nfrom api.schemas.notification import NotificationInput\nfrom api.services.authorization import CurrentUser\nfrom api.services.mail import send_email\nfrom api.services.rate_limiting import user_rate_limit\n\nrouter = APIRouter()\n\n@router.post("/notifications/email", dependencies=[\n    Depends(user_rate_limit(3, seconds=900, scope="notification-email")),\n])\ndef email_notification(body: NotificationInput, user: CurrentUser):\n    if not user.email:\n        raise HTTPException(400, "Ajoutez une adresse e-mail à votre profil")\n    html = "<p>" + escape(body.message).replace("\\n", "<br>") + "</p>"\n    if not send_email(user.email, html, body.subject):\n        raise HTTPException(503, "L’envoi a échoué")\n    return {"data": None, "message": "Message accepté par SMTP"}',
    note: "La fonction est synchrone : une route def laisse FastAPI exécuter le travail hors de la boucle async. Pour une route async, utilisez un thread ou Celery. Avec BackgroundTasks, l’envoi reste dans le processus de l’API et peut être perdu au redémarrage ; utilisez le worker si la reprise est nécessaire. Pour plusieurs destinataires, passez une liste à send_email : les adresses seront visibles dans To. Envoyez séparément si elles doivent rester privées. False peut signaler un refus partiel ; une relance aveugle peut donc créer des doublons. Les modèles HTML existants sont dans api/html/email ; échappez les données saisies par les utilisateurs.",
    examples: [
      {
        label: "backend/api/schemas/notification.py · fichier à créer",
        language: "python",
        code: 'from pydantic import BaseModel, Field\n\nclass NotificationInput(BaseModel):\n    subject: str = Field(min_length=1, max_length=160, pattern=r"^[^\\r\\n]+$")\n    message: str = Field(min_length=1, max_length=4000)',
      },
      {
        label: ".env.dev ou .env.prod · serveur SMTP avec STARTTLS",
        language: "bash",
        code: 'EMAIL_HOST="smtp.example.com"\nEMAIL_PORT="587"\nEMAIL_DOMAIN="example.com"\nEMAIL_USERNAME=""\nEMAIL_PASSWORD=""\n# Expéditeur actuel : notification@EMAIL_DOMAIN.\n# STARTTLS et authentification sont requis par send_email.\n# Renseigner les secrets uniquement dans le fichier racine non versionné.',
      },
      {
        label: "backend/api/tasks/notifications.py · variante avec reprise",
        language: "python",
        code: 'from api.services.background import background_task\nfrom api.services.mail import send_email\n\n@background_task(name="notifications.send_email", max_retries=3)\ndef deliver_email(receiver: str, html: str, subject: str):\n    if not send_email(receiver, html, subject):\n        raise RuntimeError("SMTP indisponible ou destinataire refusé")\n    return {"accepted": True}\n\n# Ajouter "api.tasks.notifications" à include dans services/background.py.\n# Dans une route async, après les contrôles et la transaction SQL :\n# task_id = await enqueue_async(deliver_email, user.email, html, body.subject)\n# Import : from api.services.background import enqueue_async\n# Retourner HTTP 202 et task_id : c’est une mise en file, pas un envoi confirmé.\n# False ne distingue pas panne temporaire et refus permanent : pas de retry aveugle.\n# La livraison peut être répétée après panne : prévoir la déduplication métier.\n# Les messages contiennent l’adresse et le HTML : protéger le broker.',
      },
    ],
  },
] as const;
