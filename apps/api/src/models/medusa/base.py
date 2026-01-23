from pydantic import BaseModel, ConfigDict


class MedusaBaseModel(BaseModel):
    model_config = ConfigDict(extra="allow")
