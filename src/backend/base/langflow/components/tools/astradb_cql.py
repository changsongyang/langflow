import urllib
from http import HTTPStatus

from langflow.schema.dataframe import DataFrame
import requests

from langflow.custom import Component
from langflow.io import DictInput, IntInput, MessageTextInput, Output, SecretStrInput
from langflow.schema import Data


class AstraDBCQLToolComponent(Component):
    display_name: str = "Astra DB CQL"
    description: str = "Create a tool to get transactional data from DataStax Astra DB CQL Table"
    documentation: str = "https://docs.langflow.org/Components/components-tools#astra-db-cql-tool"
    icon: str = "AstraDB"

    inputs = [
        MessageTextInput(
            name="keyspace",
            display_name="Keyspace",
            value="default_keyspace",
            info="The keyspace name within Astra DB where the data is stored.",
            required=True,
            advanced=True,
        ),
        MessageTextInput(
            name="table_name",
            display_name="Table Name",
            info="The name of the table within Astra DB where the data is stored.",
            required=True,
        ),
        SecretStrInput(
            name="token",
            display_name="Astra DB Application Token",
            info="Authentication token for accessing Astra DB.",
            value="ASTRA_DB_APPLICATION_TOKEN",
            required=True,
        ),
        MessageTextInput(
            name="api_endpoint",
            display_name="API Endpoint",
            info="API endpoint URL for the Astra DB service.",
            value="ASTRA_DB_API_ENDPOINT",
            required=True,
        ),
        MessageTextInput(
            name="projection_fields",
            display_name="Projection fields",
            info="Attributes to return separated by comma.",
            required=True,
            value="*",
            advanced=True,
        ),
        DictInput(
            name="partition_keys",
            display_name="Partition Keys",
            is_list=True,
            info="Field name and description to the model",
            required=True,
            tool_mode=True,
        ),
        DictInput(
            name="clustering_keys",
            display_name="Clustering Keys",
            is_list=True,
            info="Field name and description to the model",
            tool_mode=True,
        ),
        DictInput(
            name="static_filters",
            display_name="Static Filters",
            is_list=True,
            advanced=True,
            info="Field name and value. When filled, it will not be generated by the LLM.",
        ),
        IntInput(
            name="number_of_results",
            display_name="Number of Results",
            info="Number of results to return.",
            advanced=True,
            value=5,
        ),
    ]
    outputs = [
        Output(name="api_run_model", display_name="Data", method="run_model"),
        Output(name="api_as_dataframe", display_name="Dataframe", method="as_dataframe",tool_mode=False),
    ]

    def astra_rest(self, args):
        headers = {"Accept": "application/json", "X-Cassandra-Token": f"{self.token}"}
        astra_url = f"{self.api_endpoint}/api/rest/v2/keyspaces/{self.keyspace}/{self.table_name}/"
        key = []

        # Partition keys are mandatory
        key = [self.partition_keys[k] for k in self.partition_keys]

        # Clustering keys are optional
        for k in self.clustering_keys:
            if k in args:
                key.append(args[k])
            elif self.static_filters[k] is not None:
                key.append(self.static_filters[k])

        url = f"{astra_url}{'/'.join(key)}?page-size={self.number_of_results}"

        if self.projection_fields != "*":
            url += f"&fields={urllib.parse.quote(self.projection_fields.replace(' ', ''))}"

        res = requests.request("GET", url=url, headers=headers, timeout=10)

        if int(res.status_code) >= HTTPStatus.BAD_REQUEST:
            return res.text

        try:
            res_data = res.json()
            return res_data["data"]
        except ValueError:
            return res.status_code

    def projection_args(self, input_str: str) -> dict:
        elements = input_str.split(",")
        result = {}

        for element in elements:
            if element.startswith("!"):
                result[element[1:]] = False
            else:
                result[element] = True

        return result

    def run_model(self, **args) -> Data | list[Data]:
        results = self.astra_rest(args)
        data: list[Data] = [Data(data=doc) for doc in results]
        self.status = data
        return results

    def as_dataframe(self, **args) -> DataFrame:
        results = self.astra_rest(args)
        results = self.astra_rest(args)
        data: list[Data] = [Data(data=doc) for doc in results]
        return DataFrame(data)
