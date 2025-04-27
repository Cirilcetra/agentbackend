#!/bin/bash

# Stop any running backend server
echo "Stopping any running backend server..."
ps aux | grep 'uvicorn app.main:app' | grep -v grep | awk '{print $2}' | xargs -r kill -9
sleep 2

# Set the environment variable to use a persistent storage for ChromaDB
export CHROMA_DB_PATH="./chroma_db"

# Create the directory if it doesn't exist
mkdir -p "$CHROMA_DB_PATH"

# Create a temporary patch to fix the document ID issue
cat > fix_document_id.patch <<EOF
--- reindex_vector_db.py.orig	2025-03-29 22:45:00
+++ reindex_vector_db.py	2025-03-29 22:45:00
@@ -132,8 +132,7 @@
                 
                 # Format document data for vector DB
                 document_data = {
-                    "id": doc
-                    "title": doc.get("title"),
+                    "id": doc.get("id"), "title": doc.get("title"),
                     "description": doc.get("description"),
                     "file_name": doc.get("file_name"),
                     "extracted_text": doc.get("extracted_text"),
EOF

# Apply the patch to fix the document ID issue
echo "Applying patch to fix document ID issue..."
patch -p0 < fix_document_id.patch

# Run the reindexing script with the force flag
echo "Running reindexing script..."
python reindex_vector_db.py --force

# Add the truck driver document directly to the vector DB
echo "Adding truck driver document to vector DB..."
python -c "from app.embeddings import add_truck_driver_document_to_vector_db; add_truck_driver_document_to_vector_db()"

# Restart the backend server
echo "Restarting the backend server..."
nohup python -m uvicorn app.main:app --reload > backend.log 2>&1 &

echo "Done! The vector database has been fixed and the backend server restarted."
echo "Check backend.log and reindex_documents.log for details." 