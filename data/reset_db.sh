#!/bin/bash

DB_PATH="data/x_data.db"

if [ -f "$DB_PATH" ]; then
    echo "Deleting existing database at $DB_PATH..."
    rm "$DB_PATH"
    echo "Database deleted."
else
    echo "No existing database found at $DB_PATH."
fi

echo "Recreating empty database and tables..."
python3 -c "from scripts.load_local_data import create_tables; import sqlite3; db=sqlite3.connect('$DB_PATH'); create_tables(db); db.close()"
echo "Database reset and tables created. You can now reload data with scripts/load_local_data.py." 