"""
Nous Scallop Sidecar — Probabilistic Reasoning Layer (v2)

Architecture: CozoDB (System of Record) → Scallop (Sidecar Reasoner)
- CozoDB: deterministic hard gate (L1)
- Scallop: probabilistic evidence aggregation via KG multi-hop (L1.5)

v2 changes (GPT-5.4 critique fixes):
- Unified program source (no dead SCALLOP_PROGRAM string)
- KG risk rules ACTUALLY connected to decision chain
- Non-mirror rules: multi-hop KG path propagation
- action_pattern → attack_technique → tactic chain
- Honest naming (margin not uncertainty, fired_results not rules_fired)
"""
import json
import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import scallopy

logger = logging.getLogger("nous.scallop_sidecar")


@dataclass
class ScallopVerdict:
    """Scallop probabilistic reasoning result."""
    p_block: float
    p_allow: float
    margin: float           # |p_block - p_allow| — renamed from "uncertainty"
    decision: str           # "block" | "allow" | "review" | "uncertain"
    evidence: list          # triggered evidence paths (renamed from proof_paths)
    latency_ms: float
    kg_paths_found: int     # actual KG paths used in reasoning
    fired_results: int      # number of result tuples

    @property
    def is_low_margin(self) -> bool:
        return self.margin < 0.3

    def to_dict(self) -> dict:
        return {
            "p_block": round(self.p_block, 4),
            "p_allow": round(self.p_allow, 4),
            "margin": round(self.margin, 4),
            "decision": self.decision,
            "evidence": self.evidence[:10],
            "latency_ms": round(self.latency_ms, 3),
            "kg_paths_found": self.kg_paths_found,
            "fired_results": self.fired_results,
        }


class ScallopSidecar:
    """Scallop probabilistic reasoning sidecar.

    KG multi-hop chain:
      act:<function> ←BELONGS_TO← ap:<pattern> →INSTANTIATES→ attack:technique:<T>
      ←CONTAINS← attack:tactic:<TA> ←EXPLOITED_BY← category:<cat>

    This is the NON-MIRROR value: CozoDB pattern-matches action_type,
    Scallop traces through KG to find indirect risk signals with 
    confidence propagation.
    """

    def __init__(self, db=None, provenance: str = "topkproofs"):
        self.provenance = provenance
        self._static_entities = []
        self._static_relations = []
        self._kg_loaded = False
        self._kg_version = None

        if db is not None:
            self._load_kg(db)

    def _load_kg(self, db):
        """Preload KG from CozoDB into memory."""
        t0 = time.perf_counter()

        try:
            ents = db.query(
                '?[id, etype, props, confidence] := '
                '*entity{id, etype, props, confidence}'
            )
            rels = db.query(
                '?[from_id, to_id, rtype, confidence] := '
                '*relation{from_id, to_id, rtype, confidence}'
            )

            self._static_entities = []
            self._static_relations = []

            for e in ents:
                props = e.get('props') or {}
                if isinstance(props, str):
                    try:
                        props = json.loads(props)
                    except (json.JSONDecodeError, TypeError):
                        props = {}
                name = props.get('name', '') or e['id']
                conf = float(e.get('confidence') or 1.0)
                if conf <= 0:
                    conf = 1.0
                self._static_entities.append((conf, (e['id'], e['etype'], name)))

            for r in rels:
                conf = float(r.get('confidence') or 1.0)
                if conf <= 0:
                    conf = 1.0
                self._static_relations.append(
                    (conf, (r['from_id'], r['to_id'], r['rtype']))
                )

            self._kg_loaded = True
            self._kg_version = time.time()
            load_ms = (time.perf_counter() - t0) * 1000
            logger.info(
                "KG loaded: %d entities, %d relations in %.1fms",
                len(self._static_entities), len(self._static_relations), load_ms
            )
        except Exception as exc:
            logger.warning("KG load failed (non-fatal): %s", exc)

    def reload_kg(self, db):
        """Force reload KG (call after KG updates)."""
        self._load_kg(db)

    def _build_context(self) -> scallopy.ScallopContext:
        """Build a ScallopContext with all rules and static KG.
        
        Single source of truth for the Scallop program.
        Rules are split into three tiers:
          Tier 1: Mirror rules (same as CozoDB, for baseline parity)
          Tier 2: KG-backed rules (non-mirror, Scallop's unique value)
          Tier 3: Aggregation
        """
        ctx = scallopy.ScallopContext(provenance=self.provenance)

        # === Base Relations ===
        ctx.add_relation("entity", (str, str, str))
        ctx.add_relation("kg_rel", (str, str, str))
        ctx.add_relation("action_type", (str,))
        ctx.add_relation("tool_name", (str,))
        ctx.add_relation("has_signal", (str,))

        # === Derived Relations ===
        ctx.add_relation("hard_block", (str,))
        ctx.add_relation("soft_block", (str,))
        ctx.add_relation("trivial_allow", (str,))
        ctx.add_relation("should_block", (str,))
        ctx.add_relation("should_allow", (str,))
        # KG-derived
        ctx.add_relation("action_has_pattern", (str, str))     # (act_id, pattern_id)
        ctx.add_relation("pattern_attack", (str, str))          # (pattern_id, technique_id)
        ctx.add_relation("attack_in_tactic", (str, str))        # (technique_id, tactic_id)
        ctx.add_relation("category_uses_tactic", (str, str))    # (category_id, tactic_id)
        ctx.add_relation("kg_risk_signal", (str, str, str))     # (tool_name, risk_path, reason)
        ctx.add_relation("kg_soft_block", (str,))               # KG-derived soft block

        # ============================================================
        # TIER 1: Mirror Rules (CozoDB parity)
        # ============================================================
        for action in ["delete_file", "modify_config", "exec_destructive", "write_protected"]:
            ctx.add_rule(f'hard_block("T3: {action}") = action_type("{action}")')

        ctx.add_rule('hard_block("T5: social URL") = has_signal("url_has_social_pattern")')
        ctx.add_rule(
            'hard_block("T-disinfo: election") = '
            'has_signal("has_factual_correction_signal"), '
            'has_signal("has_election_disinformation_signal")'
        )
        ctx.add_rule('soft_block("T3-soft: publish") = action_type("publish_post")')
        ctx.add_rule('soft_block("T3-upload: upload") = action_type("upload")')
        ctx.add_rule('trivial_allow("trivial: calendar") = action_type("create_calendar_event")')
        ctx.add_rule('trivial_allow("trivial: benign") = has_signal("is_trivial")')

        # ============================================================
        # TIER 2: KG-Backed Non-Mirror Rules (Scallop's unique value)
        # ============================================================
        # Chain: act:<fn> ←BELONGS_TO← ap:<pattern> →INSTANTIATES→ attack:technique:<T>
        #        ←CONTAINS← attack:tactic:<TA>
        
        # Step 1: tool_name → patterns that BELONG_TO this specific action
        ctx.add_rule(
            'action_has_pattern(tname, pat_id) = '
            'tool_name(tname), '
            'kg_rel(pat_id, tname, "BELONGS_TO")'
        )

        # Step 2: pattern → attack technique it INSTANTIATES
        ctx.add_rule(
            'pattern_attack(pat_id, tech_id) = '
            'entity(pat_id, "action_pattern", _), '
            'kg_rel(pat_id, tech_id, "INSTANTIATES")'
        )

        # Step 3: technique → tactic it belongs to (via CONTAINS)
        ctx.add_rule(
            'attack_in_tactic(tech_id, tactic_id) = '
            'entity(tech_id, "attack_technique", _), '
            'kg_rel(tactic_id, tech_id, "CONTAINS")'
        )

        # Step 4: category → tactic (EXPLOITED_BY)
        ctx.add_rule(
            'category_uses_tactic(cat_id, tactic_id) = '
            'entity(cat_id, "category", _), '
            'kg_rel(cat_id, tactic_id, "EXPLOITED_BY")'
        )

        # COMPOSITE: tool_name → act → pattern → attack technique (2 hops)
        # Join: tool_name must match the act entity ID (act:<tool_name>)
        ctx.add_rule(
            'kg_risk_signal(tname, pat_id, "2hop") = '
            'tool_name(tname), '
            'kg_rel(pat_id, tname, "BELONGS_TO"), '
            'entity(pat_id, "action_pattern", _), '
            'kg_rel(pat_id, tech_id, "INSTANTIATES"), '
            'entity(tech_id, "attack_technique", _)'
        )

        # COMPOSITE: tool_name → act → pattern → attack → tactic (3 hops)
        ctx.add_rule(
            'kg_risk_signal(tname, tactic_id, "3hop") = '
            'tool_name(tname), '
            'kg_rel(pat_id, tname, "BELONGS_TO"), '
            'entity(pat_id, "action_pattern", _), '
            'kg_rel(pat_id, tech_id, "INSTANTIATES"), '
            'entity(tech_id, "attack_technique", _), '
            'kg_rel(tactic_id, tech_id, "CONTAINS")'
        )

        # KG risk → soft block (if any KG risk path found)
        ctx.add_rule(
            'kg_soft_block("kg_risk") = kg_risk_signal(_, _, _)'
        )

        # ============================================================
        # TIER 3: Aggregation
        # ============================================================
        ctx.add_rule('should_block(r) = hard_block(r)')
        ctx.add_rule('should_block(r) = soft_block(r)')
        ctx.add_rule('should_block(r) = kg_soft_block(r)')
        ctx.add_rule('should_allow(r) = trivial_allow(r)')
        # Default allow: only if nothing blocks
        ctx.add_rule(
            'should_allow("default: no block signal") = '
            'tool_name(_), ~should_block(_)'
        )

        # === Load Static KG ===
        if self._kg_loaded:
            ctx.add_facts("entity", self._static_entities)
            ctx.add_facts("kg_rel", self._static_relations)

        return ctx

    def evaluate(self, tool_call: dict, facts: dict) -> ScallopVerdict:
        """Run probabilistic evaluation on a single request.

        Injects request-scoped facts into a pre-built Scallop program
        with KG multi-hop rules.
        """
        t0 = time.perf_counter()

        ctx = self._build_context()

        # === Inject Request Facts ===
        atype = facts.get("action_type", "")
        if atype:
            action_conf = facts.get("action_confidence", 1.0)
            if not isinstance(action_conf, (int, float)):
                action_conf = 1.0
            ctx.add_facts("action_type", [(float(action_conf), (atype,))])

        # Tool name — use both the raw tool_name AND map to act: entity ID
        tname = facts.get("tool_name", "") or tool_call.get("tool_name", "")
        if tname:
            ctx.add_facts("tool_name", [(1.0, (tname,))])
            # Also add as act:<tname> for KG lookup
            act_id = f"act:{tname}"
            ctx.add_facts("tool_name", [(1.0, (act_id,))])

        # Signals
        signal_keys = [
            "url_has_social_pattern",
            "has_factual_correction_signal",
            "has_election_disinformation_signal",
            "is_trivial",
            "has_celebration_signal",
        ]
        for sk in signal_keys:
            if facts.get(sk):
                ctx.add_facts("has_signal", [(1.0, (sk,))])

        # === Run ===
        ctx.run()

        # === Read Results ===
        blocks = list(ctx.relation("should_block"))
        allows = list(ctx.relation("should_allow"))
        hard_blocks = list(ctx.relation("hard_block"))
        soft_blocks_raw = list(ctx.relation("soft_block"))
        kg_soft_blocks = list(ctx.relation("kg_soft_block"))
        kg_risk_signals = list(ctx.relation("kg_risk_signal"))

        # Probabilities
        p_hard_block = max((b[0] for b in hard_blocks), default=0.0)
        p_soft_block = max((b[0] for b in soft_blocks_raw), default=0.0)
        p_kg_block = max((b[0] for b in kg_soft_blocks), default=0.0)
        p_block = max((b[0] for b in blocks), default=0.0)
        p_allow = max((a[0] for a in allows), default=0.0)

        is_only_soft = p_hard_block == 0.0 and (p_soft_block > 0.0 or p_kg_block > 0.0)

        # Normalize
        total = p_block + p_allow
        if total > 0:
            p_block_norm = p_block / total
            p_allow_norm = p_allow / total
        else:
            p_block_norm = 0.0
            p_allow_norm = 1.0

        margin = abs(p_block_norm - p_allow_norm)

        # Decision
        HARD_BLOCK_THRESHOLD = 0.7
        if p_hard_block >= HARD_BLOCK_THRESHOLD:
            decision = "block"
        elif is_only_soft:
            decision = "review"
        elif p_block_norm >= HARD_BLOCK_THRESHOLD:
            decision = "block"
        elif p_block_norm >= 0.3:
            decision = "review"
        elif margin < 0.2:
            decision = "uncertain"
        else:
            decision = "allow"

        # Evidence
        evidence = []
        for b in hard_blocks:
            evidence.append({"tier": "mirror", "type": "hard_block", "prob": round(b[0], 4), "reason": b[1][0]})
        for b in soft_blocks_raw:
            evidence.append({"tier": "mirror", "type": "soft_block", "prob": round(b[0], 4), "reason": b[1][0]})
        for b in kg_soft_blocks:
            evidence.append({"tier": "kg", "type": "kg_soft_block", "prob": round(b[0], 4), "reason": b[1][0]})
        for a in allows:
            evidence.append({"tier": "agg", "type": "allow", "prob": round(a[0], 4), "reason": a[1][0]})
        for s in kg_risk_signals:
            evidence.append({
                "tier": "kg",
                "type": "kg_risk_signal",
                "prob": round(s[0], 4),
                "tool": s[1][0],
                "path": s[1][1],
                "chain": s[1][2],
            })

        latency_ms = (time.perf_counter() - t0) * 1000

        return ScallopVerdict(
            p_block=p_block_norm,
            p_allow=p_allow_norm,
            margin=margin,
            decision=decision,
            evidence=evidence,
            latency_ms=latency_ms,
            kg_paths_found=len(kg_risk_signals),
            fired_results=len(blocks) + len(allows),
        )


# ── Singleton ─────────────────────────────────────────────────────────────

_sidecar: Optional[ScallopSidecar] = None


def get_sidecar(db=None) -> ScallopSidecar:
    """Get or create singleton ScallopSidecar.
    
    If db is provided and sidecar has no KG, reload.
    """
    global _sidecar
    if _sidecar is None:
        _sidecar = ScallopSidecar(db=db)
    elif db is not None and not _sidecar._kg_loaded:
        _sidecar.reload_kg(db)
    return _sidecar


def scallop_evaluate(tool_call: dict, facts: dict, db=None) -> ScallopVerdict:
    """Convenience function for shadow mode integration."""
    sidecar = get_sidecar(db)
    return sidecar.evaluate(tool_call, facts)
