"""
Local Graph Engine for MiroFish
Enables offline / local GraphRAG knowledge graph extraction and querying
using the configured LLM (e.g. Google Gemini) without requiring an external Zep Cloud account.
"""

import os
import json
import uuid
import logging
from typing import Dict, Any, List, Optional
from ..config import Config

logger = logging.getLogger('mirofish.local_graph')

GRAPHS_DIR = os.path.join(os.path.dirname(__file__), '../../uploads/graphs')


def is_local_zep_mode(api_key: Optional[str] = None) -> bool:
    """Return True if local graph engine should be used instead of Zep Cloud."""
    key = api_key or Config.ZEP_API_KEY or ""
    return not key or key == "your_zep_api_key_here" or key.lower() in ("local", "mock", "none")


def get_graph_file_path(graph_id: str) -> str:
    os.makedirs(GRAPHS_DIR, exist_ok=True)
    return os.path.join(GRAPHS_DIR, f"{graph_id}.json")


def local_graph_exists(graph_id: str) -> bool:
    return os.path.exists(get_graph_file_path(graph_id))


def load_local_graph(graph_id: str) -> Optional[Dict[str, Any]]:
    path = get_graph_file_path(graph_id)
    if os.path.exists(path):
        try:
            with open(path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Failed to load local graph {graph_id}: {e}")
    return None


def save_local_graph(graph_id: str, data: Dict[str, Any]) -> None:
    path = get_graph_file_path(graph_id)
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def build_local_graph_with_llm(
    text: str,
    ontology: Dict[str, Any],
    graph_name: str,
    graph_id: Optional[str] = None,
    progress_callback: Optional[Any] = None
) -> Dict[str, Any]:
    """
    Extract entity nodes and relationship edges from text using LLM Client.
    """
    from .llm_client import LLMClient
    from .locale import get_language_instruction
    
    client = LLMClient()
    graph_id = graph_id or f"mirofish_{uuid.uuid4().hex[:16]}"
    
    if progress_callback:
        progress_callback("Extracting entities with LLM...", 30)

    entity_types = [e.get('name') for e in ontology.get('entity_types', [])]
    edge_types = [e.get('name') for e in ontology.get('edge_types', [])]
    
    lang_inst = get_language_instruction()

    prompt = f"""You are a Knowledge Graph Extraction Engine.
Analyze the following document and extract a high-fidelity Knowledge Graph based on the provided ontology.

Available Entity Types:
{json.dumps(entity_types, ensure_ascii=False, indent=2)}

Available Relation Types:
{json.dumps(edge_types, ensure_ascii=False, indent=2)}

Document Text:
{text[:9000]}

Instructions:
1. Extract between 8 and 12 key entities directly relevant to the document topics.
2. For each entity, specify a realistic name, select its entity type from Available Entity Types, and provide a 1-sentence concise summary.
3. Extract 6-12 relationship edges between these entities using the Available Relation Types.
4. Keep all descriptions concise.
5. {lang_inst}

Respond ONLY with a valid JSON object matching this schema:
{{
  "nodes": [
    {{
      "name": "Entity Name (e.g. Solo Developer Max, TechReviewer Sarah, Security Auditor)",
      "type": "Must be one of the Available Entity Types",
      "summary": "1-2 sentence description of their role, perspective, and background",
      "attributes": {{"focus": "GUI Tools", "platform": "macOS"}}
    }}
  ],
  "edges": [
    {{
      "source_name": "Exact Name of Source Entity",
      "target_name": "Exact Name of Target Entity",
      "relation": "Must be one of the Available Relation Types",
      "fact": "Clear factual statement describing their relationship or interaction"
    }}
  ]
}}
"""
    result = client.chat_json(messages=[{"role": "user", "content": prompt}], max_tokens=8192, max_attempts=2)
    
    if progress_callback:
        progress_callback("Processing extracted graph...", 75)
        
    raw_nodes = result.get('nodes', [])
    raw_edges = result.get('edges', [])
    
    nodes = []
    name_to_uuid = {}
    
    for item in raw_nodes:
        node_uuid = str(uuid.uuid4())
        name = item.get('name', 'Unknown')
        name_to_uuid[name] = node_uuid
        ent_type = item.get('type', 'Entity')
        labels = [ent_type, "Entity"]
        nodes.append({
            "uuid": node_uuid,
            "name": name,
            "labels": labels,
            "summary": item.get('summary', ''),
            "attributes": item.get('attributes', {})
        })
        
    edges = []
    for item in raw_edges:
        src_name = item.get('source_name')
        tgt_name = item.get('target_name')
        src_uuid = name_to_uuid.get(src_name)
        tgt_uuid = name_to_uuid.get(tgt_name)
        
        # Fuzzy match if exact match fails
        if not src_uuid and src_name:
            for k, u in name_to_uuid.items():
                if k.lower() in src_name.lower() or src_name.lower() in k.lower():
                    src_uuid = u
                    break
        if not tgt_uuid and tgt_name:
            for k, u in name_to_uuid.items():
                if k.lower() in tgt_name.lower() or tgt_name.lower() in k.lower():
                    tgt_uuid = u
                    break
                    
        if src_uuid and tgt_uuid and src_uuid != tgt_uuid:
            edges.append({
                "uuid": str(uuid.uuid4()),
                "name": item.get('relation', 'RELATES_TO'),
                "fact": item.get('fact', ''),
                "source_node_uuid": src_uuid,
                "target_node_uuid": tgt_uuid,
                "attributes": {}
            })
            
    found_types = list(set([n['labels'][0] for n in nodes if n.get('labels')]))
    
    graph_data = {
        "graph_id": graph_id,
        "name": graph_name,
        "nodes": nodes,
        "edges": edges,
        "entity_types": found_types,
        "total_nodes": len(nodes),
        "total_edges": len(edges)
    }
    
    save_local_graph(graph_id, graph_data)
    
    if progress_callback:
        progress_callback("Knowledge graph ready!", 95)
        
    return graph_data
