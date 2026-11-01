'''Resolve the OpenRouteService base URL and derive related endpoints.'''
import os


DEFAULT_MATRIX_URL = 'http://localhost:8080/ors/v2/matrix/driving-car'


def resolve_ors_url(cli_override: str | None = None) -> str:
    '''Return the ORS matrix URL: CLI override, then $ORS_URL, then default.

    Args:
        cli_override: Optional URL string from the CLI --server flag. An empty
            string is treated as "not provided" so callers can pass argparse
            defaults without a special case.

    Returns:
        The resolved ORS matrix endpoint URL.
    '''
    if cli_override:
        return cli_override
    return os.environ.get('ORS_URL') or DEFAULT_MATRIX_URL


def directions_url_from_matrix_url(matrix_url: str) -> str:
    '''Derive the single-pair directions endpoint from a matrix endpoint URL.

    Args:
        matrix_url: An ORS matrix endpoint URL containing the ``/matrix/`` path segment.

    Returns:
        The corresponding directions endpoint URL.

    Raises:
        ValueError: If ``matrix_url`` does not contain ``/matrix/``.
    '''
    if '/matrix/' not in matrix_url:
        raise ValueError(f"Expected '/matrix/' segment in URL: {matrix_url}")
    return matrix_url.replace('/matrix/', '/directions/')
