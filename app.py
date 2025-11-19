import os
import json
import re
from flask import Flask, render_template, request, redirect, url_for

JSON_DIR = "data"   # directory containing individual JSON files
RESULTS_PER_PAGE = 48   # 4 cards × 12 rows per page

app = Flask(__name__)

# miniture descriptions
def load_dataset(json_dir):
    data = []
    for filename in os.listdir(json_dir):
        if filename.endswith(".json"):
            path = os.path.join(json_dir, filename)
            with open(path, "r", encoding="utf-8") as f:
                record = json.load(f)
                record["_filename"] = filename

                record["_search_text"] = " ".join([
                    str(record.get("scene_description_enriched", "")),
                    str(record.get("scene_interpretation", "")),
                    str(record.get("spatial_context", "")),
                    str(record.get("architectural_context", "")),
                    " ".join(record.get("building_types", [])),
                    " ".join(record.get("architectural_elements", [])),
                    " ".join(record.get("persons", [])),
                ]).lower()

                data.append(record)

    return data


# ------------------------------------------------------------
# TOKENIZER
# ------------------------------------------------------------
def tokenize(text):
    return re.findall(r"[a-zA-Z0-9_]+", text.lower())


# ------------------------------------------------------------
# BUILD INVERTED INDEX
# ------------------------------------------------------------
def build_inverted_index(data):
    index = {}
    for i, record in enumerate(data):
        tokens = tokenize(record["_search_text"])
        for token in tokens:
            index.setdefault(token, set()).add(i)
    return index


# Load at startup
DATA = load_dataset(JSON_DIR)
INDEX = build_inverted_index(DATA)


# ------------------------------------------------------------
# SEARCH BY KEYWORDS (global)
# ------------------------------------------------------------
def search_keyword(query):
    if not query.strip():
        return list(range(len(DATA)))

    tokens = tokenize(query)
    first = tokens[0]
    results = INDEX.get(first, set()).copy()

    for t in tokens[1:]:
        results &= INDEX.get(t, set())

    return list(results)



def filter_exact(value, field_value):
    """Exact match for controlled vocabularies."""
    if not value:
        return True
    return value.lower() == str(field_value).lower()

def filter_contains(text, field_value):
    if not text:
        return True
    return text.lower() in str(field_value).lower()

def filter_list(text, values_list):
    if not text:
        return True
    text = text.lower()
    return any(text in v.lower() for v in values_list)


def filter_field(text, field_value):
    """Simple case-insensitive containment."""
    if not text:
        return True
    if not field_value:
        return False
    return text.lower() in field_value.lower()


def filter_list_field(text, values_list):
    """Check containment inside a list field."""
    if not text:
        return True
    joined = " ".join(values_list).lower()
    return text.lower() in joined


def filter_results(indices,
                   f_scene_desc=None,
                   f_scene_interp=None,
                   f_spatial=None,
                   f_arch=None,
                   f_buildings=None,
                   f_elements=None,
                   f_persons=None):
    
    final = []
    for idx in indices:
        rec = DATA[idx]

        # TEXT FIELDS
        if not filter_contains(f_scene_desc, rec.get("scene_description_enriched", "")):
            continue

        if not filter_contains(f_scene_interp, rec.get("scene_interpretation", "")):
            continue

        # CONTROLLED VOCAB (need exact match)
        if not filter_exact(f_spatial, rec.get("spatial_context", "")):
            continue

        if not filter_exact(f_arch, rec.get("architectural_context", "")):
            continue

        # LIST FIELDS
        if not filter_list(f_buildings, rec.get("building_types", [])):
            continue

        if not filter_list(f_elements, rec.get("architectural_elements", [])):
            continue

        if not filter_list(f_persons, rec.get("persons", [])):
            continue

        final.append(rec)

    return final



@app.route("/", methods=["GET", "POST"])
def search_page():

    # Process search request
    if request.method == "POST":
        query = request.form.get("query", "")
        f_scene_desc = request.form.get("f_scene_desc", "")
        f_scene_interp = request.form.get("f_scene_interp", "")
        f_spatial = request.form.get("f_spatial", "")
        f_arch = request.form.get("f_arch", "")
        f_buildings = request.form.get("f_buildings", "")
        f_elements = request.form.get("f_elements", "")
        f_persons = request.form.get("f_persons", "")

        # Redirect to GET with all parameters encoded in URL
        return redirect(url_for("search_page",
                                query=query,
                                f_scene_desc=f_scene_desc,
                                f_scene_interp=f_scene_interp,
                                f_spatial=f_spatial,
                                f_arch=f_arch,
                                f_buildings=f_buildings,
                                f_elements=f_elements,
                                f_persons=f_persons,
                                page=1))

    # get search parameters from URL (GET)
    query = request.args.get("query", "")
    f_scene_desc = request.args.get("f_scene_desc", "")
    f_scene_interp = request.args.get("f_scene_interp", "")
    f_spatial = request.args.get("f_spatial", "")
    f_arch = request.args.get("f_arch", "")
    f_buildings = request.args.get("f_buildings", "")
    f_elements = request.args.get("f_elements", "")
    f_persons = request.args.get("f_persons", "")

    # Pagination
    page = int(request.args.get("page", 1))

 
    # Perform search
    indices = search_keyword(query)
    results_all = filter_results(
        indices,
        f_scene_desc=f_scene_desc,
        f_scene_interp=f_scene_interp,
        f_spatial=f_spatial,
        f_arch=f_arch,
        f_buildings=f_buildings,
        f_elements=f_elements,
        f_persons=f_persons
    )

    total_results = len(results_all)
    total_pages = max(1, (total_results + RESULTS_PER_PAGE - 1) // RESULTS_PER_PAGE)

    # Slice for the current page
    start = (page - 1) * RESULTS_PER_PAGE
    end = start + RESULTS_PER_PAGE
    results_page = results_all[start:end]


    return render_template(
        "search.html",
        results=results_page,
        query=query,
        f_scene_desc=f_scene_desc,
        f_scene_interp=f_scene_interp,
        f_spatial=f_spatial,
        f_arch=f_arch,
        f_buildings=f_buildings,
        f_elements=f_elements,
        f_persons=f_persons,
        page=page,
        total_pages=total_pages,
        total_results=total_results
    )



if __name__ == "__main__":
    print(f"Loaded {len(DATA)} JSON records.")
    app.run(debug=True)
