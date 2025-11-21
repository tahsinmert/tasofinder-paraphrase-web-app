"""Utility helpers powering TasoFind word discovery features."""
from __future__ import annotations

import random
import re
from typing import Dict, List, Optional, Set, Tuple

import nltk
from nltk.corpus import wordnet as wn
from nltk.tag import pos_tag
from nltk.tokenize import word_tokenize

_WORDNET_PACKAGES = ("wordnet", "omw-1.4", "punkt", "punkt_tab", "averaged_perceptron_tagger", "averaged_perceptron_tagger_eng")


def _ensure_wordnet_data() -> None:
    """Download lexical datasets if they are missing."""
    for package in _WORDNET_PACKAGES:
        try:
            if package in ("punkt", "punkt_tab"):
                if package == "punkt_tab":
                    nltk.data.find("tokenizers/punkt_tab")
                else:
                    nltk.data.find(f"tokenizers/{package}")
            elif package in ("averaged_perceptron_tagger", "averaged_perceptron_tagger_eng"):
                if package == "averaged_perceptron_tagger_eng":
                    nltk.data.find("taggers/averaged_perceptron_tagger_eng")
                else:
                    nltk.data.find(f"taggers/{package}")
            else:
                nltk.data.find(f"corpora/{package}")
        except LookupError:
            nltk.download(package, quiet=True)


def _clean_word(word: str) -> str:
    """Normalize the incoming word for querying."""
    return word.strip().lower()


def _collect_lemmas(words: Set[str], synset_words: List[str]) -> None:
    for name in synset_words:
        cleaned = name.replace("_", " ").lower()
        if cleaned:
            words.add(cleaned)


def _lookup_synonyms(word: str) -> Set[str]:
    synonyms: Set[str] = set()
    for synset in wn.synsets(word):
        lemma_names = [lemma.name() for lemma in synset.lemmas()]
        _collect_lemmas(synonyms, lemma_names)
    return synonyms


def _lookup_antonyms(word: str) -> Set[str]:
    antonyms: Set[str] = set()
    for synset in wn.synsets(word):
        for lemma in synset.lemmas():
            for ant in lemma.antonyms():
                antonyms.add(ant.name().replace("_", " ").lower())
    return antonyms


def _lookup_related(word: str) -> Set[str]:
    related: Set[str] = set()
    for synset in wn.synsets(word):
        hypernyms = synset.hypernyms()
        hyponyms = synset.hyponyms()
        for relation in (*hypernyms, *hyponyms):
            lemma_names = [lemma.name() for lemma in relation.lemmas()]
            _collect_lemmas(related, lemma_names)
    return related


def _collect_examples(word: str) -> Set[str]:
    examples: Set[str] = set()
    for synset in wn.synsets(word):
        for example in synset.examples():
            sentence = example.strip()
            if sentence:
                examples.add(sentence)
    return examples


def _get_synonym_formality_score(word: str, synonym: str) -> float:
    """
    Estimate formality score for a synonym.
    Higher score = more formal, lower score = more casual.
    Simple heuristic based on word length and commonality.
    """
    # Longer words tend to be more formal
    length_bonus = len(synonym) / 20.0
    
    # Common informal words
    informal_words = {
        "guy", "kid", "cool", "awesome", "stuff", "thing", "get", "got", "gonna", 
        "wanna", "yeah", "yep", "nah", "nope", "huge", "tiny", "big", "small"
    }
    if synonym.lower() in informal_words:
        return 0.2
    
    # Common formal words
    formal_words = {
        "individual", "personnel", "utilize", "facilitate", "implement", 
        "substantial", "considerable", "significant", "demonstrate", "exhibit"
    }
    if synonym.lower() in formal_words:
        return 0.9
    
    return min(1.0, 0.5 + length_bonus)


def _filter_synonyms_by_style(synonyms: List[str], style: str = "balanced") -> List[str]:
    """Filter synonyms based on style preference."""
    if style == "balanced":
        return synonyms
    
    # Score each synonym
    scored = [(syn, _get_synonym_formality_score("", syn)) for syn in synonyms]
    
    if style == "formal":
        # Prefer more formal synonyms (higher score)
        scored.sort(reverse=True, key=lambda x: x[1])
    elif style == "casual":
        # Prefer more casual synonyms (lower score)
        scored.sort(key=lambda x: x[1])
    elif style == "academic":
        # Prefer formal and longer words
        scored.sort(reverse=True, key=lambda x: (x[1], len(x[0])))
    elif style == "simple":
        # Prefer shorter, simpler words
        scored.sort(key=lambda x: (len(x[0]), x[1]))
    
    return [syn for syn, _ in scored]


def _get_synonyms_for_word(word: str, pos_tag: Optional[str] = None, max_synonyms: int = 10, style: str = "balanced") -> List[str]:
    """Get multiple synonyms for a word, considering part of speech if available."""
    word_lower = word.lower()
    
    # Try with POS tag first, then without
    synsets = []
    if pos_tag:
        synsets = wn.synsets(word_lower, pos=_map_pos_tag(pos_tag))
    if not synsets:
        synsets = wn.synsets(word_lower)
    
    if not synsets:
        return []
    
    synonyms: Set[str] = set()
    
    # Collect synonyms from multiple synsets (up to 5 most common)
    for synset in synsets[:5]:
        for lemma in synset.lemmas():
            synonym = lemma.name().replace("_", " ").lower()
            # Only single-word synonyms, and not the original word
            if synonym != word_lower and len(synonym.split()) == 1:
                # Filter out very similar words - must be different enough
                if len(synonym) >= 2:  # At least 2 characters
                    # Don't add if it's too similar (same first 2 letters and similar length)
                    if not (synonym[:2] == word_lower[:2] and abs(len(synonym) - len(word_lower)) <= 1):
                        synonyms.add(synonym)
                if len(synonyms) >= max_synonyms:
                    break
        if len(synonyms) >= max_synonyms:
            break
    
    # If still not enough, try related words (hypernyms/hyponyms)
    if len(synonyms) < 3 and synsets:
        for synset in synsets[:2]:
            for hypernym in synset.hypernyms()[:1]:
                for lemma in hypernym.lemmas():
                    synonym = lemma.name().replace("_", " ").lower()
                    if synonym != word_lower and len(synonym.split()) == 1 and len(synonym) >= 3:
                        synonyms.add(synonym)
                        if len(synonyms) >= max_synonyms:
                            break
    
    synonyms_list = list(synonyms)
    
    # Filter by style if specified
    if style != "balanced":
        synonyms_list = _filter_synonyms_by_style(synonyms_list, style)
    
    return synonyms_list[:max_synonyms]


def _map_pos_tag(tag: Optional[str]) -> Optional[str]:
    """Map NLTK POS tag to WordNet POS tag."""
    if not tag:
        return None
    tag = tag.upper()
    if tag.startswith("N"):
        return wn.NOUN
    if tag.startswith("V"):
        return wn.VERB
    if tag.startswith("J"):
        return wn.ADJ
    if tag.startswith("R"):
        return wn.ADV
    return None


def _calculate_variation_score(
    original: str,
    variation: str,
    original_tokens: List[str],
    variation_tokens: List[str],
    word_replacements: Dict[str, List[str]],
    tagged: List[Tuple[str, str]]
) -> float:
    """
    Calculate a quality score for a paraphrase variation.
    Higher score means better paraphrase (preserves meaning while being different).
    
    Scoring factors:
    1. Semantic similarity (using WordNet synsets)
    2. Optimal difference (not too similar, not too different)
    3. Number of word replacements (optimal range)
    4. Word quality (using synonyms from first synsets)
    5. Sentence length preservation
    """
    if not variation or variation.lower() == original.lower():
        return 0.0
    
    original_lower = original.lower()
    variation_lower = variation.lower()
    
    # 1. Calculate word overlap - should be moderate (30-70%)
    original_words = set(token.lower() for token in original_tokens if token.isalnum())
    variation_words = set(token.lower() for token in variation_tokens if token.isalnum())
    
    if not original_words:
        return 0.0
    
    overlap = len(original_words & variation_words) / len(original_words)
    
    # Optimal overlap is 40-70% - too similar or too different is bad
    overlap_score = 1.0
    if overlap < 0.3:  # Too different
        overlap_score = overlap / 0.3
    elif overlap > 0.85:  # Too similar
        overlap_score = 1.0 - ((overlap - 0.85) / 0.15)
    
    # 2. Count meaningful word replacements
    replacements_count = 0
    synonym_quality_score = 0.0
    replacement_details: List[Tuple[str, str]] = []
    
    original_tagged_dict = {idx: (word, pos) for idx, (word, pos) in enumerate(tagged)}
    
    for idx, var_token in enumerate(variation_tokens):
        if idx < len(original_tokens):
            orig_token = original_tokens[idx]
            if orig_token.lower() != var_token.lower() and var_token.isalnum():
                orig_lower = orig_token.lower()
                if orig_lower in word_replacements:
                    # Check if this is a valid synonym replacement
                    if var_token.lower() in [s.lower() for s in word_replacements[orig_lower]]:
                        replacements_count += 1
                        replacement_details.append((orig_lower, var_token.lower()))
                        
                        # Check synonym quality - earlier in synonym list = better
                        synonyms = word_replacements[orig_lower]
                        try:
                            syn_index = [s.lower() for s in synonyms].index(var_token.lower())
                            # First 3 synonyms get highest score
                            if syn_index < 3:
                                synonym_quality_score += 1.0
                            elif syn_index < 5:
                                synonym_quality_score += 0.8
                            else:
                                synonym_quality_score += 0.6
                        except ValueError:
                            synonym_quality_score += 0.4
    
    # Optimal number of replacements: 25-50% of replaceable words
    replaceable_count = len([w for w in original_tokens if w.isalnum() and w.lower() in word_replacements])
    if replaceable_count > 0:
        replacement_ratio = replacements_count / replaceable_count
        replacement_score = 1.0
        if replacement_ratio < 0.2:  # Too few replacements
            replacement_score = replacement_ratio / 0.2
        elif replacement_ratio > 0.7:  # Too many replacements
            replacement_score = 1.0 - ((replacement_ratio - 0.7) / 0.3)
    else:
        replacement_score = 1.0 if replacements_count > 0 else 0.0
    
    # Normalize synonym quality score
    if replacements_count > 0:
        synonym_quality_score = synonym_quality_score / replacements_count
    else:
        synonym_quality_score = 0.0
    
    # 3. Semantic similarity using WordNet synsets
    semantic_score = 1.0
    try:
        original_content_words = [w for w in original_words if w not in {
            "the", "a", "an", "and", "or", "but", "in", "on", "at", "to", "for",
            "of", "with", "by", "is", "are", "was", "were", "be", "been", "have",
            "has", "had", "do", "does", "did", "will", "would", "could", "should"
        }]
        variation_content_words = [w for w in variation_words if w not in {
            "the", "a", "an", "and", "or", "but", "in", "on", "at", "to", "for",
            "of", "with", "by", "is", "are", "was", "were", "be", "been", "have",
            "has", "had", "do", "does", "did", "will", "would", "could", "should"
        }]
        
        if original_content_words and variation_content_words:
            # Check if replaced words share synsets with originals
            shared_synsets = 0
            total_checks = 0
            
            for orig_word, var_word in replacement_details:
                orig_synsets = set(wn.synsets(orig_word))
                var_synsets = set(wn.synsets(var_word))
                
                if orig_synsets and var_synsets:
                    total_checks += 1
                    # Check if they share any synsets (direct synonym)
                    if orig_synsets & var_synsets:
                        shared_synsets += 1
                    else:
                        # Check for semantic similarity through hypernyms/hyponyms
                        orig_hypernyms = set()
                        var_hypernyms = set()
                        for syn in orig_synsets:
                            orig_hypernyms.update(syn.hypernyms())
                            orig_hypernyms.update(syn.hyponyms())
                        for syn in var_synsets:
                            var_hypernyms.update(syn.hypernyms())
                            var_hypernyms.update(syn.hyponyms())
                        
                        if orig_hypernyms & var_hypernyms or orig_hypernyms & var_synsets or var_hypernyms & orig_synsets:
                            shared_synsets += 0.5
            
            if total_checks > 0:
                semantic_score = shared_synsets / total_checks
    except Exception:
        # If semantic check fails, use default score
        pass
    
    # 4. Length preservation - should be similar (±30%)
    length_ratio = len(variation) / len(original) if len(original) > 0 else 1.0
    length_score = 1.0
    if length_ratio < 0.7 or length_ratio > 1.3:
        length_score = 0.5
    
    # 5. Word count similarity
    word_count_diff = abs(len(original_words) - len(variation_words))
    word_count_score = 1.0 - (word_count_diff / max(len(original_words), 1) * 0.5)
    word_count_score = max(0.0, word_count_score)
    
    # Calculate final weighted score
    # Weights: overlap (20%), replacement (25%), synonym quality (25%), semantic (20%), length (10%)
    final_score = (
        overlap_score * 0.20 +
        replacement_score * 0.25 +
        synonym_quality_score * 0.25 +
        semantic_score * 0.20 +
        length_score * 0.05 +
        word_count_score * 0.05
    )
    
    # Bonus for having reasonable number of replacements (2-5)
    if 2 <= replacements_count <= 5:
        final_score *= 1.1
    elif replacements_count == 0:
        final_score *= 0.3
    
    return min(1.0, final_score)


def _should_replace_word(word: str, pos_tag: Optional[str]) -> bool:
    """Determine if a word should be replaced in paraphrase."""
    if not word:
        return False
    
    # Skip punctuation and special characters
    if not word.isalnum() and not word.replace("'", "").isalnum():
        return False
    
    if len(word) < 3:
        return False
    
    # Skip common stop words
    stop_words = {
        "the", "a", "an", "and", "or", "but", "in", "on", "at", "to", "for",
        "of", "with", "by", "is", "are", "was", "were", "be", "been", "have",
        "has", "had", "do", "does", "did", "will", "would", "could", "should",
        "this", "that", "these", "those", "it", "its", "he", "she", "they"
    }
    if word.lower() in stop_words:
        return False
    
    # Only replace nouns, verbs, adjectives, and adverbs
    if pos_tag:
        tag = pos_tag.upper()
        return tag.startswith(("N", "V", "J", "R"))
    return True


def _calculate_variation_stats(
    original: str,
    variation: str,
    original_tokens: List[str],
    variation_tokens: List[str],
    word_replacements: Dict[str, List[str]]
) -> Dict[str, any]:
    """Calculate detailed statistics for a variation."""
    original_words = set(token.lower() for token in original_tokens if token.isalnum())
    variation_words = set(token.lower() for token in variation_tokens if token.isalnum())
    
    overlap = len(original_words & variation_words)
    total_original = len(original_words)
    similarity = (overlap / total_original * 100) if total_original > 0 else 0
    
    # Count word changes
    changes = 0
    changed_words = []
    for idx in range(min(len(original_tokens), len(variation_tokens))):
        if original_tokens[idx].lower() != variation_tokens[idx].lower():
            if original_tokens[idx].isalnum() and variation_tokens[idx].isalnum():
                changes += 1
                changed_words.append({
                    "from": original_tokens[idx],
                    "to": variation_tokens[idx]
                })
    
    length_diff = len(variation) - len(original)
    length_percent = ((len(variation) - len(original)) / len(original) * 100) if len(original) > 0 else 0
    
    return {
        "similarity_percent": round(similarity, 1),
        "word_changes": changes,
        "changed_words": changed_words,
        "length_diff": length_diff,
        "length_percent": round(length_percent, 1),
        "original_length": len(original),
        "variation_length": len(variation)
    }


def _rearrange_sentence_structure(tokens: List[str], tagged: List[Tuple[str, str]]) -> List[str]:
    """
    Rearrange sentence structure by moving phrases and changing word order.
    Advanced strategy to break n-gram patterns detected by AI systems.
    """
    if len(tokens) < 4:
        return tokens
    
    new_tokens = list(tokens)
    
    # Strategy: Find and rearrange noun phrases and verb phrases
    # Move adjectives to different positions
    adjectives = []
    nouns = []
    verbs = []
    adverbs = []
    
    for i, (token, (word, pos)) in enumerate(zip(tokens, tagged)):
        pos_upper = pos.upper()
        if pos_upper.startswith('JJ'):  # Adjectives
            adjectives.append((i, token))
        elif pos_upper.startswith('NN'):  # Nouns
            nouns.append((i, token))
        elif pos_upper.startswith('VB'):  # Verbs
            verbs.append((i, token))
        elif pos_upper.startswith('RB'):  # Adverbs
            adverbs.append((i, token))
    
    # Try to rearrange: move adjectives or adverbs
    if len(adjectives) >= 2 and len(tokens) > 5:
        # Swap positions of first two adjectives if they're not consecutive
        adj_indices = [i for i, _ in adjectives[:2]]
        if len(adj_indices) == 2 and abs(adj_indices[0] - adj_indices[1]) > 1:
            try:
                new_tokens[adj_indices[0]], new_tokens[adj_indices[1]] = \
                    new_tokens[adj_indices[1]], new_tokens[adj_indices[0]]
            except:
                pass
    
    # Move adverbs to different positions
    if len(adverbs) >= 1 and len(nouns) >= 1:
        # Try moving adverb to end or beginning
        if len(new_tokens) > 3:
            adv_idx = adverbs[0][0]
            if adv_idx > 0 and adv_idx < len(new_tokens) - 1:
                # Move adverb to end
                adv_token = new_tokens[adv_idx]
                new_tokens = [t for i, t in enumerate(new_tokens) if i != adv_idx]
                new_tokens.append(adv_token)
    
    return new_tokens


def _create_turnitin_proof_paraphrase(
    original: str,
    tokens: List[str],
    tagged: List[Tuple[str, str]],
    word_replacements: Dict[str, List[str]],
    replaceable_words: List[Tuple[int, str, str]]
) -> Optional[str]:
    """
    Create an advanced Turnitin-proof paraphrase using multiple strategies:
    1. Maximum synonym replacement (85-95% of words)
    2. Sentence structure rearrangement
    3. Active/passive voice conversion attempts
    4. Word order randomization
    5. N-gram pattern breaking
    6. Structural pattern changes
    """
    if not replaceable_words or len(replaceable_words) < 1:
        return None
    
    new_tokens = list(tokens)
    
    # Strategy 1: Replace MAXIMUM replaceable words (85-95%) with least common synonyms
    replacements_made = 0
    replace_count = max(1, int(len(replaceable_words) * random.uniform(0.85, 0.95)))
    words_to_replace = random.sample(replaceable_words, min(replace_count, len(replaceable_words)))
    
    for idx, word, pos in words_to_replace:
        word_lower = word.lower()
        if word_lower in word_replacements and word_replacements[word_lower]:
            synonyms = word_replacements[word_lower]
            # ALWAYS prefer least common synonyms (last 30% of list)
            if len(synonyms) > 3:
                # Choose from last 30% (least common, most different)
                start_idx = max(len(synonyms) - len(synonyms) // 3, len(synonyms) // 2)
                replacement = random.choice(synonyms[start_idx:])
            elif len(synonyms) > 1:
                # Choose from last item (least common)
                replacement = random.choice(synonyms[-1:])
            else:
                replacement = synonyms[0]
            
            # Preserve capitalization
            if word and word[0].isupper():
                replacement = replacement.capitalize()
            
            new_tokens[idx] = replacement
            replacements_made += 1
    
    # Strategy 2: Rearrange sentence structure
    try:
        new_tokens = _rearrange_sentence_structure(new_tokens, tagged)
    except:
        pass  # If rearrangement fails, continue with current tokens
    
    # Strategy 3: Apply multiple structural transformations
    sentence_text = " ".join(new_tokens)
    sentence_lower = sentence_text.lower()
    
    # Advanced pattern replacements for structure changes
    structural_changes = [
        # Active to passive-like transformations
        (r'\b(the|a|an)?\s*(\w+)\s+(is|are|was|were)\s+(\w+ed)\s+by\s+(\w+)', r'\5 \4 \2'),  # "X is done by Y" -> "Y done X"
        (r'\b(is|are|was|were)\s+(\w+ed)\s+by\s+(\w+)', r'\3 \2'),  # "is done by X" -> "X done"
        
        # Verb-adverb reordering
        (r'\b(\w+)\s+(\w+ly)\s+(\w+)', r'\1 \3 \2'),  # "verb quickly noun" -> "verb noun quickly"
        (r'\b(is|are|was|were)\s+(\w+ly)\s+(\w+)', r'\3 \2'),  # "is quickly done" -> "done quickly"
        
        # Adjective-noun reordering (some contexts)
        (r'\b(very|quite|rather|extremely)\s+(\w+)\s+(\w+)', r'\3 \2'),  # "very good idea" -> "idea good"
        
        # Pronoun substitution attempts
        (r'\b(it|this|that)\s+is\s+', r'this demonstrates '),  # "it is" -> "this demonstrates"
        (r'\b(we|they)\s+(\w+)\s+', r'the process \2 '),  # "we do" -> "the process do"
    ]
    
    # Sentence starter variations (handled separately due to lambda)
    def replace_starter(match):
        return random.choice(['this', 'such', 'one']) + ' '
    
    def replace_pronoun(match):
        return 'the aforementioned '
    
    # Apply structural changes (try multiple)
    for pattern, replacement in structural_changes[:6]:  # Limit to avoid over-processing
        if re.search(pattern, sentence_lower, re.IGNORECASE):
            try:
                sentence_text = re.sub(pattern, replacement, sentence_text, flags=re.IGNORECASE, count=1)
                # Only apply first successful transformation
                break
            except:
                pass
    
    # Sentence starter variations (applied separately)
    if re.search(r'^(the|a|an)\s+', sentence_text, re.IGNORECASE):
        try:
            sentence_text = re.sub(r'^(the|a|an)\s+', replace_starter, sentence_text, flags=re.IGNORECASE, count=1)
        except:
            pass
    
    if re.search(r'^(this|that|it)\s+', sentence_text, re.IGNORECASE):
        try:
            sentence_text = re.sub(r'^(this|that|it)\s+', replace_pronoun, sentence_text, flags=re.IGNORECASE, count=1)
        except:
            pass
    
    # Strategy 4: Add sentence restructuring phrases
    # Add transition words at the beginning if sentence is long enough
    if len(sentence_text.split()) > 6:
        starters = ['Furthermore,', 'Additionally,', 'Moreover,', 'Notably,', 'Specifically,']
        if not sentence_text[0].isupper() or sentence_text.split()[0] not in starters:
            # Randomly add starter (30% chance)
            if random.random() < 0.3:
                sentence_text = random.choice(starters) + ' ' + sentence_text[0].lower() + sentence_text[1:] if len(sentence_text) > 1 else sentence_text
    
    # Strategy 5: Rearrange phrases by moving prepositional phrases
    # Pattern: "verb noun preposition phrase" -> "verb preposition phrase noun"
    prep_pattern = r'\b(\w+)\s+(\w+)\s+(in|on|at|by|with|for|to|from|of|about|under|over)\s+(\w+(?:\s+\w+){0,3})'
    if re.search(prep_pattern, sentence_lower):
        try:
            def rearrange_prep(match):
                verb = match.group(1)
                noun = match.group(2)
                prep = match.group(3)
                phrase = match.group(4)
                # Rearrange: "verb noun prep phrase" -> "verb prep phrase noun"
                return f"{verb} {prep} {phrase} {noun}"
            sentence_text = re.sub(prep_pattern, rearrange_prep, sentence_text, count=1, flags=re.IGNORECASE)
        except:
            pass
    
    # Fix punctuation
    sentence_text = re.sub(r"\s+([.,!?;:])", r"\1", sentence_text)
    sentence_text = re.sub(r"([.,!?;:])\s*([.,!?;:])", r"\1\2", sentence_text)
    sentence_text = re.sub(r"\s+", " ", sentence_text).strip()
    
    # Strategy 6: Calculate advanced similarity metrics
    original_words = set(w.lower() for w in tokens if w.isalnum())
    new_words = set(w.lower() for w in sentence_text.split() if w.isalnum())
    
    if not original_words:
        return None
    
    # Word-level similarity
    word_overlap = len(original_words & new_words)
    word_change_rate = 1 - (word_overlap / len(original_words))
    
    # N-gram similarity (2-grams and 3-grams)
    def get_ngrams(tokens_list, n):
        return [tuple(tokens_list[i:i+n]) for i in range(len(tokens_list)-n+1)]
    
    original_2grams = set(get_ngrams([w.lower() for w in tokens if w.isalnum()], 2))
    new_2grams = set(get_ngrams([w.lower() for w in sentence_text.split() if w.isalnum()], 2))
    
    original_3grams = set(get_ngrams([w.lower() for w in tokens if w.isalnum()], 3))
    new_3grams = set(get_ngrams([w.lower() for w in sentence_text.split() if w.isalnum()], 3))
    
    if original_2grams:
        bigram_overlap = len(original_2grams & new_2grams) / len(original_2grams)
        bigram_change_rate = 1 - bigram_overlap
    else:
        bigram_change_rate = word_change_rate
    
    if original_3grams:
        trigram_overlap = len(original_3grams & new_3grams) / len(original_3grams)
        trigram_change_rate = 1 - trigram_overlap
    else:
        trigram_change_rate = word_change_rate
    
    # Combined change rate (weighted: words 40%, bigrams 30%, trigrams 30%)
    combined_change_rate = (word_change_rate * 0.4) + (bigram_change_rate * 0.3) + (trigram_change_rate * 0.3)
    
    # Only return if significantly different:
    # - At least 70% word change
    # - At least 60% bigram change  
    # - At least 50% trigram change
    # - Combined change rate at least 65%
    # - And actually different from original
    if (word_change_rate >= 0.70 and 
        bigram_change_rate >= 0.60 and 
        trigram_change_rate >= 0.50 and
        combined_change_rate >= 0.65 and
        sentence_text.lower() != original.lower() and
        len(sentence_text) > 0):
        return sentence_text
    
    # Fallback: if main strategy fails, return if at least 75% word change
    if word_change_rate >= 0.75 and sentence_text.lower() != original.lower():
        return sentence_text
    
    return None


def paraphrase_sentence(
    sentence: str, 
    num_variations: int = 5,
    style: str = "balanced",
    length_preference: str = "same",
    anti_detection: bool = False
) -> Dict[str, List[str]]:
    """Generate paraphrased variations of a sentence by replacing words with synonyms."""
    _ensure_wordnet_data()
    
    if not sentence or not sentence.strip():
        return {
            "original": "",
            "variations": [],
                "variation_stats": [],
                "best_variation": "",
                "best_score": 0.0,
            "word_replacements": {},
        }
    
    original = sentence.strip()
    
    try:
        # Tokenize and tag
        tokens = word_tokenize(original)
        tagged = pos_tag(tokens)
        
        # Build word replacement map - collect all possible synonyms
        word_replacements: Dict[str, List[str]] = {}
        replaceable_words: List[Tuple[int, str, str]] = []  # (index, word, pos)
        
        # Collect synonyms for each replaceable word
        for idx, (word, pos) in enumerate(tagged):
            if _should_replace_word(word, pos):
                synonyms_list = _get_synonyms_for_word(word, pos, max_synonyms=15, style=style)
                if synonyms_list:
                    word_lower = word.lower()
                    word_replacements[word_lower] = synonyms_list
                    replaceable_words.append((idx, word, pos))
        
        # If no synonyms found, return early
        if not word_replacements or not replaceable_words:
            stats = _calculate_variation_stats(original, original, tokens, tokens, {})
            stats["score"] = 0.0
            return {
                "original": original,
                "variations": [original],
                "variation_stats": [stats],
                "best_variation": original,
                "best_score": 0.0,
                "style": style,
                "length_preference": length_preference,
                "word_replacements": {},
            }
        
        variations: List[str] = []
        seen_variations: Set[str] = set()
        
        # Anti-detection mode: Create Turnitin-proof paraphrase first
        turnitin_proof = None
        if anti_detection:
            turnitin_proof = _create_turnitin_proof_paraphrase(
                original, tokens, tagged, word_replacements, replaceable_words
            )
            if turnitin_proof and turnitin_proof.lower() not in seen_variations:
                variations.append(turnitin_proof)
                seen_variations.add(turnitin_proof.lower())
        
        # Generate variations - ensure each one is different
        for variation_num in range(num_variations * 5):  # Try more times
            if len(variations) >= num_variations:
                break
                
            # In anti-detection mode, be more aggressive with replacements
            if anti_detection:
                # Replace 85-95% of replaceable words (maximum aggressiveness)
                replace_count = max(1, int(len(replaceable_words) * random.uniform(0.85, 0.95)))
                words_to_replace = random.sample(replaceable_words, min(replace_count, len(replaceable_words)))
            else:
                words_to_replace = random.sample(
                    replaceable_words, 
                    min(len(replaceable_words), random.randint(1, len(replaceable_words)))
                )
                
            new_tokens = list(tokens)  # Start with original tokens
            replacements_made = 0
            
            # Replace selected words
            for idx, word, pos in words_to_replace:
                word_lower = word.lower()
                if word_lower in word_replacements:
                    synonyms = word_replacements[word_lower]
                    if synonyms:
                        if anti_detection:
                            # In anti-detection mode, ALWAYS prefer least common synonyms (last 30%)
                            if len(synonyms) > 3:
                                start_idx = max(len(synonyms) - len(synonyms) // 3, len(synonyms) // 2)
                                replacement = random.choice(synonyms[start_idx:])
                            elif len(synonyms) > 1:
                                replacement = random.choice(synonyms[-1:])  # Last synonym (least common)
                            else:
                                replacement = synonyms[0]
                        else:
                            replacement = random.choice(synonyms)
                        # Preserve capitalization
                        if word and word[0].isupper():
                            replacement = replacement.capitalize()
                        new_tokens[idx] = replacement
                        replacements_made += 1
            
            if replacements_made > 0:
                variation = " ".join(new_tokens)
                # Fix punctuation spacing
                variation = re.sub(r"\s+([.,!?;:])", r"\1", variation)
                variation = re.sub(r"([.,!?;:])\s*([.,!?;:])", r"\1\2", variation)
                variation = re.sub(r"\s+", " ", variation).strip()
                variation_lower = variation.lower()
                
                # In anti-detection mode, ensure minimum 70% word change (much more aggressive)
                if anti_detection:
                    original_words = set(w.lower() for w in tokens if w.isalnum())
                    variation_words = set(w.lower() for w in variation.split() if w.isalnum())
                    if original_words:
                        overlap = len(original_words & variation_words) / len(original_words)
                        change_rate = 1 - overlap
                        if change_rate < 0.70:  # Less than 70% change - skip (too similar)
                            continue
                        
                        # Also check n-gram similarity for anti-detection
                        def get_ngrams(word_list, n):
                            return [tuple(word_list[i:i+n]) for i in range(len(word_list)-n+1)]
                        
                        orig_word_list = [w.lower() for w in tokens if w.isalnum()]
                        var_word_list = [w.lower() for w in variation.split() if w.isalnum()]
                        
                        orig_2grams = set(get_ngrams(orig_word_list, 2))
                        var_2grams = set(get_ngrams(var_word_list, 2))
                        if orig_2grams:
                            bigram_overlap = len(orig_2grams & var_2grams) / len(orig_2grams)
                            if bigram_overlap > 0.55:  # More than 55% bigram overlap - skip
                                continue
                
                # Only add if different from original and not seen before
                if (variation_lower != original.lower() and 
                    variation_lower not in seen_variations and
                    len(variation) > 0):
                    variations.append(variation)
                    seen_variations.add(variation_lower)
        
        # If still no variations, force at least one replacement
        if not variations and replaceable_words:
            new_tokens = list(tokens)
            # Replace the first replaceable word
            idx, word, pos = replaceable_words[0]
            word_lower = word.lower()
            if word_lower in word_replacements and word_replacements[word_lower]:
                replacement = word_replacements[word_lower][0]
                if word and word[0].isupper():
                    replacement = replacement.capitalize()
                new_tokens[idx] = replacement
                variation = " ".join(new_tokens)
                variation = re.sub(r"\s+([.,!?;:])", r"\1", variation)
                variation = re.sub(r"\s+", " ", variation).strip()
                if variation.lower() != original.lower():
                    variations.append(variation)
        
        # If still no variations, return original
        if not variations:
            variations = [original]
        
        # Filter by length preference
        if length_preference != "same":
            filtered_variations = []
            original_length = len(original)
            
            for variation in variations:
                var_length = len(variation)
                length_ratio = var_length / original_length if original_length > 0 else 1.0
                
                if length_preference == "shorter" and length_ratio < 0.95:
                    filtered_variations.append(variation)
                elif length_preference == "longer" and length_ratio > 1.05:
                    filtered_variations.append(variation)
                elif length_preference == "same" and 0.9 <= length_ratio <= 1.1:
                    filtered_variations.append(variation)
            
            if filtered_variations:
                variations = filtered_variations[:num_variations * 2]  # Keep more for scoring
        
        # Score and rank all variations
        variation_tokens_list = [word_tokenize(v) for v in variations]
        scored_variations = []
        variation_stats_list = []
        
        for i, (variation, var_tokens) in enumerate(zip(variations, variation_tokens_list)):
            score = _calculate_variation_score(
                original, variation, tokens, var_tokens, word_replacements, tagged
            )
            
            # Calculate detailed stats
            stats = _calculate_variation_stats(
                original, variation, tokens, var_tokens, word_replacements
            )
            stats["score"] = round(score, 3)
            
            scored_variations.append((score, variation, i, stats))
            variation_stats_list.append(stats)
        
        # Sort by score (highest first)
        scored_variations.sort(reverse=True, key=lambda x: x[0])
        
        # Get best variation (highest score)
        best_variation = scored_variations[0][1] if scored_variations else variations[0]
        best_score = scored_variations[0][0] if scored_variations else 0.0
        
        # Return top variations (best first) with stats
        ranked_variations = []
        ranked_stats = []
        for score, variation, idx, stats in scored_variations[:num_variations]:
            ranked_variations.append(variation)
            ranked_stats.append(stats)
        
        return {
            "original": original,
            "variations": ranked_variations,
            "variation_stats": ranked_stats,
            "best_variation": best_variation,
            "best_score": round(best_score, 3),
            "turnitin_proof": turnitin_proof if anti_detection else None,
            "style": style,
            "length_preference": length_preference,
            "anti_detection": anti_detection,
            "word_replacements": {k: sorted(v) for k, v in word_replacements.items()},
        }
    
    except Exception as e:
        # Log error but still return something useful
        import traceback
        print(f"Paraphrase error: {e}")
        print(traceback.format_exc())
        # Fallback: return original sentence
        try:
            tokens = word_tokenize(original)
            stats = _calculate_variation_stats(original, original, tokens, tokens, {})
            stats["score"] = 0.0
        except:
            stats = {"similarity_percent": 100.0, "word_changes": 0, "score": 0.0}
        
        return {
            "original": original,
            "variations": [original],
            "variation_stats": [stats],
            "best_variation": original,
            "best_score": 0.0,
            "style": style,
            "length_preference": length_preference,
            "word_replacements": {},
        }


def lookup_word(raw_word: str) -> Dict[str, List[str]]:
    """Return synonyms, antonyms, related words, and examples for a word."""
    _ensure_wordnet_data()
    word = _clean_word(raw_word)
    if not word:
        return {
            "word": "",
            "synonyms": [],
            "antonyms": [],
            "related": [],
            "examples": [],
        }

    synonyms = _lookup_synonyms(word)
    antonyms = _lookup_antonyms(word)
    related = _lookup_related(word)
    examples = _collect_examples(word)

    # Avoid echoing the same word in results
    for collection in (synonyms, antonyms, related):
        collection.discard(word)

    return {
        "word": word,
        "synonyms": sorted(synonyms),
        "antonyms": sorted(antonyms),
        "related": sorted(related),
        "examples": sorted(examples),
    }
