"""Asset dependency graph — Draft → Typography → Carousel → Export."""

from __future__ import annotations

from app.modules.carousel.domain.models import (
    AssetDependencyGraph,
    DependencyEdge,
    DependencyNode,
    ExportArtifact,
    new_id,
)


class DefaultAssetDependencyGraphBuilder:
    def build(
        self,
        *,
        draft_id: str,
        typography_asset_ids: tuple[str, ...] = (),
        carousel_asset_id: str,
        export_artifacts: tuple[ExportArtifact, ...] = (),
    ) -> AssetDependencyGraph:
        nodes: list[DependencyNode] = []
        edges: list[DependencyEdge] = []

        draft_node = f"draft:{draft_id}"
        nodes.append(DependencyNode(node_id=draft_node, kind="draft", ref=draft_id))

        typo_nodes: list[str] = []
        for tid in typography_asset_ids:
            nid = f"typography:{tid}"
            typo_nodes.append(nid)
            nodes.append(DependencyNode(node_id=nid, kind="typography", ref=tid))
            edges.append(DependencyEdge(parent_id=draft_node, child_id=nid, relation="produces"))

        carousel_node = f"carousel:{carousel_asset_id}"
        nodes.append(
            DependencyNode(node_id=carousel_node, kind="carousel", ref=carousel_asset_id)
        )
        parents = typo_nodes or [draft_node]
        for parent in parents:
            edges.append(
                DependencyEdge(parent_id=parent, child_id=carousel_node, relation="produces")
            )
        if not typo_nodes:
            # still record draft → carousel
            pass

        for exp in export_artifacts:
            eid = f"export:{exp.artifact_id}"
            nodes.append(
                DependencyNode(
                    node_id=eid,
                    kind="export",
                    ref=exp.artifact_id,
                    metadata={"format": exp.format, "object_key": exp.object_key},
                )
            )
            edges.append(
                DependencyEdge(parent_id=carousel_node, child_id=eid, relation="produces")
            )

        return AssetDependencyGraph(
            graph_id=new_id(),
            nodes=tuple(nodes),
            edges=tuple(edges),
            metadata={
                "chain": ["draft", "typography", "carousel", "export"],
                "supports_replay": True,
                "supports_regeneration": True,
            },
        )
