from pydantic import BaseModel, Field, RootModel
from typing import Union, Dict


class LinkTemplate(BaseModel):
    template_url: str
    defaults: Dict[str, str] = Field(default_factory=dict)


LinkConfig = Union[str, LinkTemplate]


class GoLinksConfig(RootModel):
    root: Dict[str, LinkConfig]
