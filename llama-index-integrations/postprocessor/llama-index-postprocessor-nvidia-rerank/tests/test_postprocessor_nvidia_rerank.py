import os
from typing import List
import pytest
from llama_index.postprocessor.nvidia_rerank import NVIDIARerank
from llama_index.core.schema import NodeWithScore, Document
from llama_index.core.node_parser import SentenceSplitter

import faker


@pytest.fixture()
def text() -> str:
    fake = faker.Faker()
    fake.seed_instance(os.environ.get("FAKER_SEED", 13131))
    return fake.paragraph(2016)


@pytest.fixture()
def query() -> str:
    return "what use is testing?"


@pytest.fixture()
def documents(text: str) -> List[Document]:
    # TODO: remove workaround ([:456]) for server-side truncation bug
    return [Document(text=text[:456]) for text in SentenceSplitter().split_text(text)]


@pytest.fixture()
def nodes(documents: List[Document]) -> List[NodeWithScore]:
    return [NodeWithScore(node=document) for document in documents]


@pytest.mark.integration()
def test_basic(model: str, mode: dict) -> None:
    text = "Testing leads to failure, and failure leads to understanding."
    result = (
        NVIDIARerank(model=model)
        .mode(**mode)
        .postprocess_nodes(
            [NodeWithScore(node=Document(text=text))],
            query_str=text,
        )
    )
    assert result
    assert isinstance(result, list)
    assert len(result) == 1
    assert all(isinstance(node, NodeWithScore) for node in result)
    assert all(isinstance(node.node, Document) for node in result)
    assert all(isinstance(node.score, float) for node in result)
    assert all(node.node.text == text for node in result)


@pytest.mark.integration()
def test_accuracy(model: str, mode: dict) -> None:
    texts = ["first", "last"]
    query = "last"
    result = (
        NVIDIARerank(model=model)
        .mode(**mode)
        .postprocess_nodes(
            [NodeWithScore(node=Document(text=text)) for text in texts],
            query_str=query,
        )
    )
    assert result
    assert isinstance(result, list)
    assert len(result) == 2
    assert all(isinstance(node, NodeWithScore) for node in result)
    assert all(isinstance(node.node, Document) for node in result)
    assert all(isinstance(node.score, float) for node in result)
    assert result[0].node.text == "last"


@pytest.mark.integration()
def test_direct_empty_docs(query: str, model: str, mode: dict) -> None:
    ranker = NVIDIARerank(model=model).mode(**mode)
    result_docs = ranker.postprocess_nodes(nodes=[], query_str=query)
    assert len(result_docs) == 0


@pytest.mark.integration()
def test_direct_top_n_negative(
    query: str, nodes: List[NodeWithScore], model: str, mode: dict
) -> None:
    orig = NVIDIARerank.Config.validate_assignment
    NVIDIARerank.Config.validate_assignment = False
    ranker = NVIDIARerank(model=model).mode(**mode)
    ranker.top_n = -100
    NVIDIARerank.Config.validate_assignment = orig
    result = ranker.postprocess_nodes(nodes=nodes, query_str=query)
    assert len(result) == 0


@pytest.mark.integration()
def test_direct_top_n_zero(
    query: str, nodes: List[NodeWithScore], model: str, mode: dict
) -> None:
    ranker = NVIDIARerank(model=model).mode(**mode)
    ranker.top_n = 0
    result = ranker.postprocess_nodes(nodes=nodes, query_str=query)
    assert len(result) == 0


@pytest.mark.integration()
def test_direct_top_n_one(
    query: str, nodes: List[NodeWithScore], model: str, mode: dict
) -> None:
    ranker = NVIDIARerank(model=model).mode(**mode)
    ranker.top_n = 1
    result = ranker.postprocess_nodes(nodes=nodes, query_str=query)
    assert len(result) == 1


@pytest.mark.integration()
def test_direct_top_n_equal_len_docs(
    query: str, nodes: List[NodeWithScore], model: str, mode: dict
) -> None:
    ranker = NVIDIARerank(model=model).mode(**mode)
    ranker.top_n = len(nodes)
    result = ranker.postprocess_nodes(nodes=nodes, query_str=query)
    assert len(result) == len(nodes)


@pytest.mark.integration()
def test_direct_top_n_greater_len_docs(
    query: str, nodes: List[NodeWithScore], model: str, mode: dict
) -> None:
    ranker = NVIDIARerank(model=model).mode(**mode)
    ranker.top_n = len(nodes) * 2
    result = ranker.postprocess_nodes(nodes=nodes, query_str=query)
    assert len(result) == len(nodes)


@pytest.mark.parametrize("batch_size", [-10, 0])
def test_invalid_max_batch_size(model: str, mode: dict, batch_size: int) -> None:
    ranker = NVIDIARerank(model=model).mode(**mode)
    with pytest.raises(ValueError):
        ranker.max_batch_size = batch_size


def test_invalid_top_n(model: str, mode: dict) -> None:
    ranker = NVIDIARerank(model=model).mode(**mode)
    with pytest.raises(ValueError):
        ranker.top_n = -10


@pytest.mark.integration()
@pytest.mark.parametrize(
    ("batch_size", "top_n"),
    (
        (7, 7),  # batch_size == top_n
        (17, 7),  # batch_size > top_n
        (3, 13),  # batch_size < top_n
        (1, 1),  # batch_size == top_n, corner case 1
        (1, 10),  # batch_size < top_n, corner case 1
        (10, 1),  # batch_size > top_n, corner case 1
    ),
)
def test_rerank_batching(
    query: str,
    nodes: List[NodeWithScore],
    model: str,
    mode: dict,
    batch_size: int,
    top_n: int,
) -> None:
    assert len(nodes) > batch_size, "test requires more nodes"

    ranker = NVIDIARerank(model=model).mode(**mode)
    ranker.top_n = top_n
    ranker.max_batch_size = batch_size
    result = ranker.postprocess_nodes(nodes=nodes, query_str=query)
    assert len(result) == min(len(nodes), top_n)
    for node in result:
        assert node.score is not None
        assert isinstance(node.score, float)
    assert all(
        result[i].score >= result[i + 1].score for i in range(len(result) - 1)
    ), "results are not sorted"
