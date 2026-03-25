"""Nous — 知识图谱数据库 (M1.2 + M1.4 + M11.4)

NousDB: 嵌入式 Cozo 数据库 wrapper
- init_schema(): 创建 6 张表 + entity_version 历史版本表 (M11.4)
- upsert_entities/relations(): 批量幂等写入（含版本化检测）
- query(): 执行原始 Datalog
- find_entity/find_by_type/related/path/search(): 高级查询 API (M1.4)
- get_entity_history/get_entity_at(): 实体历史版本 API (M11.4)
"""
import json
import time
from pathlib import Path
from typing import Optional

from pycozo import Client

from nous.schema import Entity, Relation


class NousDB:
    """Cozo 嵌入式知识图谱数据库"""

    def __init__(self, path: str = "nous.db"):
        """
        初始化 Cozo 嵌入式 DB。

        path: ":memory:" 使用内存模式（测试用），否则使用 SQLite 持久化
        """
        if path == ":memory:":
            self.db = Client("mem", "")
        else:
            self.db = Client("sqlite", path)
        self.init_schema()

    def init_schema(self):
        """按 design.md §4 创建 6+5 张表（已存在则跳过）

        包含 OWL 2 RL 推理规则所需的 5 张表（E1）。
        """
        schemas = [
            # Layer 3: 知识图谱
            """
            :create entity {
                id: String =>
                etype: String,
                labels: [String],
                props: Json,
                metadata: Json,
                confidence: Float default 1.0,
                source: String default '',
                created_at: Float default 0.0,
                updated_at: Float default 0.0
            }
            """,
            """
            :create relation {
                from_id: String,
                to_id: String,
                rtype: String =>
                props: Json,
                confidence: Float default 1.0,
                source: String default '',
                created_at: Float default 0.0
            }
            """,
            """
            :create ontology_class {
                id: String =>
                parent: String default '',
                props_schema: Json,
                constraints: [String]
            }
            """,
            # Layer 2: 决策图谱
            """
            :create constraint {
                id: String =>
                rule_body: String default '',
                verdict: String,
                priority: Int default 0,
                enabled: Bool default true,
                ttl_days: Int default 0,
                metadata: Json,
                created_at: Float default 0.0
            }
            """,
            """
            :create decision_log {
                ts: Float,
                session_key: String =>
                tool_name: String default '',
                facts: Json,
                gates: Json,
                latency_us: Int default 0,
                outcome: String default '',
                proof_trace: Json,
                schema_version: String default '1.0'
            }
            """,
            # Layer 1: 自治理
            """
            :create proposal {
                id: String =>
                constraint_draft: Json,
                trigger_pattern: String default '',
                confidence: Float default 0.0,
                status: String default 'pending',
                created_at: Float default 0.0,
                reviewed_at: Float default 0.0
            }
            """,
            # M11.4: Entity 版本历史表
            # 每次 entity 属性变更时，旧版本数据写入此表保留历史
            """
            :create entity_version {
                entity_id: String,
                version: Int =>
                etype: String,
                labels: [String],
                props: Json,
                metadata: Json,
                confidence: Float default 1.0,
                source: String default '',
                valid_from: Float default 0.0,
                valid_to: Float default 0.0,
                changed_fields: [String]
            }
            """,
        ]

        for schema in schemas:
            try:
                self.db.run(schema)
            except Exception as e:
                err_str = str(e).lower()
                # 表已存在是正常情况：pycozo 抛出 "conflicts with an existing one"
                if (
                    "already exists" in err_str
                    or "alreadyexists" in err_str
                    or "conflicts with an existing" in err_str
                ):
                    pass
                else:
                    # 其他错误重新抛出
                    raise

        # E1: OWL 2 RL 推理规则表
        from nous.owl_rules import init_owl_schema
        init_owl_schema(self)

    def upsert_entities(self, entities: list[Entity], strict: bool = False):
        """批量 upsert entity（幂等）——按 id 覆盖写入
        
        strict=True: required 缺失则拒绝写入
        strict=False: required 缺失仅 warning，仍写入

        M11.4: 写入前先检查旧版本是否存在并有字段变更，若有则写入 entity_version。
        """
        if not entities:
            return

        from nous.type_registry import validate_entity
        
        # 批量构建数据行
        rows = []
        for e in entities:
            vr = validate_entity(e.etype, e.properties)
            if vr.errors:
                if strict:
                    raise ValueError(
                        f"Entity {e.id} validation failed: {'; '.join(vr.errors)}")
                else:
                    import logging
                    logging.getLogger(__name__).warning(
                        f"Entity {e.id} schema warnings: {'; '.join(vr.errors)}")
            if vr.confidence_penalty > 0:
                e.confidence = max(0.1, e.confidence - vr.confidence_penalty)

            # M11.4: 版本化检查——在覆盖写入前保存旧版本
            self._check_and_save_version(e)
            
            rows.append([
                e.id,
                e.etype,
                e.labels,
                e.properties,
                e.metadata,
                e.confidence,
                e.source,
                e.created_at,
                e.updated_at,
            ])

        # 分批写入（每批 50 条，避免单条 Datalog 过长）
        batch_size = 50
        for i in range(0, len(rows), batch_size):
            batch = rows[i:i + batch_size]
            self._batch_put_entities(batch)

    def _check_and_save_version(self, entity: Entity):
        """M11.4 内部方法：检查 entity 是否已存在且有字段变更，若有则将旧版本写入 entity_version。

        变更检测字段：props / labels / metadata / confidence
        新实体（不存在旧记录）不写入 entity_version。
        无变更则跳过，保证幂等性。
        """
        # 查询当前实体是否存在
        existing = self.find_entity(entity.id)
        if existing is None:
            # 新实体，无需版本化
            return

        # 检测各字段是否变更
        changed_fields = []
        if existing.get("props") != entity.properties:
            changed_fields.append("props")
        if existing.get("labels") != entity.labels:
            changed_fields.append("labels")
        if existing.get("metadata") != entity.metadata:
            changed_fields.append("metadata")
        # 浮点比较用容差，避免精度误差误判
        if abs(existing.get("confidence", 1.0) - entity.confidence) > 1e-9:
            changed_fields.append("confidence")

        if not changed_fields:
            # 无变更，跳过版本记录（幂等）
            return

        # 查当前最大 version 号，决定新版本号
        ver_rows = self._query_with_params(
            "?[max(version)] := *entity_version{entity_id, version}, entity_id = $eid",
            {"eid": entity.id},
        )
        # max(version) 列名可能带括号，取第一个值
        if ver_rows:
            raw_max = list(ver_rows[0].values())[0]
            next_version = (int(raw_max) + 1) if raw_max is not None else 1
        else:
            next_version = 1

        now = time.time()
        # valid_from 用旧实体的 updated_at（表示该版本生效的起始时间）
        valid_from = existing.get("updated_at") or existing.get("created_at") or 0.0

        # 将旧版本数据写入 entity_version
        try:
            self.db.run(
                "?[entity_id, version, etype, labels, props, metadata, confidence, "
                "source, valid_from, valid_to, changed_fields] "
                "<- [[$eid, $ver, $etype, $labels, $props, $meta, $conf, $src, $vf, $vt, $cf]] "
                ":put entity_version { entity_id, version => etype, labels, props, metadata, "
                "confidence, source, valid_from, valid_to, changed_fields }",
                {
                    "eid": entity.id,
                    "ver": next_version,
                    "etype": existing.get("etype", ""),
                    "labels": existing.get("labels", []),
                    "props": existing.get("props", {}),
                    "meta": existing.get("metadata", {}),
                    "conf": float(existing.get("confidence", 1.0)),
                    "src": existing.get("source", ""),
                    "vf": float(valid_from),
                    "vt": float(now),
                    "cf": changed_fields,
                },
            )
        except Exception as e:
            raise RuntimeError(
                f"_check_and_save_version failed for {entity.id}: {e}"
            ) from e

    def _batch_put_entities(self, rows: list):
        """内部：批量 put entity 行"""
        # 构建 Datalog 数据字面量
        literals = []
        for r in rows:
            id_, etype, labels, props, meta, conf, src, cat, uat = r
            # pycozo 接受 Python 对象直接传入 Json 列
            literals.append([id_, etype, labels, props, meta, conf, src, cat, uat])

        # 用参数化方式传入数据
        # pycozo run() 支持 params 字典，但批量行更好用 inline 方式
        for lit in literals:
            id_, etype, labels, props, meta, conf, src, cat, uat = lit
            try:
                self.db.run(
                    "?[id, etype, labels, props, metadata, confidence, source, created_at, updated_at] "
                    "<- [[$id, $etype, $labels, $props, $meta, $conf, $src, $cat, $uat]] "
                    ":put entity { id => etype, labels, props, metadata, confidence, source, created_at, updated_at }",
                    {
                        "id": id_,
                        "etype": etype,
                        "labels": labels,
                        "props": props,
                        "meta": meta,
                        "conf": conf,
                        "src": src,
                        "cat": cat,
                        "uat": uat,
                    }
                )
            except Exception as e:
                raise RuntimeError(f"upsert_entity failed for {id_}: {e}") from e

    def upsert_relations(self, relations: list[Relation]):
        """批量 upsert relation（幂等）——按 (from_id, to_id, rtype) 覆盖写入"""
        if not relations:
            return

        for rel in relations:
            try:
                self.db.run(
                    "?[from_id, to_id, rtype, props, confidence, source, created_at] "
                    "<- [[$from_id, $to_id, $rtype, $props, $conf, $src, $cat]] "
                    ":put relation { from_id, to_id, rtype => props, confidence, source, created_at }",
                    {
                        "from_id": rel.from_id,
                        "to_id": rel.to_id,
                        "rtype": rel.rtype,
                        "props": rel.properties,
                        "conf": rel.confidence,
                        "src": rel.source,
                        "cat": rel.created_at,
                    }
                )
            except Exception as e:
                raise RuntimeError(
                    f"upsert_relation failed for {rel.from_id}→{rel.to_id}: {e}"
                ) from e

    def query(self, datalog: str) -> list[dict]:
        """
        执行原始 Datalog 查询。
        返回 list[dict]（每行一个 dict）。
        """
        result = self.db.run(datalog)
        # pycozo 默认返回 pandas DataFrame（dataframe=True）
        if hasattr(result, "to_dict"):
            return result.to_dict(orient="records")
        # fallback：已经是 list
        if isinstance(result, list):
            return result
        return []

    def count_entities(self) -> int:
        """返回 entity 表行数"""
        rows = self.query("?[count(id)] := *entity{id}")
        if rows:
            return list(rows[0].values())[0]
        return 0

    def count_relations(self) -> int:
        """返回 relation 表行数"""
        rows = self.query("?[count(from_id)] := *relation{from_id, to_id, rtype}")
        if rows:
            return list(rows[0].values())[0]
        return 0

    # ── M1.3 支持 ─────────────────────────────────────────────────────────

    def delete_entity(self, entity_id: str):
        """删除一个 entity 及其所有关联关系"""
        # 删关系（from 或 to 匹配的）
        self.db.run(
            "?[from_id, to_id, rtype] := "
            "*relation{from_id, to_id, rtype}, from_id = $eid "
            ":rm relation {from_id, to_id, rtype}",
            {"eid": entity_id},
        )
        self.db.run(
            "?[from_id, to_id, rtype] := "
            "*relation{from_id, to_id, rtype}, to_id = $eid "
            ":rm relation {from_id, to_id, rtype}",
            {"eid": entity_id},
        )
        # 删实体
        self.db.run(
            "?[id] := id = $eid :rm entity {id}",
            {"eid": entity_id},
        )

    # ── M1.4 高级查询 API ──────────────────────────────────────────────

    def find_entity(self, entity_id: str) -> Optional[dict]:
        """根据 ID 精确查找实体，返回 dict 或 None"""
        rows = self._query_with_params(
            "?[id, etype, labels, props, metadata, confidence, source, "
            "created_at, updated_at] := "
            "*entity{id, etype, labels, props, metadata, confidence, "
            "source, created_at, updated_at}, id = $eid",
            {"eid": entity_id},
        )
        return rows[0] if rows else None

    def find_by_type(self, etype: str) -> list[dict]:
        """按类型查找所有实体"""
        return self._query_with_params(
            "?[id, etype, labels, props, confidence, source] := "
            "*entity{id, etype, labels, props, confidence, source}, "
            "etype = $et",
            {"et": etype},
        )

    def related(
        self,
        entity_id: str,
        rtype: Optional[str] = None,
        direction: str = "out",
        rank_by_effective: bool = False,
    ) -> list[dict]:
        """
        查找实体的直接关系邻居。

        direction: "out"(出边), "in"(入边), "both"(双向)
        rtype: 可选过滤关系类型
        rank_by_effective: 若 True，按 effective_confidence（含衰减）降序排列
        """
        results = []

        if direction in ("out", "both"):
            q = (
                "?[to_id, rtype, props, confidence, created_at] := "
                "*relation{from_id, to_id, rtype, props, confidence, created_at}, "
                "from_id = $eid"
            )
            if rtype:
                q += ", rtype = $rt"
            rows = self._query_with_params(q, {"eid": entity_id, "rt": rtype or ""})
            for r in rows:
                r["direction"] = "out"
            results.extend(rows)

        if direction in ("in", "both"):
            q = (
                "?[from_id, rtype, props, confidence, created_at] := "
                "*relation{from_id, to_id, rtype, props, confidence, created_at}, "
                "to_id = $eid"
            )
            if rtype:
                q += ", rtype = $rt"
            rows = self._query_with_params(q, {"eid": entity_id, "rt": rtype or ""})
            for r in rows:
                r["direction"] = "in"
            results.extend(rows)

        if rank_by_effective and results:
            from nous.edge_weight import rank_relations_by_effective_confidence
            results = rank_relations_by_effective_confidence(results)

        return results

    def record_relation_access(self, from_id: str, to_id: str, rtype: str):
        """记录关系被访问（M11.2 使用频率反馈）。

        更新 relation.props 中的 last_accessed 和 access_count。
        """
        from nous.edge_weight import record_access
        import json as _json

        rows = self._query_with_params(
            "?[props, confidence, source, created_at] := "
            "*relation{from_id, to_id, rtype, props, confidence, source, created_at}, "
            "from_id = $fid, to_id = $tid, rtype = $rt",
            {"fid": from_id, "tid": to_id, "rt": rtype},
        )
        if not rows:
            return

        row = rows[0]
        old_props = row["props"] if isinstance(row["props"], dict) else {}
        new_props = record_access(old_props)

        self.db.run(
            "?[from_id, to_id, rtype, props, confidence, source, created_at] "
            "<- [[$fid, $tid, $rt, $props, $conf, $src, $cat]] "
            ":put relation { from_id, to_id, rtype => props, confidence, source, created_at }",
            {
                "fid": from_id, "tid": to_id, "rt": rtype,
                "props": new_props, "conf": row["confidence"],
                "src": row["source"], "cat": row["created_at"],
            },
        )

    def path(
        self,
        from_id: str,
        to_id: str,
        max_hops: int = 3,
    ) -> list[dict]:
        """
        查找两个实体之间的路径（BFS，最多 max_hops 跳）。

        返回路径中的节点和边列表。
        Cozo 不原生支持可变长度路径，所以逐跳展开。
        """
        # 1 跳
        one_hop = self._query_with_params(
            "?[from_id, rtype, to_id] := "
            "*relation{from_id, to_id, rtype}, "
            "from_id = $fid, to_id = $tid",
            {"fid": from_id, "tid": to_id},
        )
        if one_hop:
            return [{"hops": 1, "path": one_hop}]

        if max_hops < 2:
            return []

        # 2 跳
        two_hop = self._query_with_params(
            "?[mid, r1, r2] := "
            "*relation{from_id: f, to_id: mid, rtype: r1}, "
            "*relation{from_id: mid, to_id: t, rtype: r2}, "
            "f = $fid, t = $tid",
            {"fid": from_id, "tid": to_id},
        )
        if two_hop:
            return [{"hops": 2, "path": two_hop}]

        if max_hops < 3:
            return []

        # 3 跳
        three_hop = self._query_with_params(
            "?[m1, m2, r1, r2, r3] := "
            "*relation{from_id: f, to_id: m1, rtype: r1}, "
            "*relation{from_id: m1, to_id: m2, rtype: r2}, "
            "*relation{from_id: m2, to_id: t, rtype: r3}, "
            "f = $fid, t = $tid",
            {"fid": from_id, "tid": to_id},
        )
        if three_hop:
            return [{"hops": 3, "path": three_hop}]

        return []

    def search(self, keyword: str) -> list[dict]:
        """
        在实体名称和属性中搜索关键词（大小写不敏感）。

        用 Cozo str_includes 实现。
        """
        # 搜索 props 的 JSON 字符串表示中是否包含关键词
        return self._query_with_params(
            '?[id, etype, props, confidence] := '
            '*entity{id, etype, props, confidence}, '
            'json_str = to_string(props), '
            'str_includes(lowercase(json_str), lowercase($kw))',
            {"kw": keyword},
        )

    def _query_with_params(self, datalog: str, params: dict) -> list[dict]:
        """执行带参数的 Datalog 查询"""
        result = self.db.run(datalog, params)
        if hasattr(result, "to_dict"):
            return result.to_dict(orient="records")
        if isinstance(result, list):
            return result
        return []

    # ── E1: OWL 2 RL 推理 ─────────────────────────────────────────────

    def run_owl_reasoning(self) -> dict:
        """执行 OWL 2 RL 推理并物化结果。返回推理统计。"""
        from nous.owl_rules import materialize_inferences
        return materialize_inferences(self)

    def inferred_type(self, entity_id: str) -> list[dict]:
        """查询实体的推导类型。"""
        from nous.owl_rules import inferred_types
        return inferred_types(self, entity_id)

    def inferred_relations(self, entity_id: str,
                           direction: str = "out") -> list[dict]:
        """查询实体的推导关系。"""
        from nous.owl_rules import inferred_relations as _ir
        return _ir(self, entity_id, direction)

    # ── M11.4: Entity 版本化 API ───────────────────────────────────────

    def get_entity_history(self, entity_id: str) -> list[dict]:
        """M11.4: 查询实体的完整版本历史列表，按版本号升序返回。

        返回格式：
          [
            {version, etype, labels, props, metadata, confidence,
             source, valid_from, valid_to, changed_fields},
            ...
          ]
        """
        rows = self._query_with_params(
            "?[version, etype, labels, props, metadata, confidence, "
            "source, valid_from, valid_to, changed_fields] := "
            "*entity_version{entity_id, version, etype, labels, props, metadata, "
            "confidence, source, valid_from, valid_to, changed_fields}, "
            "entity_id = $eid",
            {"eid": entity_id},
        )
        # 按版本号升序排列，保证历史顺序正确
        return sorted(rows, key=lambda r: r.get("version", 0))

    def get_entity_at(self, entity_id: str, timestamp: float) -> Optional[dict]:
        """M11.4: 返回实体在指定时间点的快照。

        查找策略：
        1. 先从 entity_version 中找 valid_from <= ts < valid_to 的历史版本
        2. 若未找到历史版本（时间点在当前版本之后），直接返回当前实体
        3. 若实体完全不存在，返回 None

        Args:
            entity_id: 实体 ID
            timestamp: 查询时间点（epoch seconds）

        Returns:
            实体快照 dict，或 None（实体不存在）
        """
        # 从历史版本表中查找指定时间点所在区间
        rows = self._query_with_params(
            "?[version, etype, labels, props, metadata, confidence, "
            "source, valid_from, valid_to, changed_fields] := "
            "*entity_version{entity_id, version, etype, labels, props, metadata, "
            "confidence, source, valid_from, valid_to, changed_fields}, "
            "entity_id = $eid, "
            "valid_from <= $ts, "
            "$ts < valid_to",
            {"eid": entity_id, "ts": timestamp},
        )
        if rows:
            # 理论上最多一条（时间区间不重叠），取版本号最大的那条
            return sorted(rows, key=lambda r: r.get("version", 0))[-1]

        # 历史版本中没有，说明时间点在当前版本范围内（或实体不存在）
        return self.find_entity(entity_id)

    def close(self):
        """关闭数据库连接"""
        try:
            self.db.close()
        except Exception:
            pass
