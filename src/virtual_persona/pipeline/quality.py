from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List


@dataclass
class AssetQualityTrace:
    face_similarity: float | None = None
    scene_logic_score: float = 0.0
    hand_integrity_flag: bool = True
    body_consistency_flag: bool = True
    artifact_flags: List[str] = field(default_factory=list)
    prompt_mode: str = "dense"
    reference_pack_used: str = "fallback"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "face_similarity": self.face_similarity,
            "scene_logic_score": self.scene_logic_score,
            "hand_integrity_flag": self.hand_integrity_flag,
            "body_consistency_flag": self.body_consistency_flag,
            "artifact_flags": ", ".join(self.artifact_flags),
            "prompt_mode": self.prompt_mode,
            "reference_pack_used": self.reference_pack_used,
        }


class FaceConsistencyScorer:
    def __init__(self, threshold: float = 0.35) -> None:
        self.threshold = threshold

    def score(self, generated_embedding: List[float] | None, reference_embedding: List[float] | None) -> float | None:
        if not generated_embedding or not reference_embedding or len(generated_embedding) != len(reference_embedding):
            return None
        dot = sum(a * b for a, b in zip(generated_embedding, reference_embedding))
        g_norm = sum(a * a for a in generated_embedding) ** 0.5
        r_norm = sum(b * b for b in reference_embedding) ** 0.5
        if g_norm == 0 or r_norm == 0:
            return None
        return max(-1.0, min(1.0, dot / (g_norm * r_norm)))

    def passed(self, similarity: float | None) -> bool:
        if similarity is None:
            return True
        return similarity >= self.threshold


class SceneSanityChecker:
    RULE_FLAGS = {
        "seated_table_shot": ["impossible seated geometry", "feet on table unless explicitly requested", "floating shoe"],
        "mirror_selfie": ["broken mirror reflection", "phone geometry mismatch"],
        "kitchen": ["broken mug handle", "hand intersecting cup"],
    }

    def evaluate(self, metadata: Dict[str, Any]) -> Dict[str, Any]:
        flags: List[str] = []
        shot = str(metadata.get("shot_archetype") or "")
        location = str(metadata.get("location") or "").lower()

        flags.extend(self.RULE_FLAGS.get(shot, [] if shot else []))
        if "kitchen" in location:
            flags.extend(self.RULE_FLAGS["kitchen"])

        manual = metadata.get("manual_reject_reason")
        if manual:
            flags.append(f"manual_reject:{manual}")

        logic_score = max(0.0, 1.0 - 0.15 * len(flags))
        return {"scene_logic_score": round(logic_score, 2), "artifact_flags": flags}


class CandidateRanker:
    def rank(self, candidates: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        def _score(row: Dict[str, Any]) -> float:
            sim = float(row.get("face_similarity") or 0)
            scene = float(row.get("scene_logic_score") or 0)
            penalty = len([f for f in str(row.get("artifact_flags") or "").split(",") if f.strip()]) * 0.08
            return sim * 0.6 + scene * 0.4 - penalty

        return sorted(candidates, key=_score, reverse=True)
