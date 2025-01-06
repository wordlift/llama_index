import pytest

from llama_index.graph_stores.wordlift import WordLiftGraphStore


@pytest.fixture()
def wordlift_graph_store(wiremock_url: str) -> WordLiftGraphStore:
    return WordLiftGraphStore(
        key="key609433189806627",
        api_url=wiremock_url,
    )


def test_wordlift_graph_store(wordlift_graph_store: WordLiftGraphStore):
    triples = wordlift_graph_store.get(
        "https://data.wordlift.io/wl78195/things/hello-world"
    )
    assert [
        [
            "http://schema.org/mentions",
            "https://data.wordlift.io/wl78195/things/entity-2",
        ]
    ] == triples
