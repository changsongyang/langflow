from typing import Any

from langflow.custom import Component
from langflow.io import (
    BoolInput,
    HandleInput,
    MultilineInput,
    Output,
    StrInput,
)
from langflow.schema import Data, DataFrame
from langflow.schema.message import Message


class ParserComponent(Component):
    display_name = "Parser"
    description = (
        "Format a DataFrame or Data object into text using a template. "
        "Enable 'Stringify' to convert input into a readable string instead."
    )
    icon = "braces"
    name = "Parser"

    inputs = [
        BoolInput(
            name="stringify",
            display_name="Stringify",
            info="Enable to convert input to a string instead of using a template.",
            value=False,
            real_time_refresh=True,
        ),
        MultilineInput(
            name="template",
            display_name="Template",
            info="Use placeholders like '{Name}', '{Age}' for DataFrames or '{text}' for Data.",
            value="Name: {Name}, Age: {Age}, Country: {Country}",  # Example default
            dynamic=True,
            show=True,
            required=True,
        ),
        HandleInput(
            name="input_data",
            display_name="Data or DataFrame",
            input_types=["DataFrame", "Data"],
            info="Accepts either a DataFrame or a Data object.",
            required=True,
        ),
        StrInput(
            name="sep",
            display_name="Separator",
            advanced=True,
            value="\n",
            info="String used to separate rows/items.",
        ),
        BoolInput(
            name="clean_data",
            display_name="Clean Data",
            info="Enable to clean the data by removing empty rows and lines in each cell.",
            value=False,
            show=False,
            required=False,
        ),
    ]

    outputs = [
        Output(
            display_name="Parsed Text",
            name="parsed_text",
            info="Formatted text output.",
            method="parse_combined_text",
        ),
    ]

    def update_build_config(self, build_config, field_value, field_name=None):
        """Dynamically hide/show `template` and enforce requirement based on `stringify`."""
        if field_name == "stringify":
            build_config["template"]["show"] = not field_value
            build_config["template"]["required"] = not field_value
            build_config["clean_data"]["show"] = field_value
            build_config["clean_data"]["required"] = field_value
        return build_config

    def _clean_args(self):
        """Prepare arguments based on input type."""
        input_data = self.input_data
        if isinstance(input_data, list) and all(isinstance(item, Data) for item in input_data):
            msg = "List of Data objects is not supported."
            raise ValueError(msg)
        if isinstance(input_data, DataFrame):
            return input_data, None, self.template, self.sep, self.stringify
        if isinstance(input_data, Data):
            return None, input_data, self.template, self.sep, self.stringify
        if isinstance(input_data, dict) and "data" in input_data:
            try:
                if "columns" in input_data:  # Likely a DataFrame
                    return DataFrame.from_dict(input_data), None, self.template, self.sep, self.stringify
                # Likely a Data object
                return None, Data(**input_data), self.template, self.sep, self.stringify
            except (TypeError, ValueError, KeyError) as e:
                msg = f"Invalid structured input provided: {e!s}"
                raise ValueError(msg) from e
        else:
            msg = f"Unsupported input type: {type(input_data)}. Expected DataFrame or Data."
            raise ValueError(msg)

    def parse_combined_text(self) -> Message:
        """Parse all rows/items into a single text or convert input to string if `stringify` is enabled."""
        df, data, template, sep, stringify = self._clean_args()

        if stringify:
            return self.convert_to_string()

        lines = []

        if df is not None:
            for _, row in df.iterrows():
                formatted_text = template.format(**row.to_dict())
                lines.append(formatted_text)
        elif data is not None:
            formatted_text = template.format(text=data.get_text())
            lines.append(formatted_text)

        combined_text = sep.join(lines)
        self.status = combined_text
        return Message(text=combined_text)

    def _validate_input(self) -> None:
        """Validate the input data and raise ValueError if invalid."""
        if self.input_data is None:
            msg = "Input data cannot be None"
            raise ValueError(msg)
        if not isinstance(self.input_data, Data | DataFrame | Message | str | list):
            msg = f"Expected Data or DataFrame or Message or str, got {type(self.input_data).__name__}"
            raise TypeError(msg)

    def _safe_convert(self, data: Any) -> str:
        """Safely convert input data to string."""
        try:
            if isinstance(data, str):
                return data
            if isinstance(data, Message):
                return data.get_text()
            if isinstance(data, Data):
                if data.get_text() is None:
                    msg = "Empty Data object"
                    raise ValueError(msg)
                return data.get_text()
            if isinstance(data, DataFrame):
                if hasattr(self, "clean_data") and self.clean_data:
                    # Remove empty rows
                    data = data.dropna(how="all")
                    # Remove empty lines in each cell
                    data = data.replace(r"^\s*$", "", regex=True)
                    # Replace multiple newlines with a single newline
                    data = data.replace(r"\n+", "\n", regex=True)
                return data.to_markdown(index=False)
            return str(data)
        except (ValueError, TypeError, AttributeError) as e:
            msg = f"Error converting data: {e!s}"
            raise ValueError(msg) from e

    def convert_to_string(self) -> Message:
        """Convert input data to string with proper error handling."""
        self._validate_input()
        result = ""
        if isinstance(self.input_data, list):
            result = "\n".join([self._safe_convert(item) for item in self.input_data])
        else:
            result = self._safe_convert(self.input_data)
        self.log(f"Converted to string with length: {len(result)}")
        return Message(text=result)
