from vector_store.chroma.client import get_chroma_client
from vector_store.chroma.collection_manager import initialise_all_collections

print("Connecting to ChromaDB...")
try:
    client = get_chroma_client()
    print("Heartbeat:", client.heartbeat())

    print("\nCreating / verifying collections...")
    collections = initialise_all_collections()

    print("\nFinal collection count:", len(collections))
    for name, col in collections.items():
        print(f"  {name}  —  {col.count()} documents")

    print("\nChromaDB collections OK")
except Exception as e:
    import traceback
    print(f"ERROR: {type(e).__name__}: {e}")
    traceback.print_exc()
