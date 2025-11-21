"""TasoFind Flask application."""
from __future__ import annotations

from flask import Flask, jsonify, render_template, request

from word_lookup import lookup_word, paraphrase_sentence

app = Flask(__name__, static_folder='static', static_url_path='/static')


@app.get("/")
def index() -> str:
    """Render the main search page."""
    return render_template("index.html")


@app.get("/api/lookup")
def lookup() -> tuple:
    """Return synonym, antonym, related word, and example lists for the word."""
    word = request.args.get("word", "").strip()
    if not word:
        return jsonify({"error": "A 'word' query parameter is required."}), 400

    try:
        result = lookup_word(word)
    except Exception as exc:  # pragma: no cover - defensive guard for production
        app.logger.exception("Word lookup failed", exc_info=exc)
        return jsonify({"error": "Unable to process the request right now."}), 500

    return jsonify(result)


@app.post("/api/paraphrase")
def paraphrase() -> tuple:
    """Generate paraphrased variations of a sentence."""
    data = request.get_json()
    if not data or "sentence" not in data:
        return jsonify({"error": "A 'sentence' field is required in the request body."}), 400

    sentence = data.get("sentence", "").strip()
    num_variations = data.get("num_variations", 5)
    style = data.get("style", "balanced")  # balanced, formal, casual, academic, simple
    length_preference = data.get("length_preference", "same")  # same, shorter, longer
    anti_detection = data.get("anti_detection", False)  # Turnitin-proof mode
    
    if not sentence:
        return jsonify({"error": "Sentence cannot be empty."}), 400

    try:
        result = paraphrase_sentence(
            sentence, 
            num_variations=int(num_variations),
            style=style,
            length_preference=length_preference,
            anti_detection=anti_detection
        )
        # Debug logging
        app.logger.info(f"Paraphrase result: {len(result.get('variations', []))} variations for sentence: {sentence[:50]}")
        if result.get('variations'):
            app.logger.info(f"First variation: {result['variations'][0]}")
    except Exception as exc:  # pragma: no cover - defensive guard for production
        app.logger.exception("Paraphrase failed", exc_info=exc)
        return jsonify({"error": "Unable to process the request right now."}), 500

    return jsonify(result)


@app.post("/api/bulk-paraphrase")
def bulk_paraphrase() -> tuple:
    """Generate paraphrased variations for multiple sentences/paragraphs."""
    data = request.get_json()
    if not data or "paragraphs" not in data:
        return jsonify({"error": "A 'paragraphs' array is required in the request body."}), 400

    paragraphs = data.get("paragraphs", [])
    num_variations = data.get("num_variations", 3)
    style = data.get("style", "balanced")
    length_preference = data.get("length_preference", "same")
    
    if not paragraphs or not isinstance(paragraphs, list):
        return jsonify({"error": "Paragraphs must be a non-empty array."}), 400
    
    if len(paragraphs) > 50:
        return jsonify({"error": "Maximum 50 paragraphs allowed at once."}), 400

    results = []
    errors = []
    
    try:
        for idx, paragraph in enumerate(paragraphs):
            if not paragraph or not paragraph.strip():
                errors.append({"index": idx, "error": "Empty paragraph"})
                continue
                
            try:
                result = paraphrase_sentence(
                    paragraph.strip(),
                    num_variations=int(num_variations),
                    style=style,
                    length_preference=length_preference
                )
                results.append({
                    "index": idx,
                    "original": paragraph.strip(),
                    "success": True,
                    "result": result
                })
            except Exception as exc:
                app.logger.exception(f"Paraphrase failed for paragraph {idx}", exc_info=exc)
                errors.append({
                    "index": idx,
                    "original": paragraph.strip()[:100],
                    "error": "Processing failed"
                })
                
        return jsonify({
            "success": len(results),
            "errors": len(errors),
            "results": results,
            "errors_detail": errors,
            "settings": {
                "num_variations": num_variations,
                "style": style,
                "length_preference": length_preference
            }
        })
    except Exception as exc:  # pragma: no cover - defensive guard for production
        app.logger.exception("Bulk paraphrase failed", exc_info=exc)
        return jsonify({"error": "Unable to process the request right now."}), 500


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)
