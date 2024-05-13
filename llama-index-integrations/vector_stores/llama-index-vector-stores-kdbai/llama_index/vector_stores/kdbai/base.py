"""KDB.AI vector store index.

An index that is built within KDB.AI.

"""

import logging
from typing import Any, List, Callable, Optional

import pandas as pd

from llama_index.core.bridge.pydantic import PrivateAttr
from llama_index.core.schema import BaseNode, TextNode
from llama_index.core.vector_stores.types import (
    BasePydanticVectorStore,
    VectorStoreQuery,
    VectorStoreQueryResult,
)
from llama_index.vector_stores.kdbai.utils import default_sparse_encoder

DEFAULT_COLUMN_NAMES = ["document_id", "text", "embedding"]

DEFAULT_BATCH_SIZE = 100


# INITIALISE LOGGER AND SET FORMAT
logger = logging.getLogger(__name__)


# MATCH THE METADATA COLUMN DATA TYPE TO ITS PYTYPE
def convert_metadata_col(column, value):
    try:
        if column["pytype"] == "str":
            return str(value)
        elif column["pytype"] == "bytes":
            return value.encode("utf-8")
        elif column["pytype"] == "datetime64[ns]":
            return pd.to_datetime(value)
        elif column["pytype"] == "timedelta64[ns]":
            return pd.to_timedelta(value)
        return value.astype(column["pytype"])
    except Exception as e:
        logger.error(
            f"Failed to convert column {column['name']} to type {column['pytype']}: {e}"
        )


class KDBAIVectorStore(BasePydanticVectorStore):
    """The KDBAI Vector Store.

    In this vector store we store the text, its embedding and
    its metadata in a KDBAI vector store table. This implementation
    allows the use of an already existing table.

    Args:
        table kdbai.Table: The KDB.AI table to use as storage.
        batch (int, optional): batch size to insert data.
            Default is 100.

    Returns:
        KDBAIVectorStore: Vectorstore that supports add and query.
    """

    stores_text: bool = True
    flat_metadata: bool = True

    hybrid_search: bool = False
    batch_size: int

    _table: Any = PrivateAttr()
    _sparse_encoder: Optional[Callable] = PrivateAttr()

    def __init__(
        self,
        table: Any = None,
        hybrid_search: bool = False,
        sparse_encoder: Optional[Callable] = None,
        batch_size: int = DEFAULT_BATCH_SIZE,
        **kwargs: Any,
    ) -> None:
        """Initialize params."""
        try:
            import kdbai_client as kdbai

            logger.info("KDBAI client version: " + kdbai.__version__)

        except ImportError:
            raise ValueError(
                "Could not import kdbai_client package."
                "Please add it to the dependencies."
            )

        if table is None:
            raise ValueError("Must provide an existing KDB.AI table.")
        else:
            self._table = table

        if hybrid_search:
            if sparse_encoder is None:
                self._sparse_encoder = default_sparse_encoder
            else:
                self._sparse_encoder = sparse_encoder

        super().__init__(batch_size=batch_size, hybrid_search=hybrid_search)

    @property
    def client(self) -> Any:
        """Return KDB.AI client."""
        return self._table

    @classmethod
    def class_name(cls) -> str:
        return "KDBAIVectorStore"

    def add(
        self,
        nodes: List[BaseNode],
        **add_kwargs: Any,
    ) -> List[str]:
        """Add nodes to the KDBAI Vector Store.

        Args:
            nodes (List[BaseNode]): List of nodes to be added.

        Returns:
            List[str]: List of document IDs that were added.
        """
        df = pd.DataFrame()
        docs = []
        schema = self._table.schema()["columns"]
        if self.hybrid_search:
            schema = [item for item in schema if item["name"] != "sparseVectors"]

        try:
            for node in nodes:
                doc = {
                    "document_id": node.node_id.encode("utf-8"),
                    "text": node.text.encode("utf-8"),
                    "embedding": node.embedding,
                }

                if self.hybrid_search:
                    doc["sparseVectors"] = self._sparse_encoder([node.get_content()])

                # handle extra columns
                if len(schema) > len(DEFAULT_COLUMN_NAMES):
                    for column in schema[len(DEFAULT_COLUMN_NAMES) :]:
                        try:
                            doc[column["name"]] = convert_metadata_col(
                                column, node.metadata[column["name"]]
                            )
                        except Exception as e:
                            logger.error(
                                f"Error writing column {column['name']} as type {column['pytype']}: {e}."
                            )

                docs.append(doc)

            df = pd.DataFrame(docs)
            for i in range((len(df) - 1) // self.batch_size + 1):
                batch = df.iloc[i * self.batch_size : (i + 1) * self.batch_size]
                try:
                    self._table.insert(batch, warn=False)
                    logger.info(f"inserted batch {i}")
                except Exception as e:
                    logger.exception(
                        f"Failed to insert batch {i} of documents into the datastore: {e}"
                    )

            return df["document_id"].tolist()

        except Exception as e:
            logger.error(f"Error preparing data for KDB.AI: {e}.")

    def query(self, query: VectorStoreQuery, **kwargs: Any) -> VectorStoreQueryResult:
        if query.filters is None:
            filter = []
        else:
            filter = query.filters

        if self.hybrid_search:
            alpha = query.alpha if query.alpha is not None else 0.5
            sparse_vectors = self._sparse_encoder([query.query_str])
            results = self._table.hybrid_search(
                dense_vectors=[query.query_embedding],
                sparse_vectors=sparse_vectors,
                n=query.similarity_top_k,
                filter=filter,
                alpha=alpha,
            )[0]
        else:
            results = self._table.search(
                vectors=[query.query_embedding], n=query.similarity_top_k, filter=filter
            )[0]

        top_k_nodes = []
        top_k_ids = []
        top_k_scores = []

        for result in results.to_dict(orient="records"):
            metadata = {x: result[x] for x in result if x not in DEFAULT_COLUMN_NAMES}
            node = TextNode(
                text=result["text"], id_=result["document_id"], metadata=metadata
            )
            top_k_ids.append(result["document_id"])
            top_k_nodes.append(node)
            top_k_scores.append(result["__nn_distance"])

        return VectorStoreQueryResult(
            nodes=top_k_nodes, similarities=top_k_scores, ids=top_k_ids
        )

    def delete(self, **delete_kwargs: Any) -> None:
        raise Exception("Not implemented.")
