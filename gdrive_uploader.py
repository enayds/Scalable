import pandas as pd
from io import BytesIO
import streamlit as st
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload, MediaIoBaseDownload


# -------------------- AUTH & DRIVE SERVICE --------------------

def get_drive_service():
    secrets = st.secrets["google"]
    creds = Credentials(
        token=None,
        refresh_token=secrets["refresh_token"],
        token_uri="https://oauth2.googleapis.com/token",
        client_id=secrets["client_id"],
        client_secret=secrets["client_secret"]
    )
    return build("drive", "v3", credentials=creds)


# -------------------- FILE & SHEET HELPERS --------------------

def get_today_filename():
    import datetime
    return datetime.date.today().isoformat() + ".xlsx"


def find_file(service, filename):
    query = f"name = '{filename}' and mimeType = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'"
    results = service.files().list(q=query, fields="files(id, name)").execute()
    files = results.get("files", [])
    return files[0] if files else None


def normalize_date_column(df, column_name):
    if column_name in df.columns:
        df[column_name] = pd.to_datetime(df[column_name], errors="coerce")
        df[column_name] = df[column_name].dt.date  # Convert to date only
    return df


# -------------------- UPLOAD / UPDATE FILE --------------------

def upload_new_file_with_sheet(service, df, filename, sheet_name):
    buffer = BytesIO()
    with pd.ExcelWriter(buffer, engine="xlsxwriter") as writer:
        df.to_excel(writer, sheet_name=sheet_name, index=False)
    buffer.seek(0)

    media = MediaIoBaseUpload(buffer, mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    file_metadata = {'name': filename, 'mimeType': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'}
    service.files().create(body=file_metadata, media_body=media, fields='id').execute()


def update_existing_file_by_sheet(service, file_id, new_df, sheet_name):
    request = service.files().get_media(fileId=file_id)
    fh = BytesIO()
    downloader = MediaIoBaseDownload(fh, request)
    done = False
    while not done:
        status, done = downloader.next_chunk()
    fh.seek(0)

    # Load all sheets
    existing_sheets = pd.read_excel(fh, sheet_name=None)

    # Normalize both old and new data
    if sheet_name in existing_sheets:
        existing_df = normalize_date_column(existing_sheets[sheet_name], "Date Posted")
    else:
        existing_df = pd.DataFrame()

    new_df = normalize_date_column(new_df, "Date Posted")
    updated_df = pd.concat([existing_df, new_df]).drop_duplicates()

    # Write all sheets back, updating the selected one
    buffer = BytesIO()
    with pd.ExcelWriter(buffer, engine="xlsxwriter") as writer:
        for sheet, df in existing_sheets.items():
            if sheet != sheet_name:
                df.to_excel(writer, sheet_name=sheet, index=False)
        updated_df.to_excel(writer, sheet_name=sheet_name, index=False)

    buffer.seek(0)

    media = MediaIoBaseUpload(buffer, mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    service.files().update(fileId=file_id, media_body=media).execute()


# -------------------- MAIN UPLOAD FUNCTION --------------------

def upload_to_drive(df, category, prefix=None):
    filename = get_today_filename(prefix)
    service = get_drive_service()
    file_info = find_file(service, filename)

    # Normalize and clean up date
    df = normalize_date_column(df, "Date Posted")

    if file_info:
        update_existing_file_by_sheet(service, file_info['id'], df, category)
        st.success(f"File updated successfully under '{category}' sheet!")
    else:
        upload_new_file_with_sheet(service, df, filename, category)
        st.success(f"New Excel file created with '{category}' sheet!")
