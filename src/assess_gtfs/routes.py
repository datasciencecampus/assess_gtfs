"""Helpers for working with routes.txt."""
import os
import pathlib
import warnings
from typing import Union

import pandas as pd
import requests
from bs4 import BeautifulSoup

from assess_gtfs.utils.constants import PKG_PATH
from assess_gtfs.utils.defence import (
    _is_expected_filetype,
    _type_defence,
    _url_defence,
)

warnings.filterwarnings(
    action="ignore", category=DeprecationWarning, module=".*pkg_resources"
)
# see https://github.com/datasciencecampus/transport-network-performance/
# issues/19


def _construct_extended_schema_table(
    some_soup: BeautifulSoup, cd_list: list, desc_list: list
) -> (list, list):
    """Create the extended table from a soup object. Not exported.

    Parameters
    ----------
    some_soup : bs4.BeautifulSoup
        A bs4 soup representation of `ext_spec_url`.
    cd_list : list
        A list of schema codes scraped so far. Will append addiitonal codes to
        this list.
    desc_list : list
        A list of schema descriptions found so far. Will append additional
        descriptions to this list.

    Returns
    -------
    tuple[0]: list
        route_type codes of proposed GTFS scheme extension.
    tuple[1]: list
        route_type descriptions of proposed GTFS scheme extension.

    """
    for i in some_soup.findAll("table"):
        # target table has 'nice_table' class
        if i.get("class")[0] == "nice-table":
            target = i

    for row in target.tbody.findAll("tr"):
        # Get the table headers
        found = row.findAll("th")
        if found:
            cols = [f.text for f in found]
        else:
            # otherwise get the table data
            dat = [i.text for i in row.findAll("td")]
            # subset to the required column
            cd_list.append(dat[cols.index("Code")])
            desc_list.append(dat[cols.index("Description")])

    return (cd_list, desc_list)


def _get_response_text(url: str) -> str:
    """Return the response & extract the text. Not exported."""
    r = requests.get(url)
    t = r.text
    return t


def scrape_route_type_lookup(
    gtfs_url: str = "https://gtfs.org/schedule/reference/",
    ext_spec_url: str = (
        "https://developers.google.com/transit/gtfs/reference/"
        "extended-route-types"
    ),
    extended_schema: bool = True,
) -> pd.core.frame.DataFrame:
    """Scrape a lookup of GTFS route_type codes to descriptions.

    Scrapes HTML tables from `gtfs_url` to provide a lookup of `route_type`
    codes to human readable descriptions. Useful for confirming available
    modes of transport within a GTFS. If `extended_schema` is True, then also
    include the proposed extension of route_type to the GTFS.

    Parameters
    ----------
    gtfs_url : str, optional
        The url containing the GTFS accepted route_type codes. Defaults to
        "https://gtfs.org/schedule/reference/".
    ext_spec_url : str, optional
        The url containing the table of the proposed extension to the GTFS
        schema for route_type codes. Defaults to
        ( "https://developers.google.com/transit/gtfs/reference/"
        "extended-route-types" ).
    extended_schema : bool, optional
        Should the extended schema table be scraped and included in the output?
        Defaults to True.

    Returns
    -------
    pd.core.frame.DataFrame
        A lookup of route_type codes to descriptions.

    Raises
    ------
    ValueError
        `gtfs_url` or `ext_spec_url` are not "http" or "https" protocol.
    TypeError
        `extended_schema` is not of type bool.

    """
    # a little defence
    for url in [gtfs_url, ext_spec_url]:
        _url_defence(url)

    _type_defence(extended_schema, "extended_schema", bool)
    # Get the basic scheme lookup
    resp_txt = _get_response_text(gtfs_url)
    soup = BeautifulSoup(resp_txt, "html.parser")
    for dat in soup.findAll("td"):
        # Look for a pattern to target, going with Tram, could go more specific
        # with regex if table format unstable.
        if "Tram" in dat.text:
            target_node = dat

    cds = list()
    txts = list()
    # the required data is in awkward little inline 'table' that's really
    # a table row, but helpfully the data is either side of some break
    # tags
    for x in target_node.findAll("br"):
        cds.append(x.nextSibling.text)
        txts.append(x.previousSibling.text)
    # strip out rubbish
    cds = [cd for cd in cds if len(cd) > 0]
    txts = [t.strip(" - ") for t in txts if t.startswith(" - ")]
    # catch the final description which is not succeeded by a break
    txts.append(target_node.text.split(" - ")[-1])
    # if interested in the extended schema, get that too. Perhaps not
    # relevant to all territories
    if extended_schema:
        resp_txt = _get_response_text(ext_spec_url)
        soup = BeautifulSoup(resp_txt, "html.parser")
        cds, txts = _construct_extended_schema_table(soup, cds, txts)

    route_lookup = pd.DataFrame(zip(cds, txts), columns=["route_type", "desc"])

    return route_lookup


def get_saved_route_type_lookup(
    path: Union[str, pathlib.Path] = pathlib.Path(
        os.path.join(PKG_PATH, "data", "route_lookup.pkl")
    )
) -> pd.DataFrame:
    """Get the locally saved route type lookup as a dataframe.

    Parameters
    ----------
    path : Union[str, pathlib.Path], optional
        The path to the route type lookup,
        defaults to os.path.join(PKG_PATH, "data", "route_lookup.pkl")

    Returns
    -------
    pd.DataFrame
        The route type lookup

    """
    # defences
    _is_expected_filetype(
        pth=path, param_nm="path", check_existing=True, exp_ext=".pkl"
    )
    lookup = pd.read_pickle(path)
    ACCEPTED_TYPES = (dict, pd.DataFrame)
    # Check unserialized .pkl file is of correct type.
    # The rationale for not implementing _type_defence() here is that a more
    # informative error message provides better detail to the user in this
    # instance
    if not isinstance(lookup, ACCEPTED_TYPES):
        raise TypeError(
            "Serialized object in specified .pkl file is of type: "
            f"{type(lookup)}. Expected {ACCEPTED_TYPES}"
        )
    # convert dicts to pandas df
    if isinstance(lookup, dict):
        lookup = pd.DataFrame(lookup)
    if len(lookup) < 1:
        warnings.warn("Route type lookup has length of 0", UserWarning)
    EXPECTED_COLS = ["route_type", "desc"]
    # check columns
    for col in lookup.columns.values:
        if col.lower() not in EXPECTED_COLS:
            warnings.warn(
                f"Unexpected column '{col}' in route type lookup", UserWarning
            )

    return lookup
