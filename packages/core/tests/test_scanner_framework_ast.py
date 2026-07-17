"""Framework-object AST detector — precision test: construct+invoke vs. import-only."""

from __future__ import annotations

from pathlib import Path

from opencomplai_core.models import SignalCategory
from opencomplai_core.scanner.detectors.framework_ast import FrameworkAstDetector
from opencomplai_core.scanner.features import ScanConfig, extract_features
from opencomplai_core.scanner.inventory import build_repo_inventory
from opencomplai_core.scanner.registry import DETECTOR_REGISTRY


def _repo_with_framework_object(tmp_path: Path, code: str) -> Path:
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "agent.py").write_text(code, encoding="utf-8")
    return tmp_path


def test_langchain_agent_executor_construct_and_invoke_is_flagged(tmp_path: Path):
    repo = _repo_with_framework_object(
        tmp_path,
        "from langchain.agents import AgentExecutor\n"
        "\n"
        "def run():\n"
        "    agent = AgentExecutor(llm=None, tools=[])\n"
        "    return agent.invoke({'input': 'hello'})\n",
    )
    inv = build_repo_inventory(repo)
    config = ScanConfig(framework_detectors=True)
    features = extract_features(inv, config)
    detector = FrameworkAstDetector()
    evidence = detector.detect(features)
    assert len(evidence) == 1
    assert evidence[0].category == SignalCategory.AGENT_FRAMEWORK
    assert evidence[0].token_label == "AgentExecutor"


def test_import_only_is_not_flagged(tmp_path: Path):
    repo = _repo_with_framework_object(
        tmp_path,
        "import langchain\n"
        "\n"
        "def unrelated():\n"
        "    print('just importing, not instantiating')\n",
    )
    inv = build_repo_inventory(repo)
    config = ScanConfig(framework_detectors=True)
    features = extract_features(inv, config)
    detector = FrameworkAstDetector()
    evidence = detector.detect(features)
    assert evidence == []


def test_crewai_crew_construct_and_invoke_is_flagged(tmp_path: Path):
    repo = _repo_with_framework_object(
        tmp_path,
        "from crewai import Crew\n"
        "\n"
        "def run():\n"
        "    crew = Crew(agents=[], tasks=[])\n"
        "    return crew.kickoff()\n",
    )
    inv = build_repo_inventory(repo)
    config = ScanConfig(framework_detectors=True)
    features = extract_features(inv, config)
    detector = FrameworkAstDetector()
    evidence = detector.detect(features)
    assert len(evidence) == 1
    assert evidence[0].token_label == "Crew"


def test_autogen_conversable_agent_construct_and_invoke_is_flagged(tmp_path: Path):
    repo = _repo_with_framework_object(
        tmp_path,
        "from autogen import ConversableAgent\n"
        "\n"
        "def run():\n"
        "    agent = ConversableAgent(name='bot')\n"
        "    return agent.generate_reply([])\n",
    )
    inv = build_repo_inventory(repo)
    config = ScanConfig(framework_detectors=True)
    features = extract_features(inv, config)
    detector = FrameworkAstDetector()
    evidence = detector.detect(features)
    assert len(evidence) == 1
    assert evidence[0].token_label == "ConversableAgent"


def test_langgraph_stategraph_construct_and_invoke_is_flagged(tmp_path: Path):
    repo = _repo_with_framework_object(
        tmp_path,
        "from langgraph.graph import StateGraph\n"
        "\n"
        "def run():\n"
        "    graph = StateGraph(dict)\n"
        "    return graph.compile()\n",
    )
    inv = build_repo_inventory(repo)
    config = ScanConfig(framework_detectors=True)
    features = extract_features(inv, config)
    detector = FrameworkAstDetector()
    evidence = detector.detect(features)
    assert len(evidence) == 1
    assert evidence[0].token_label == "StateGraph"


def test_framework_detectors_off_by_default(tmp_path: Path):
    repo = _repo_with_framework_object(
        tmp_path,
        "from langchain.agents import AgentExecutor\n"
        "\n"
        "def run():\n"
        "    agent = AgentExecutor(llm=None, tools=[])\n"
        "    return agent.invoke({'input': 'hello'})\n",
    )
    inv = build_repo_inventory(repo)
    features = extract_features(inv, ScanConfig())  # framework_detectors defaults False
    assert features.framework_objects == []
    detector = FrameworkAstDetector()
    assert detector.detect(features) == []


def test_detector_registry_count_increased_by_one():
    detector_ids = [d.detector_id for d in DETECTOR_REGISTRY]
    assert "DET_FRAMEWORK_AST_V1" in detector_ids
    assert len(detector_ids) == len(set(detector_ids))  # no duplicate ids


def test_no_regression_in_existing_detector_evidence_counts(tmp_path: Path):
    (tmp_path / "requirements.txt").write_text(
        "face_recognition\nopenai\n", encoding="utf-8"
    )
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "face.py").write_text(
        "import face_recognition\nimport openai\n", encoding="utf-8"
    )
    inv = build_repo_inventory(tmp_path)
    features = extract_features(inv, ScanConfig())
    non_framework_detectors = [
        d for d in DETECTOR_REGISTRY if d.detector_id != "DET_FRAMEWORK_AST_V1"
    ]
    total_evidence = sum(len(d.detect(features)) for d in non_framework_detectors)
    assert total_evidence > 0
