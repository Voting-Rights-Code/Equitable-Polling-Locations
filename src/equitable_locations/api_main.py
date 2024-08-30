from litestar import Litestar, MediaType, Request, Response, get, post
from litestar.status_codes import HTTP_500_INTERNAL_SERVER_ERROR
from logzero import logger
from equitable_locations.io.census import CensusData

from pydantic import BaseModel


class CensusModel(BaseModel):
    county_name: str
    county_state: str


@get("/")
async def hello_world() -> str:
    return "Hello, world!"


@post("/initialize-census")
def initialize_census(data: CensusModel) -> dict[str, str]:
    census = CensusData(data.county_name, data.county_state)
    return {"message": f"Census initialized for {data.county_name}"}


def internal_server_error_handler(request: Request, exc: Exception) -> Response:
    logger.error("Encountered HTTP_500_INTERNAL_SERVER_ERROR")
    logger.exception(exc)
    return Response(
        media_type=MediaType.TEXT,
        content=f"Server Error: {exc}",
        status_code=500,
    )


app = Litestar(
    route_handlers=[hello_world, initialize_census],
    exception_handlers={HTTP_500_INTERNAL_SERVER_ERROR: internal_server_error_handler},
)
