import aiosqlite
import json
import re
import os

DB_PATH = os.path.join(os.path.dirname(__file__), 'uploads.db')

# Extract all ScAddr numbers from a list of log strings
def extract_sc_addrs_from_logs(logs):
    addrs = set()
    pattern = re.compile(r"ScAddr\((\d+)\)")
    for entry in logs:
        for match in pattern.findall(entry):
            addrs.add(int(match))
    return list(addrs)

# Update the sc_addresses column for a given upload id
def update_sc_addresses_for_upload(upload_id, logs):
    addrs = extract_sc_addrs_from_logs(logs)
    addrs_json = json.dumps(addrs, ensure_ascii=False)
    return addrs_json

# Script to update all uploads in the DB with extracted sc_addresses
def update_all_uploads_sc_addresses():
    import asyncio
    async def _update():
        async with aiosqlite.connect(DB_PATH) as conn:
            async with conn.execute('SELECT id, logs FROM uploads') as cursor:
                rows = await cursor.fetchall()
            for row in rows:
                upload_id, logs_json = row
                if not logs_json:
                    continue
                try:
                    logs = json.loads(logs_json)
                except Exception:
                    continue
                addrs_json = update_sc_addresses_for_upload(upload_id, logs)
                await conn.execute('UPDATE uploads SET sc_addresses = ? WHERE id = ?', (addrs_json, upload_id))
            await conn.commit()
    asyncio.run(_update())

if __name__ == "__main__":
    update_all_uploads_sc_addresses()
    print("SC addresses updated for all uploads.")
