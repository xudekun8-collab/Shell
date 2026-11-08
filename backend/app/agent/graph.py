"""四节点状态图：perceive → retrieve → plan → act。"""
from langgraph.graph import END, START, StateGraph

from app.agent.nodes.act import make_act
from app.agent.nodes.perceive import make_perceive
from app.agent.nodes.plan import make_plan
from app.agent.nodes.retrieve import make_retrieve
from app.agent.state import State


def _route_after_retrieve(state: dict) -> str:
    return "act" if state.get("intent") == "end" else "plan"


def build_graph(llm_client, session_factory):
    graph = StateGraph(State)
    graph.add_node("perceive", make_perceive(session_factory))
    graph.add_node("retrieve", make_retrieve(session_factory))
    graph.add_node("plan", make_plan(llm_client))
    graph.add_node("act", make_act(session_factory))
    graph.add_edge(START, "perceive")
    graph.add_edge("perceive", "retrieve")
    graph.add_conditional_edges(
        "retrieve",
        _route_after_retrieve,
        {"plan": "plan", "act": "act"},
    )
    graph.add_edge("plan", "act")
    graph.add_edge("act", END)
    return graph.compile()
