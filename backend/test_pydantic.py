from pydantic import BaseModel, field_validator

class Test(BaseModel):
    urls: list[str]

    @field_validator('urls', mode='before')
    def split_urls(cls, v):
        return [v] if isinstance(v, str) else v

t = Test(urls='a,b')
print(t)
