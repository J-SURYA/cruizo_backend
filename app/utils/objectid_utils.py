from bson import ObjectId
from pydantic_core import core_schema
from pydantic import GetCoreSchemaHandler, GetJsonSchemaHandler
from pydantic.json_schema import JsonSchemaValue


class PyObjectId(ObjectId):
    """Custom Pydantic type for MongoDB ObjectId."""

    @classmethod
    def __get_pydantic_core_schema__(
        cls, source_type, handler: GetCoreSchemaHandler
    ) -> core_schema.CoreSchema:
        """Pydantic v2 core schema validator for ObjectId."""

        def validate(v):
            if not ObjectId.is_valid(v):
                raise ValueError("Invalid ObjectId")
            return ObjectId(v)

        return core_schema.no_info_plain_validator_function(validate)

    @classmethod
    def __get_pydantic_json_schema__(
        cls, schema: core_schema.CoreSchema, handler: GetJsonSchemaHandler
    ) -> JsonSchemaValue:
        """Pydantic v2 JSON schema for OpenAPI documentation."""
        return {"type": "string", "pattern": "^[a-fA-F0-9]{24}$"}
