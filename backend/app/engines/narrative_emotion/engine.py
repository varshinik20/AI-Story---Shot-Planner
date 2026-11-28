"""NetworkX-powered Narrative & Emotion Graph modeling + structural diagnostics."""

from __future__ import annotations

import uuid
from typing import Any

import networkx as nx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.conversation import Conversation
from app.db.models.domain import (
    Character,
    Location,
    NarrativeEvent,
    NarrativeGraph,
)


class NarrativeEmotionEngine:
    """Builds a NetworkX DiGraph across events, characters, locations, and emotional transitions."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def build_and_analyze(
        self,
        *,
        project_id: uuid.UUID,
        characters: list[Character],
        locations: list[Location],
        events: list[NarrativeEvent],
        story_structure: dict[str, Any],
    ) -> NarrativeGraph:
        ordered_events = sorted(events, key=lambda e: e.timeline_position)
        graph = nx.DiGraph()

        nodes_payload: list[dict[str, Any]] = []
        edges_payload: list[dict[str, Any]] = []

        # 1. Add Character & Location reference nodes
        char_by_name: dict[str, str] = {}
        for ch in characters:
            node_id = ch.character_code
            char_by_name[ch.name.lower()] = node_id
            attrs = {"node_type": "character", "label": ch.name, "role": ch.role}
            graph.add_node(node_id, **attrs)
            nodes_payload.append({"id": node_id, **attrs})

        loc_by_name: dict[str, str] = {}
        for loc in locations:
            node_id = loc.location_code
            loc_by_name[loc.name.lower()] = node_id
            attrs = {"node_type": "location", "label": loc.name, "time_of_day": loc.time_of_day}
            graph.add_node(node_id, **attrs)
            nodes_payload.append({"id": node_id, **attrs})

        # 2. Add NarrativeEvent nodes & emotional nodes
        for ev in ordered_events:
            ev_attrs = {
                "node_type": "event",
                "label": ev.event_id,
                "description": ev.description,
                "timeline_position": ev.timeline_position,
                "narrative_role": ev.narrative_role,
                "narrative_importance": ev.narrative_importance,
                "emotion": ev.emotion,
                "intensity": ev.intensity,
                "location": ev.location,
            }
            graph.add_node(ev.event_id, **ev_attrs)
            nodes_payload.append({"id": ev.event_id, **ev_attrs})

            # Connect characters present in this event
            for ch_name in ev.characters or []:
                ch_node = char_by_name.get(ch_name.lower())
                if ch_node:
                    graph.add_edge(ch_node, ev.event_id, edge_type="character_presence")
                    edges_payload.append(
                        {"source": ch_node, "target": ev.event_id, "edge_type": "character_presence"}
                    )

            # Connect location
            if ev.location:
                loc_node = loc_by_name.get(ev.location.lower())
                if loc_node:
                    graph.add_edge(loc_node, ev.event_id, edge_type="location_setting")
                    edges_payload.append(
                        {"source": loc_node, "target": ev.event_id, "edge_type": "location_setting"}
                    )

        # 3. Connect temporal, causal, and emotional transition edges across events
        abrupt_transitions: list[dict[str, Any]] = []
        weak_causal_links: list[dict[str, Any]] = []
        emotional_arc: list[dict[str, Any]] = []

        for idx, ev in enumerate(ordered_events):
            emotional_arc.append(
                {
                    "event_id": ev.event_id,
                    "position": ev.timeline_position,
                    "emotion": ev.emotion,
                    "intensity": ev.intensity,
                    "narrative_role": ev.narrative_role,
                }
            )
            if idx == 0:
                continue

            prev = ordered_events[idx - 1]
            delta = round(ev.intensity - prev.intensity, 3)

            graph.add_edge(prev.event_id, ev.event_id, edge_type="temporal", weight=1.0)
            edges_payload.append(
                {"source": prev.event_id, "target": ev.event_id, "edge_type": "temporal", "weight": 1.0}
            )

            # Causal link check
            if ev.cause or prev.consequence:
                graph.add_edge(prev.event_id, ev.event_id, edge_type="causal", detail=ev.cause or prev.consequence)
                edges_payload.append(
                    {
                        "source": prev.event_id,
                        "target": ev.event_id,
                        "edge_type": "causal",
                        "detail": ev.cause or prev.consequence,
                    }
                )
            else:
                weak_causal_links.append(
                    {
                        "from_event": prev.event_id,
                        "to_event": ev.event_id,
                        "reason": "Missing explicit causal bridge between sequential events.",
                    }
                )

            # Emotional transition edge
            graph.add_edge(
                prev.event_id,
                ev.event_id,
                edge_type="emotional_transition",
                from_emotion=prev.emotion,
                to_emotion=ev.emotion,
                intensity_delta=delta,
            )
            edges_payload.append(
                {
                    "source": prev.event_id,
                    "target": ev.event_id,
                    "edge_type": "emotional_transition",
                    "from_emotion": prev.emotion,
                    "to_emotion": ev.emotion,
                    "intensity_delta": delta,
                }
            )

            if abs(delta) >= 0.45 and prev.emotion.lower() != ev.emotion.lower():
                abrupt_transitions.append(
                    {
                        "from_event": prev.event_id,
                        "to_event": ev.event_id,
                        "from_emotion": prev.emotion,
                        "to_emotion": ev.emotion,
                        "intensity_delta": delta,
                        "recommendation": (
                            f"Insert an establishing/reaction beat easing {prev.emotion} ({prev.intensity:.2f}) "
                            f"into {ev.emotion} ({ev.intensity:.2f})."
                        ),
                    }
                )

        # 4. NetworkX structural diagnostics
        undirected = graph.to_undirected()
        components = [sorted(list(c)) for c in nx.connected_components(undirected)] if graph.number_of_nodes() else []
        isolated_nodes = [n for n, deg in undirected.degree() if deg == 0]

        event_subgraph = graph.subgraph([e.event_id for e in ordered_events])
        event_centrality = nx.degree_centrality(event_subgraph) if len(ordered_events) > 1 else {}

        # 5. Scene sequencing recommendation driven by graph diagnostics
        scene_clusters: list[dict[str, Any]] = []
        current_cluster: list[NarrativeEvent] = []
        for ev in ordered_events:
            if not current_cluster:
                current_cluster.append(ev)
                continue
            prev_ev = current_cluster[-1]
            location_changed = (ev.location or "").strip().lower() != (prev_ev.location or "").strip().lower()
            climax_boundary = ev.narrative_role in ("climax", "resolution") and prev_ev.narrative_role != ev.narrative_role
            if location_changed or climax_boundary or len(current_cluster) >= 3:
                scene_clusters.append(self._format_cluster(len(scene_clusters) + 1, current_cluster, abrupt_transitions))
                current_cluster = [ev]
            else:
                current_cluster.append(ev)
        if current_cluster:
            scene_clusters.append(self._format_cluster(len(scene_clusters) + 1, current_cluster, abrupt_transitions))

        diagnostics = {
            "node_count": graph.number_of_nodes(),
            "edge_count": graph.number_of_edges(),
            "event_count": len(ordered_events),
            "connected_components_count": len(components),
            "connected_components": components,
            "isolated_nodes": isolated_nodes,
            "weak_causal_links": weak_causal_links,
            "abrupt_emotional_transitions": abrupt_transitions,
            "emotional_arc": emotional_arc,
            "event_centrality": event_centrality,
            "recommended_scene_clusters": scene_clusters,
            "narrative_health": (
                "strong"
                if len(isolated_nodes) == 0 and len(weak_causal_links) == 0
                else "needs_transitional_attention"
            ),
        }

        existing = (
            await self.session.execute(select(NarrativeGraph).where(NarrativeGraph.project_id == project_id))
        ).scalar_one_or_none()
        if existing is None:
            existing = NarrativeGraph(
                project_id=project_id,
                nodes=nodes_payload,
                edges=edges_payload,
                diagnostics=diagnostics,
                story_structure=story_structure,
            )
            self.session.add(existing)
        else:
            existing.nodes = nodes_payload
            existing.edges = edges_payload
            existing.diagnostics = diagnostics
            existing.story_structure = story_structure

        convs = (
            await self.session.execute(select(Conversation).where(Conversation.project_id == project_id))
        ).scalars().all()
        for conv in convs:
            conv.workflow_stage = "scenes_ready"

        await self.session.commit()
        return existing

    def _format_cluster(
        self,
        index: int,
        events: list[NarrativeEvent],
        abrupt_transitions: list[dict[str, Any]],
    ) -> dict[str, Any]:
        ev_ids = [e.event_id for e in events]
        needs_bridge = any(
            t["to_event"] in ev_ids or t["from_event"] in ev_ids for t in abrupt_transitions
        )
        return {
            "suggested_scene_order": index,
            "location": events[0].location or "Primary Location",
            "event_ids": ev_ids,
            "dominant_emotion": max(events, key=lambda e: e.intensity).emotion,
            "peak_intensity": max(e.intensity for e in events),
            "needs_pacing_bridge": needs_bridge,
        }
