from sqlalchemy import create_engine, inspect, text
import pandas as pd
from tqdm import tqdm
import os
import requests



def migrate_mysql(source_uri, destination_uri):
    """Migrate all tables from one MySQL DB to another."""
    source_engine = create_engine(source_uri)
    dest_engine = create_engine(destination_uri)

    inspector = inspect(source_engine)
    tables = inspector.get_table_names()

    if not tables:
        print("⚠️  No tables found in the source MySQL database.")
        return

    print(f"📋  Found {len(tables)} MySQL table(s): {', '.join(tables)}")

    for table in tqdm(tables, desc="Migrating MySQL Tables", unit="table"):
        print(f"\nMigrating table: {table}")
        query = f"SELECT * FROM `{table}`"

        try:
            df = pd.read_sql(query, source_engine)
            with dest_engine.begin() as conn:
                df.to_sql(table, conn, if_exists='replace', index=False)
            print(f"   ✅ Table {table} migrated successfully.")
        except Exception as e:
            print(f"   ❌ Error migrating table {table}: {e}")
            continue

    print("🎉 MySQL Migration completed successfully!")


def migrate_sql_dump(dump_content, destination_uri):
    """Load SQL dump content into the destination MySQL database."""
    dest_engine = create_engine(destination_uri)
    statements = [stmt.strip() for stmt in dump_content.split(';') if stmt.strip()]
    print(f"📋  Applying {len(statements)} SQL statement(s) from dump...")

    with dest_engine.begin() as conn:
        for stmt in tqdm(statements, desc="Executing SQL Statements", unit="stmt"):
            try:
                conn.execute(text(stmt))
            except Exception as e:
                tqdm.write(f"   ❌ Error executing statement: {e}\nStatement snippet: {stmt[:100]}...")
                continue

    print("🎉 SQL dump loaded successfully!")


if __name__ == "__main__":
    # ─── CONFIGURE YOUR SOURCE ──────────────────────────────────────────────────
    # SOURCE can be:
    # - HTTPS/HTTP URL to a .sql dump
    # - Path to local .sql file
    # - MySQL URI
    source = "C:/Users/ADMIN/PyCharmMiscProject/guvnl_dev.sql"  # Replace with actual link to .sql file
    destination = "mysql+pymysql://root:Aradhya03101998%2A@localhost/guvnl_db"  # Replace with actual MySQL URI
    # ────────────────────────────────────────────────────────────────────────────

    if source.lower().startswith(('http://', 'https://')) and destination.startswith('mysql'):
        print(f"🌐 Downloading SQL dump from {source}...")
        resp = requests.get(source)
        resp.raise_for_status()
        dump_text = resp.text
        migrate_sql_dump(dump_text, destination)

    elif os.path.isfile(source) and source.lower().endswith('.sql') and destination.startswith('mysql'):
        with open(source, 'r', encoding='utf-8') as f:
            dump_text = f.read()
        migrate_sql_dump(dump_text, destination)

    elif source.startswith('mysql') and destination.startswith('mysql'):
        migrate_mysql(source, destination)

    else:
        print("❌ Unsupported source/destination combination.\n" \
              "Use HTTP/HTTPS link or .sql file for MySQL, or two MySQL URIs.")
