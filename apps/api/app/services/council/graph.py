"""LangGraph council graph: nodes, edges, orchestration.

Flow (committee meeting order):
    START → technical → news → quant → risk → execution → tally → END

Each agent node calls `agent.deliberate(state, llm)`, appends its message (and vote),
and stashes risk/sentiment/veto into declared state channels. The terminal `tally`
node aggregates votes, applies any veto, and computes the Council Confidence Score.
"""

from __future__ import annotations

import uuid

from langgraph.graph import END, START, StateGraph

from app.domain.enums import AgentId
from app.domain.models import MarketSnapshot, Vote, VetoInfo
from app.services.council.agents.base import Agent
from app.services.council.agents.execution import ExecutionAgent
from app.services.council.agents.news import NewsAnalyst
from app.services.council.agents.quant import QuantAnalyst
from app.services.council.agents.risk import RiskManager
from app.services.council.agents.technical import TechnicalAnalyst
from app.services.council.state import CouncilState, initial_state
from app.services.council.voting import tally
from app.services.llm.client import LLMClient
from app.utils.logging import get_logger

log = get_logger("council.graph")

# The fixed committee speaking order.
COMMITTEE_ORDER: list[AgentId] = [
    AgentId.TECHNICAL,
    AgentId.NEWS,
    AgentId.QUANT,
    AgentId.RISK,
    AgentId.EXECUTION,
]
_ORDER = COMMITTEE_ORDER  # internal alias


def default_agents() -> dict[AgentId, Agent]:
    return {
        AgentId.TECHNICAL: TechnicalAnalyst(),
        AgentId.NEWS: NewsAnalyst(),
        AgentId.QUANT: QuantAnalyst(),
        AgentId.RISK: RiskManager(),
        AgentId.EXECUTION: ExecutionAgent(),
    }


def _make_agent_node(agent: Agent, llm: LLMClient):
    async def node(state: CouncilState) -> dict:
        out = await agent.deliberate(state, llm)
        msg = agent.to_message(out)
        update: dict = {"messages": [msg]}

        if agent.casts_vote and out.vote is not None:
            update["votes"] = [
                Vote(agent_id=agent.id, side=out.vote, rationale=out.text[:200])
            ]
        if out.risk_score is not None:
            update["risk_score"] = out.risk_score
        if out.sentiment is not None:
            update["sentiment"] = out.sentiment
        if out.veto:
            update["veto"] = VetoInfo(
                by_agent=agent.id,
                reason=out.veto_reason or out.text,
                risk_score=out.risk_score or 0.0,
                factors=out.veto_factors,
            )
        return update

    node.__name__ = f"{agent.id.value}_node"
    return node


def build_council_graph(agents: dict[AgentId, Agent], llm: LLMClient):
    """Compile the council StateGraph. Returns a runnable graph."""
    graph = StateGraph(CouncilState)

    for agent_id in _ORDER:
        graph.add_node(agent_id.value, _make_agent_node(agents[agent_id], llm))

    async def tally_node(state: CouncilState) -> dict:
        return tally(state)

    graph.add_node("tally", tally_node)

    # Linear committee flow.
    graph.add_edge(START, _ORDER[0].value)
    for prev, nxt in zip(_ORDER, _ORDER[1:]):
        graph.add_edge(prev.value, nxt.value)
    graph.add_edge(_ORDER[-1].value, "tally")
    graph.add_edge("tally", END)

    return graph.compile()


class Council:
    """Convenience wrapper: builds the graph once and runs rounds against snapshots."""

    def __init__(self, llm: LLMClient, agents: dict[AgentId, Agent] | None = None) -> None:
        self.agents = agents or default_agents()
        self.llm = llm
        self.graph = build_council_graph(self.agents, llm)

    async def run_round(
        self, snapshot: MarketSnapshot, session_id: str | None = None
    ) -> CouncilState:
        sid = session_id or f"sess-{uuid.uuid4().hex[:10]}"
        state = initial_state(sid, snapshot)
        log.info("council round %s on %s (offline=%s)", sid, snapshot.symbol, self.llm.is_offline)
        result: CouncilState = await self.graph.ainvoke(state)
        return result
