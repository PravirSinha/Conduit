"""
CONDUIT — Pinecone Parts Catalog Seeder
========================================
Embeds the parts catalog into Pinecone for RAG-powered
semantic search in the Intake Agent.

Usage:
    python data/seed/load_pinecone.py

What this script does:
    1. Connects to PostgreSQL and fetches all parts from inventory table
    2. Creates Pinecone index if it doesn't exist
    3. Builds rich text descriptions for each part
    4. Embeds descriptions using OpenAI text-embedding-3-small
    5. Upserts vectors to Pinecone with metadata
    6. Verifies upload with a test semantic search

Why this matters:
    The Intake Agent uses these embeddings to find relevant parts
    from a complaint like "grinding noise when braking" without
    needing exact keyword matches. It finds brake pads, rotors,
    calipers semantically — far more accurate than keyword search.

Cost estimate:
    ~28 parts x ~100 tokens each = ~2800 tokens
    text-embedding-3-small = $0.00002 per 1K tokens
    Total cost: < $0.01 (essentially free)
"""

import os
import sys
import time
import json

# ── PATH SETUP ────────────────────────────────────────────────────────────────
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)
))))

from dotenv import load_dotenv
load_dotenv()

# ── COLORS ────────────────────────────────────────────────────────────────────
GREEN  = "\033[92m"
YELLOW = "\033[93m"
RED    = "\033[91m"
BLUE   = "\033[94m"
CYAN   = "\033[96m"
RESET  = "\033[0m"
BOLD   = "\033[1m"

def print_header():
    print(f"\n{BOLD}{CYAN}")
    print("=" * 60)
    print("   CONDUIT — Pinecone Parts Catalog Seeder")
    print("   Building RAG Knowledge Base for Intake Agent")
    print("=" * 60)
    print(f"{RESET}")

def print_step(step: int, total: int, message: str):
    print(f"\n{BLUE}[{step}/{total}]{RESET} {BOLD}{message}{RESET}")

def print_success(message: str):
    print(f"  {GREEN}✓{RESET} {message}")

def print_warning(message: str):
    print(f"  {YELLOW}⚠{RESET} {message}")

def print_error(message: str):
    print(f"  {RED}✗{RESET} {message}")

def print_stat(label: str, value):
    print(f"  {CYAN}→{RESET} {label}: {BOLD}{value}{RESET}")


# ── VALIDATE ENV VARS ─────────────────────────────────────────────────────────

def validate_env():
    """Check all required env vars are present before starting"""
    required = {
        "OPENAI_API_KEY":    "OpenAI API key for embeddings",
        "PINECONE_API_KEY":  "Pinecone API key",
        "PINECONE_INDEX_NAME": "Pinecone index name (e.g. conduit-parts-catalog)",
        "DATABASE_URL":      "PostgreSQL connection string",
    }

    missing = []
    for key, description in required.items():
        if not os.getenv(key):
            missing.append(f"  {RED}✗{RESET} {key} — {description}")

    if missing:
        print(f"\n{RED}Missing required environment variables:{RESET}")
        for m in missing:
            print(m)
        print(f"\n{YELLOW}Add these to your .env file and try again.{RESET}")
        sys.exit(1)

    print_success("All environment variables present")


# ── FETCH PARTS FROM POSTGRESQL ───────────────────────────────────────────────

def fetch_parts_from_db() -> list:
    """
    Fetches all parts from the inventory table in PostgreSQL
    Returns list of dicts with part details
    """
    try:
        import psycopg2
        import psycopg2.extras

        conn = psycopg2.connect(os.getenv("DATABASE_URL"))
        cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

        cursor.execute("""
            SELECT
                part_number,
                description,
                category,
                subcategory,
                oem_part_number,
                brand,
                unit_of_measure,
                unit_cost,
                sell_price,
                compatible_makes,
                compatible_models,
                compatible_years,
                compatible_fuel_types,
                bin_location,
                qty_on_hand,
                reorder_point,
                stock_status
            FROM inventory
            ORDER BY category, subcategory, part_number
        """)

        parts = [dict(row) for row in cursor.fetchall()]
        cursor.close()
        conn.close()
        return parts

    except Exception as e:
        print_error(f"Failed to fetch parts from PostgreSQL: {e}")
        print_warning("Is PostgreSQL running? Try: docker-compose up -d postgres")
        sys.exit(1)


# ── BUILD EMBEDDING TEXT ──────────────────────────────────────────────────────

def build_embedding_text(part: dict) -> str:
    """
    Builds a rich text description for each part.

    This is the most important function in this script.
    The quality of embeddings depends entirely on the quality
    of this text — it must capture:
    - What the part IS (category, subcategory)
    - What it DOES (description)
    - What vehicles it FITS (make, model, year, fuel type)
    - What SYMPTOMS it relates to (derived from category)
    - Brand and part number for exact lookups

    The Intake Agent searches this text with a complaint like:
    "grinding noise from front wheels when braking"
    and finds brake pads, rotors, calipers — not random parts.
    """

    # Parse JSON fields if they're strings
    def parse_json_field(field):
        if isinstance(field, str):
            try:
                return json.loads(field)
            except:
                return []
        return field or []

    compatible_makes       = parse_json_field(part.get("compatible_makes", []))
    compatible_models      = parse_json_field(part.get("compatible_models", []))
    compatible_years       = parse_json_field(part.get("compatible_years", []))
    compatible_fuel_types  = parse_json_field(part.get("compatible_fuel_types", []))

    # Format year range cleanly
    if compatible_years and compatible_years != ["All"]:
        years_sorted = sorted(compatible_years)
        if len(years_sorted) > 2:
            year_str = f"{years_sorted[0]}-{years_sorted[-1]}"
        else:
            year_str = " ".join(str(y) for y in years_sorted)
    else:
        year_str = "all years"

    # Format makes and models
    makes_str  = " ".join(compatible_makes) if compatible_makes else "universal"
    models_str = " ".join(compatible_models) if compatible_models else "all models"
    fuels_str  = " ".join(compatible_fuel_types) if compatible_fuel_types else "all fuel types"

    # Symptom hints by category — critical for semantic search accuracy
    # These are the actual complaint phrases service advisors use
    symptom_hints = {
        "Brakes": (
            "brake noise grinding squeaking squealing brake pedal soft spongy "
            "vibration shaking steering wheel braking car pulls left right "
            "brake warning light brake fluid low"
        ),
        "Filters": (
            "service due oil change filter replacement periodic maintenance "
            "engine oil consumption smoke exhaust dirty air filter "
            "reduced engine performance fuel efficiency"
        ),
        "Fluids": (
            "oil change service maintenance coolant level low overheating "
            "transmission fluid ATF gear shifting rough automatic gearbox "
            "temperature warning light"
        ),
        "Electrical": (
            "battery dead not starting car wont start battery warning light "
            "alternator charging electrical accessories not working "
            "dashboard lights flickering horn not working"
        ),
        "Ignition": (
            "engine not starting rough idle misfiring engine shaking "
            "poor fuel economy spark plug replacement ignition service "
            "check engine light P0300 misfire"
        ),
        "Suspension": (
            "bouncing rough ride clunking noise suspension bumps "
            "car pulling one side uneven tyre wear steering vibration "
            "highway speed knocking creaking wheel area"
        ),
        "Engine": (
            "timing belt replacement engine noise ticking overheating "
            "coolant level dropping oil consumption white smoke "
            "rough idle engine shaking wont start"
        ),
        "EV Components": (
            "EV battery range reduced not charging full charge port error "
            "onboard charger fault regenerative braking not working "
            "battery warning light power loss sudden EV system error "
            "high voltage battery management system BMS fault"
        ),
        "Exterior": (
            "wiper blade replacement streaking smearing monsoon rain "
            "visibility poor windscreen wiper not clearing"
        ),
    }

    category    = part.get("category", "")
    subcategory = part.get("subcategory", "")
    symptoms    = symptom_hints.get(category, "")

    # OEM part number context
    oem_context = ""
    if part.get("oem_part_number"):
        oem_context = f"OEM part number {part['oem_part_number']}. "

    # Build the final embedding text
    # Format: structured but natural language for best embedding quality
    text = (
        f"{part['part_number']} {part['description']} "
        f"Category {category} subcategory {subcategory}. "
        f"Brand {part.get('brand', 'generic')}. "
        f"{oem_context}"
        f"Compatible with {makes_str} vehicles "
        f"models {models_str} "
        f"years {year_str} "
        f"fuel type {fuels_str}. "
        f"Related symptoms and complaints: {symptoms}"
    )

    return text.strip()


# ── PINECONE SETUP ────────────────────────────────────────────────────────────

def setup_pinecone_index():
    """
    Creates Pinecone index if it doesn't exist
    Uses text-embedding-3-small dimensions = 1536
    """
    try:
        from pinecone import Pinecone, ServerlessSpec

        api_key    = os.getenv("PINECONE_API_KEY")
        index_name = os.getenv("PINECONE_INDEX_NAME")

        pc = Pinecone(api_key=api_key)

        # Check if index already exists
        existing_indexes = [idx.name for idx in pc.list_indexes()]

        if index_name in existing_indexes:
            print_success(f"Index '{index_name}' already exists")
            index = pc.Index(index_name)
            stats = index.describe_index_stats()
            current_vectors = stats.get("total_vector_count", 0)
            print_stat("Current vectors in index", current_vectors)

            if current_vectors > 0:
                print_warning(
                    f"Index already has {current_vectors} vectors. "
                    f"Script will upsert (update existing + add new)."
                )
            return pc, index

        # Create new index
        print_warning(f"Index '{index_name}' not found — creating...")

        pc.create_index(
            name=index_name,
            dimension=1536,          # text-embedding-3-small output dimension
            metric="cosine",          # cosine similarity for semantic search
            spec=ServerlessSpec(
                cloud="aws",
                region="us-east-1"    # Pinecone free tier default region
            )
        )

        # Wait for index to be ready
        print_warning("Waiting for index to initialize...")
        max_wait = 60
        waited = 0
        while waited < max_wait:
            index_info = pc.describe_index(index_name)
            if index_info.status.get("ready", False):
                break
            time.sleep(3)
            waited += 3
            print(f"  {YELLOW}...{waited}s{RESET}", end="\r")

        print_success(f"Index '{index_name}' created and ready")
        index = pc.Index(index_name)
        return pc, index

    except ImportError:
        print_error("pinecone not installed. Run: pip install pinecone")
        sys.exit(1)
    except Exception as e:
        print_error(f"Pinecone setup failed: {e}")
        sys.exit(1)


# ── GENERATE EMBEDDINGS ───────────────────────────────────────────────────────

def generate_embeddings(texts: list) -> list:
    """
    Generates embeddings using OpenAI text-embedding-3-small
    Batches requests to avoid rate limits
    Returns list of embedding vectors
    """
    try:
        from openai import OpenAI

        client     = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        embeddings = []
        batch_size = 10  # process 10 texts at a time

        for i in range(0, len(texts), batch_size):
            batch = texts[i:i + batch_size]

            response = client.embeddings.create(
                model="text-embedding-3-small",
                input=batch
            )

            batch_embeddings = [item.embedding for item in response.data]
            embeddings.extend(batch_embeddings)

            print_success(
                f"Embedded batch {i//batch_size + 1}/"
                f"{(len(texts) + batch_size - 1)//batch_size} "
                f"({len(embeddings)}/{len(texts)} parts)"
            )

            # Small delay to respect rate limits
            if i + batch_size < len(texts):
                time.sleep(0.5)

        return embeddings

    except ImportError:
        print_error("openai not installed. Run: pip install openai")
        sys.exit(1)
    except Exception as e:
        print_error(f"Embedding generation failed: {e}")
        sys.exit(1)


# ── UPSERT TO PINECONE ────────────────────────────────────────────────────────

def upsert_to_pinecone(index, parts: list, embeddings: list):
    """
    Upserts vectors to Pinecone with rich metadata
    Metadata is returned with search results so agents
    get full part details without a separate DB lookup
    """

    def parse_json_field(field):
        if isinstance(field, str):
            try:
                return json.loads(field)
            except:
                return []
        return field or []

    def to_string_list(value):
        if value is None:
            return []
        if not isinstance(value, list):
            value = [value]
        return [str(item) for item in value if item is not None and str(item) != ""]

    vectors = []

    for part, embedding in zip(parts, embeddings):

        compatible_makes  = to_string_list(parse_json_field(part.get("compatible_makes", [])))
        compatible_models = to_string_list(parse_json_field(part.get("compatible_models", [])))
        compatible_years  = to_string_list(parse_json_field(part.get("compatible_years", [])))
        fuel_types        = to_string_list(parse_json_field(part.get("compatible_fuel_types", [])))

        # Metadata stored alongside vector in Pinecone
        # Pinecone metadata values must be str, int, float, bool, or list
        metadata = {
            "part_number":      part["part_number"],
            "description":      part["description"],
            "category":         part.get("category", ""),
            "subcategory":      part.get("subcategory", ""),
            "brand":            part.get("brand", ""),
            "unit_cost":        float(part.get("unit_cost", 0)),
            "sell_price":       float(part.get("sell_price", 0)),
            "bin_location":     part.get("bin_location", ""),
            "qty_on_hand":      int(part.get("qty_on_hand", 0)),
            "stock_status":     part.get("stock_status", "unknown"),
            "compatible_makes": compatible_makes,
            "compatible_models": compatible_models,
            "compatible_years": compatible_years,
            "fuel_types":       fuel_types,
            "is_ev_part":       part.get("category") == "EV Components",
            "oem_part_number":  part.get("oem_part_number") or "",
        }

        vectors.append({
            "id":       part["part_number"],   # part_number as vector ID
            "values":   embedding,
            "metadata": metadata,
        })

    # Upsert in batches of 100 (Pinecone limit per request)
    batch_size = 100
    total_upserted = 0

    for i in range(0, len(vectors), batch_size):
        batch = vectors[i:i + batch_size]
        index.upsert(vectors=batch)
        total_upserted += len(batch)
        print_success(
            f"Upserted {total_upserted}/{len(vectors)} vectors to Pinecone"
        )
        time.sleep(0.2)

    return total_upserted


# ── VERIFICATION ──────────────────────────────────────────────────────────────

def verify_with_test_search(index):
    """
    Runs 3 test semantic searches to confirm RAG is working
    These simulate real Intake Agent queries
    """
    try:
        from openai import OpenAI

        client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

        test_queries = [
            {
                "complaint": "grinding noise from front wheels when braking",
                "expected_category": "Brakes",
            },
            {
                "complaint": "car not starting battery warning light on",
                "expected_category": "Electrical",
            },
            {
                "complaint": "10000 km service oil change due",
                "expected_category": "Filters",
            },
        ]

        print(f"\n  {BOLD}Test Semantic Searches:{RESET}")

        for test in test_queries:
            # Embed the query
            response = client.embeddings.create(
                model="text-embedding-3-small",
                input=test["complaint"]
            )
            query_vector = response.data[0].embedding

            # Search Pinecone
            results = index.query(
                vector=query_vector,
                top_k=3,
                include_metadata=True
            )

            print(f"\n  {CYAN}Query:{RESET} \"{test['complaint']}\"")

            if results.matches:
                for i, match in enumerate(results.matches[:3]):
                    score     = match.score
                    part_num  = match.metadata.get("part_number", "?")
                    desc      = match.metadata.get("description", "?")[:60]
                    category  = match.metadata.get("category", "?")
                    qty       = match.metadata.get("qty_on_hand", 0)

                    status_icon = (
                        GREEN if match.metadata.get("stock_status") == "healthy"
                        else YELLOW if match.metadata.get("stock_status") == "low"
                        else RED
                    )

                    print(
                        f"  {i+1}. [{score:.3f}] {part_num} — "
                        f"{desc}... "
                        f"{status_icon}(qty:{qty}){RESET}"
                    )

                # Check top result is in expected category
                top_category = results.matches[0].metadata.get("category", "")
                if test["expected_category"].lower() in top_category.lower():
                    print_success(
                        f"Category match: expected '{test['expected_category']}' "
                        f"got '{top_category}'"
                    )
                else:
                    print_warning(
                        f"Category mismatch: expected '{test['expected_category']}' "
                        f"got '{top_category}'"
                    )
            else:
                print_warning("No results returned")

            time.sleep(0.3)

    except Exception as e:
        print_warning(f"Verification search failed: {e}")
        print_warning("Index was seeded but test search encountered an error")


# ── MAIN ──────────────────────────────────────────────────────────────────────

def main():
    print_header()
    total_steps = 6
    start_time  = time.time()

    # Step 1 — Validate env vars
    print_step(1, total_steps, "Validating environment variables...")
    validate_env()

    # Step 2 — Fetch parts from PostgreSQL
    print_step(2, total_steps, "Fetching parts catalog from PostgreSQL...")
    parts = fetch_parts_from_db()
    print_success(f"Fetched {len(parts)} parts from inventory table")

    if not parts:
        print_error(
            "No parts found in inventory table. "
            "Run generate_all.py first."
        )
        sys.exit(1)

    # Show breakdown
    categories = {}
    for p in parts:
        cat = p.get("category", "Unknown")
        categories[cat] = categories.get(cat, 0) + 1
    for cat, count in categories.items():
        print_stat(cat, f"{count} parts")

    # Step 3 — Build embedding texts
    print_step(3, total_steps, "Building embedding texts...")
    embedding_texts = []
    for part in parts:
        text = build_embedding_text(part)
        embedding_texts.append(text)

    print_success(f"Built {len(embedding_texts)} embedding texts")
    print_stat("Sample text (first part)", embedding_texts[0][:120] + "...")

    # Step 4 — Setup Pinecone index
    print_step(4, total_steps, "Setting up Pinecone index...")
    pc, index = setup_pinecone_index()

    # Step 5 — Generate embeddings + upsert
    print_step(5, total_steps, "Generating embeddings and uploading to Pinecone...")
    embeddings = generate_embeddings(embedding_texts)
    print_success(f"Generated {len(embeddings)} embeddings")
    print_stat(
        "Embedding dimensions",
        len(embeddings[0]) if embeddings else 0
    )

    total_upserted = upsert_to_pinecone(index, parts, embeddings)
    print_success(f"Successfully upserted {total_upserted} vectors")

    # Step 6 — Verify with test searches
    print_step(6, total_steps, "Verifying with semantic search tests...")
    time.sleep(2)  # small wait for Pinecone to index
    verify_with_test_search(index)

    # Summary
    elapsed = time.time() - start_time
    print(f"\n{BOLD}{GREEN}")
    print("=" * 60)
    print("   Pinecone Seeding Complete!")
    print("=" * 60)
    print(f"{RESET}")

    print_stat("Parts embedded",       total_upserted)
    print_stat("Index name",           os.getenv("PINECONE_INDEX_NAME"))
    print_stat("Embedding model",      "text-embedding-3-small")
    print_stat("Vector dimensions",    "1536")
    print_stat("Similarity metric",    "cosine")
    print_stat("Time taken",           f"{elapsed:.1f} seconds")

    print(f"\n{GREEN}✓ Intake Agent RAG is ready!{RESET}")
    print(f"\n{CYAN}Next step:{RESET} Write database/connection.py")
    print(f"  then start building the agents!\n")


if __name__ == "__main__":
    main()