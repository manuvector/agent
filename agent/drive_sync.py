import io, os, mimetypes, tempfile
from pathlib import Path
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
from .ingest import ingest_file  # your existing PDF→vector helper

SCOPES = ["https://www.googleapis.com/auth/drive.readonly"]
FOLDER_ID = os.getenv("DRIVE_FOLDER_ID")   # hard-code for MVP
CREDS_FILE = os.getenv("GOOGLE_SERVICE_KEY", "service-account.json")

def get_drive_service():
    creds = service_account.Credentials.from_service_account_file(
        CREDS_FILE, scopes=SCOPES
    )
    return build("drive", "v3", credentials=creds, cache_discovery=False)

def sync_drive_folder():
    service = get_drive_service()
    # list files inside the shared folder (no recursion for clarity)
    q = f"'{FOLDER_ID}' in parents and trashed = false"
    results = service.files().list(q=q,
                                   fields="files(id,name,mimeType,modifiedTime)").execute()
    for file in results.get("files", []):
        if file["mimeType"].startswith("application/vnd.google-apps"):
            # Export Google Docs/Sheets/Slides as PDF or plain text
            mime_map = {
                "application/vnd.google-apps.document": "application/pdf",
                "application/vnd.google-apps.presentation": "application/pdf",
                "application/vnd.google-apps.spreadsheet": "text/csv",
            }
            export_mime = mime_map.get(file["mimeType"])
            if not export_mime:
                continue  # skip drawings, forms, etc.
            request = service.files().export_media(fileId=file["id"],
                                                   mimeType=export_mime)
            suffix = mimetypes.guess_extension(export_mime) or ".pdf"
        else:
            # direct download (PDF, txt, etc.)
            request = service.files().get_media(fileId=file["id"])
            suffix = Path(file["name"]).suffix or ".bin"

        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
        downloader = MediaIoBaseDownload(tmp, request)
        done = False
        while not done:
            status, done = downloader.next_chunk()
        tmp.close()

        # call your existing ingestion function → writes to rag_document table
        ingest_file(tmp.name, display_name=file["name"], source_id=file["id"],
                    modified=file["modifiedTime"])
        os.unlink(tmp.name)

