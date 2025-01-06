"""WordLift graph store index."""
import asyncio
import logging
from typing import Any, Dict, List, Optional

import fsspec
import nest_asyncio
import rdflib
import wordlift_client
from llama_index.core.graph_stores.types import GraphStore
from wordlift_client import Configuration, AccountInfo

logger = logging.getLogger(__name__)


def _ensure_trailing_slash(path: str) -> str:
    return path if path.endswith("/") else path + "/"


class WordLiftGraphStore(GraphStore):
    _account: AccountInfo
    _configuration: Configuration

    def __init__(
        self,
        key: str,
        api_url: str = "https://api.wordlift.io",
        **kwargs: Any,
    ) -> None:
        try:
            nest_asyncio.apply()
        except ValueError:
            # We may not be in asyncio
            pass

        # Defining the host is optional and defaults to https://api.wordlift.io
        # See configuration.py for a list of all supported configuration parameters.
        self._configuration = wordlift_client.Configuration(host=api_url)

        # Configure API key authorization: ApiKey
        self._configuration.api_key["ApiKey"] = key
        self._configuration.api_key_prefix["ApiKey"] = "Key"

        self._account = asyncio.get_event_loop().run_until_complete(
            self.get_account_async()
        )

    @property
    def client(self) -> Any:
        return asyncio.get_event_loop().run_until_complete(
            wordlift_client.ApiClient(self._configuration)
        )

    async def get_account_async(self) -> AccountInfo:
        """
        Get the AccountInfo.
        """
        async with wordlift_client.ApiClient(self._configuration) as api_client:
            # Create an instance of the API class
            api_instance = wordlift_client.AccountApi(api_client)

            try:
                # Get
                return await api_instance.get_me()

            except Exception as e:
                print("Exception when calling AccountApi->get_me: %s\n" % e)

    def get(self, subj: str) -> List[List[str]]:
        """Get triplets."""
        return asyncio.get_event_loop().run_until_complete(self.get_async(subj))

    async def get_async(self, subj: str) -> List[List[str]]:
        # Enter a context with an instance of the API client
        async with wordlift_client.ApiClient(self._configuration) as api_client:
            # Create an instance of the API class
            api_instance = wordlift_client.EntitiesApi(api_client)
            list_ids = [subj]  # List[str] | One or more ids, in the form of URLs.
            include_children = "false"  # str | Whether to return all the entities whose ids start with the provided ids, by default false. (optional) (default to 'false')
            include_referenced = "false"  # str | Whether to return all the referenced entities (e.g. in `schema:mentions`), by default false. (optional) (default to 'false')
            include_private = "true"  # str | Whether to return private properties, requires an authenticated request, by default false. (optional) (default to 'false')

            try:
                # Get
                api_response = await api_instance.get_entities(
                    list_ids,
                    include_children=include_children,
                    include_referenced=include_referenced,
                    include_private=include_private,
                    _headers={"Accept": "application/ld+json"},
                )

                # Create a graph
                g = rdflib.Graph()
                g.parse(data=api_response, format="json-ld")

                # Once parsed, you can iterate through the triples
                # Convert each triple to a list of strings
                subj_ref = rdflib.URIRef(subj)
                dataset_uri = _ensure_trailing_slash(self._account.dataset_uri)

                triples_list = []
                for s, p, o in g:
                    # Filter by subject and exclude literals
                    if s == subj_ref and str(o).startswith(dataset_uri):
                        triples_list.append([str(p), str(o)])
                return triples_list

            except Exception as e:
                print("Exception when calling EntitiesApi->get_entities: %s\n" % e)

    def get_rel_map(
        self, subjs: Optional[List[str]] = None, depth: int = 2, limit: int = 30
    ) -> Dict[str, List[List[str]]]:
        """Get depth-aware rel map."""
        return {}

        # @@TODO
        # rel_map: Dict[Any, List[Any]] = {}
        # if subjs is None or len(subjs) == 0:
        #     # unlike simple graph_store, we don't do get_all here
        #     return rel_map

    def upsert_triplet(self, subj: str, rel: str, obj: str) -> None:
        """Add triplet."""
        ...

    def delete(self, subj: str, rel: str, obj: str) -> None:
        """Delete triplet."""
        ...

    def persist(
        self, persist_path: str, fs: Optional[fsspec.AbstractFileSystem] = None
    ) -> None:
        """Persist the graph store to a file."""
        return

    def get_schema(self, refresh: bool = False) -> str:
        """Get the schema of the graph store."""
        ...

    def query(self, query: str, param_map: Optional[Dict[str, Any]] = {}) -> Any:
        """Query the graph store with statement and parameters."""
        ...

    # def get(self, subj: str) -> List[List[str]]:
    #     """Get triplets."""
    #     query = """
    #         MATCH (n1:%s)-[r]->(n2:%s)
    #         WHERE n1.id = $subj
    #         RETURN type(r), n2.id;
    #     """
    #
    #     prepared_statement = query % (self.node_label, self.node_label)
    #
    #     with self._driver.session(database=self._database) as session:
    #         data = session.run(prepared_statement, {"subj": subj})
    #         return [record.values() for record in data]
    #
    # def get_rel_map(
    #         self, subjs: Optional[List[str]] = None, depth: int = 2, limit: int = 30
    # ) -> Dict[str, List[List[str]]]:
    #     """Get flat rel map."""
    #     # The flat means for multi-hop relation path, we could get
    #     # knowledge like: subj -> rel -> obj -> rel -> obj -> rel -> obj.
    #     # This type of knowledge is useful for some tasks.
    #     # +-------------+------------------------------------+
    #     # | subj        | flattened_rels                     |
    #     # +-------------+------------------------------------+
    #     # | "player101" | [95, "player125", 2002, "team204"] |
    #     # | "player100" | [1997, "team204"]                  |
    #     # ...
    #     # +-------------+------------------------------------+
    #
    #     rel_map: Dict[Any, List[Any]] = {}
    #     if subjs is None or len(subjs) == 0:
    #         # unlike simple graph_store, we don't do get_all here
    #         return rel_map
    #
    #     query = (
    #         f"""MATCH p=(n1:{self.node_label})-[*1..{depth}]->() """
    #         f"""WHERE toLower(n1.id) IN {[subj.lower() for subj in subjs] if subjs else []}"""
    #         "UNWIND relationships(p) AS rel "
    #         "WITH n1.id AS subj, p, apoc.coll.flatten(apoc.coll.toSet("
    #         "collect([type(rel), endNode(rel).id]))) AS flattened_rels "
    #         f"RETURN subj, collect(flattened_rels) AS flattened_rels LIMIT {limit}"
    #     )
    #
    #     data = list(self.query(query, {"subjs": subjs}))
    #     if not data:
    #         return rel_map
    #
    #     for record in data:
    #         rel_map[record["subj"]] = record["flattened_rels"]
    #     return rel_map
    #
    # def upsert_triplet(self, subj: str, rel: str, obj: str) -> None:
    #     """Add triplet."""
    #     query = """
    #         MERGE (n1:`%s` {id:$subj})
    #         MERGE (n2:`%s` {id:$obj})
    #         MERGE (n1)-[:`%s`]->(n2)
    #     """
    #
    #     prepared_statement = query % (
    #         self.node_label,
    #         self.node_label,
    #         rel.replace(" ", "_").upper(),
    #     )
    #
    #     with self._driver.session(database=self._database) as session:
    #         session.run(prepared_statement, {"subj": subj, "obj": obj})
    #
    # def delete(self, subj: str, rel: str, obj: str) -> None:
    #     """Delete triplet."""
    #
    #     def delete_rel(subj: str, obj: str, rel: str) -> None:
    #         with self._driver.session(database=self._database) as session:
    #             session.run(
    #                 (
    #                     "MATCH (n1:{})-[r:{}]->(n2:{}) WHERE n1.id = $subj AND n2.id"
    #                     " = $obj DELETE r"
    #                 ).format(self.node_label, rel, self.node_label),
    #                 {"subj": subj, "obj": obj},
    #             )
    #
    #     def delete_entity(entity: str) -> None:
    #         with self._driver.session(database=self._database) as session:
    #             session.run(
    #                 "MATCH (n:%s) WHERE n.id = $entity DELETE n" % self.node_label,
    #                 {"entity": entity},
    #             )
    #
    #     def check_edges(entity: str) -> bool:
    #         with self._driver.session(database=self._database) as session:
    #             is_exists_result = session.run(
    #                 "MATCH (n1:%s)--() WHERE n1.id = $entity RETURN count(*)"
    #                 % (self.node_label),
    #                 {"entity": entity},
    #             )
    #             return bool(list(is_exists_result))
    #
    #     delete_rel(subj, obj, rel)
    #     if not check_edges(subj):
    #         delete_entity(subj)
    #     if not check_edges(obj):
    #         delete_entity(obj)
    #
    # def refresh_schema(self) -> None:
    #     """
    #     Refreshes the WordLift graph schema information.
    #     """
    #     node_properties = [el["output"] for el in self.query(node_properties_query)]
    #     rel_properties = [el["output"] for el in self.query(rel_properties_query)]
    #     relationships = [el["output"] for el in self.query(rel_query)]
    #
    #     self.structured_schema = {
    #         "node_props": {el["labels"]: el["properties"] for el in node_properties},
    #         "rel_props": {el["type"]: el["properties"] for el in rel_properties},
    #         "relationships": relationships,
    #     }
    #
    #     # Format node properties
    #     formatted_node_props = []
    #     for el in node_properties:
    #         props_str = ", ".join(
    #             [f"{prop['property']}: {prop['type']}" for prop in el["properties"]]
    #         )
    #         formatted_node_props.append(f"{el['labels']} {{{props_str}}}")
    #
    #     # Format relationship properties
    #     formatted_rel_props = []
    #     for el in rel_properties:
    #         props_str = ", ".join(
    #             [f"{prop['property']}: {prop['type']}" for prop in el["properties"]]
    #         )
    #         formatted_rel_props.append(f"{el['type']} {{{props_str}}}")
    #
    #     # Format relationships
    #     formatted_rels = [
    #         f"(:{el['start']})-[:{el['type']}]->(:{el['end']})" for el in relationships
    #     ]
    #
    #     self.schema = "\n".join(
    #         [
    #             "Node properties are the following:",
    #             ",".join(formatted_node_props),
    #             "Relationship properties are the following:",
    #             ",".join(formatted_rel_props),
    #             "The relationships are the following:",
    #             ",".join(formatted_rels),
    #         ]
    #     )
    #
    # def get_schema(self, refresh: bool = False) -> str:
    #     """Get the schema of the WordLiftGraph store."""
    #     if self.schema and not refresh:
    #         return self.schema
    #     self.refresh_schema()
    #     logger.debug(f"get_schema() schema:\n{self.schema}")
    #     return self.schema
    #
    # def query(self, query: str, param_map: Optional[Dict[str, Any]] = None) -> Any:
    #     param_map = param_map or {}
    #     try:
    #         data, _, _ = self._driver.execute_query(
    #             WordLift.Query(text=query, timeout=self._timeout),
    #             database_=self._database,
    #             parameters_=param_map,
    #         )
    #         return [r.data() for r in data]
    #     except WordLift.exceptions.WordLiftError as e:
    #         if not (
    #                 (
    #                         (  # isCallInTransactionError
    #                                 e.code == "Neo.DatabaseError.Statement.ExecutionFailed"
    #                                 or e.code
    #                                 == "Neo.DatabaseError.Transaction.TransactionStartFailed"
    #                         )
    #                         and "in an implicit transaction" in e.message
    #                 )
    #                 or (  # isPeriodicCommitError
    #                         e.code == "Neo.ClientError.Statement.SemanticError"
    #                         and (
    #                                 "in an open transaction is not possible" in e.message
    #                                 or "tried to execute in an explicit transaction" in e.message
    #                         )
    #                 )
    #         ):
    #             raise
    #     # Fallback to allow implicit transactions
    #     with self._driver.session(database=self._database) as session:
    #         data = session.run(
    #             WordLift.Query(text=query, timeout=self._timeout), param_map
    #         )
    #         return [r.data() for r in data]
