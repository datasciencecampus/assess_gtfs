"""Tests for validation module."""
import pytest
from pyprojroot import here
import gtfs_kit as gk
import pandas as pd
from unittest.mock import patch, call
import os
from geopandas import GeoDataFrame
import numpy as np
import re
import pathlib

from transport_performance.gtfs.validation import (
    GtfsInstance,
    _get_intermediate_dates,
    _create_map_title_text,
)


@pytest.fixture(scope="function")  # some funcs expect cleaned feed others dont
def gtfs_fixture():
    """Fixture for test funcs expecting a valid feed object."""
    gtfs = GtfsInstance()
    return gtfs


class TestGtfsInstance(object):
    """Tests related to the GtfsInstance class."""

    def test_init_defensive_behaviours(self):
        """Testing parameter validation on class initialisation."""
        with pytest.raises(
            TypeError,
            match=r"`gtfs_pth` expected path-like, found <class 'int'>.",
        ):
            GtfsInstance(gtfs_pth=1)
        with pytest.raises(
            FileExistsError, match=r"doesnt/exist not found on file."
        ):
            GtfsInstance(gtfs_pth="doesnt/exist")
        #  a case where file is found but not a zip directory
        with pytest.raises(
            ValueError,
            match=r"`gtfs_pth` expected file extension .zip. Found .pbf",
        ):
            GtfsInstance(
                gtfs_pth=here("tests/data/newport-2023-06-13.osm.pbf")
            )
        # handling units
        with pytest.raises(
            TypeError, match=r"`units` expected a string. Found <class 'bool'>"
        ):
            GtfsInstance(units=False)
        # non metric units
        with pytest.raises(
            ValueError, match=r"`units` accepts metric only. Found: miles"
        ):
            GtfsInstance(units="Miles")  # imperial units not implemented

    def test_init_on_pass(self):
        """Assertions about the feed attribute."""
        gtfs = GtfsInstance()
        assert isinstance(
            gtfs.feed, gk.feed.Feed
        ), f"GExpected gtfs_kit feed attribute. Found: {type(gtfs.feed)}"
        assert (
            gtfs.feed.dist_units == "m"
        ), f"Expected 'm', found: {gtfs.feed.dist_units}"
        # can coerce to correct distance unit?
        gtfs1 = GtfsInstance(units="kilometers")
        assert (
            gtfs1.feed.dist_units == "km"
        ), f"Expected 'km', found: {gtfs1.feed.dist_units}"
        gtfs2 = GtfsInstance(units="metres")
        assert (
            gtfs2.feed.dist_units == "m"
        ), f"Expected 'm', found: {gtfs2.feed.dist_units}"

    def test_is_valid(self, gtfs_fixture):
        """Assertions about validity_df table."""
        gtfs_fixture.is_valid()
        assert isinstance(
            gtfs_fixture.validity_df, pd.core.frame.DataFrame
        ), f"Expected DataFrame. Found: {type(gtfs_fixture.validity_df)}"
        shp = gtfs_fixture.validity_df.shape
        assert shp == (
            7,
            4,
        ), f"Attribute `validity_df` expected a shape of (7,4). Found: {shp}"
        exp_cols = pd.Index(["type", "message", "table", "rows"])
        found_cols = gtfs_fixture.validity_df.columns
        assert (
            found_cols == exp_cols
        ).all(), f"Expected columns {exp_cols}. Found: {found_cols}"

    @patch("builtins.print")
    def test_print_alerts_defence(self, mocked_print, gtfs_fixture):
        """Check defensive behaviour of print_alerts()."""
        with pytest.raises(
            AttributeError,
            match=r"is None, did you forget to use `self.is_valid()`?",
        ):
            gtfs_fixture.print_alerts()

        gtfs_fixture.is_valid()
        gtfs_fixture.print_alerts(alert_type="doesnt_exist")
        fun_out = mocked_print.mock_calls
        assert fun_out == [
            call("No alerts of type doesnt_exist were found.")
        ], f"Expected a print about alert_type but found: {fun_out}"

    @patch("builtins.print")  # testing print statements
    def test_print_alerts_single_case(self, mocked_print, gtfs_fixture):
        """Check alerts print as expected without truncation."""
        gtfs_fixture.is_valid()
        gtfs_fixture.print_alerts()
        # fixture contains single error
        fun_out = mocked_print.mock_calls
        assert fun_out == [
            call("Invalid route_type; maybe has extra space characters")
        ], f"Expected a print about invalid route type. Found {fun_out}"

    @patch("builtins.print")
    def test_print_alerts_multi_case(self, mocked_print, gtfs_fixture):
        """Check multiple alerts are printed as expected."""
        gtfs_fixture.is_valid()
        # fixture contains several warnings
        gtfs_fixture.print_alerts(alert_type="warning")
        fun_out = mocked_print.mock_calls
        assert fun_out == [
            call("Unrecognized column agency_noc"),
            call("Repeated pair (route_short_name, route_long_name)"),
            call("Unrecognized column stop_direction_name"),
            call("Unrecognized column platform_code"),
            call("Unrecognized column trip_direction_name"),
            call("Unrecognized column vehicle_journey_code"),
        ], f"Expected print statements about GTFS warnings. Found: {fun_out}"

    @patch("builtins.print")
    def test_viz_stops_defence(self, mocked_print, gtfs_fixture):
        """Check defensive behaviours of viz_stops()."""
        with pytest.raises(
            TypeError,
            match="`out_pth` expected path-like, found <class 'bool'>",
        ):
            gtfs_fixture.viz_stops(out_pth=True)
        with pytest.raises(
            TypeError, match="`geoms` expects a string. Found <class 'int'>"
        ):
            gtfs_fixture.viz_stops(out_pth="outputs/somefile.html", geoms=38)
        with pytest.raises(
            ValueError, match="`geoms` must be either 'point' or 'hull."
        ):
            gtfs_fixture.viz_stops(
                out_pth="outputs/somefile.html", geoms="foobar"
            )
        with pytest.raises(
            TypeError,
            match="`geom_crs`.*string or integer. Found <class 'float'>",
        ):
            gtfs_fixture.viz_stops(
                out_pth="outputs/somefile.html", geom_crs=1.1
            )
        # check missing stop_id results in print instead of exception
        gtfs_fixture.feed.stops.drop("stop_id", axis=1, inplace=True)
        gtfs_fixture.viz_stops(out_pth="outputs/out.html")
        fun_out = mocked_print.mock_calls
        assert fun_out == [
            call("Key Error. Map was not written.")
        ], f"Expected confirmation that map was not written. Found: {fun_out}"

    @patch("builtins.print")
    def test_viz_stops_point(self, mock_print, tmpdir, gtfs_fixture):
        """Check behaviour of viz_stops when plotting point geom."""
        tmp = os.path.join(tmpdir, "points.html")
        gtfs_fixture.viz_stops(out_pth=pathlib.Path(tmp))
        assert os.path.exists(
            tmp
        ), f"{tmp} was expected to exist but it was not found."
        # check behaviour when parent directory doesn't exist
        no_parent_pth = os.path.join(tmpdir, "notfound", "points1.html")
        gtfs_fixture.viz_stops(
            out_pth=pathlib.Path(no_parent_pth), create_out_parent=True
        )
        assert os.path.exists(
            no_parent_pth
        ), f"{no_parent_pth} was expected to exist but it was not found."
        # check behaviour when not implemented fileext used
        tmp1 = os.path.join(tmpdir, "points2.svg")
        gtfs_fixture.viz_stops(out_pth=pathlib.Path(tmp1))
        # need to use regex for the first print statement, as tmpdir will
        # change.
        start_pat = re.compile(r"Creating parent directory:.*")
        out = mock_print.mock_calls[0].__str__()
        assert bool(
            start_pat.search(out)
        ), f"Print statement about directory creation expected. Found: {out}"
        out_last = mock_print.mock_calls[-1]
        assert out_last == call(
            ".svg format not implemented. Writing to .html"
        ), f"Expected print statement about .svg. Found: {out_last}"
        write_pth = os.path.join(tmpdir, "points2.html")
        assert os.path.exists(
            write_pth
        ), f"Map should have been written to {write_pth} but was not found."

    def test_viz_stops_hull(self, tmpdir, gtfs_fixture):
        """Check viz_stops behaviour when plotting hull geom."""
        tmp = os.path.join(tmpdir, "hull.html")
        gtfs_fixture.viz_stops(out_pth=pathlib.Path(tmp), geoms="hull")
        assert os.path.exists(
            tmp
        ), f"Map should have been written to {tmp} but was not found."

    def test__create_map_title_text_defence(self, gtfs_fixture):
        """Test the defences for _create_map_title_text()."""
        # CRS without m or km units
        gtfs_hull = gtfs_fixture.feed.compute_convex_hull()
        gdf = GeoDataFrame({"geometry": gtfs_hull}, index=[0], crs="epsg:4326")
        with pytest.raises(ValueError), pytest.warns(UserWarning):
            _create_map_title_text(gdf=gdf, units="m", geom_crs=4326)

    def test__create_map_title_text_on_pass(self):
        """Check helper can cope with non-metric cases."""
        gdf = GeoDataFrame()
        txt = _create_map_title_text(gdf=gdf, units="miles", geom_crs=27700)
        assert txt == (
            "GTFS Stops Convex Hull. Area Calculation for Metric Units Only. "
            "Units Found are in miles."
        ), f"Unexpected text output: {txt}"

    def test__get_intermediate_dates(self):
        """Check function can handle valid and invalid arguments."""
        # invalid arguments
        with pytest.raises(
            TypeError,
            match="'start' expected type pd.Timestamp."
            " Recieved type <class 'str'>",
        ):
            _get_intermediate_dates(
                start="2023-05-02", end=pd.Timestamp("2023-05-08")
            )
        with pytest.raises(
            TypeError,
            match="'end' expected type pd.Timestamp."
            " Recieved type <class 'str'>",
        ):
            _get_intermediate_dates(
                start=pd.Timestamp("2023-05-02"), end="2023-05-08"
            )

        # valid arguments
        dates = _get_intermediate_dates(
            pd.Timestamp("2023-05-01"), pd.Timestamp("2023-05-08")
        )
        assert dates == [
            pd.Timestamp("2023-05-01"),
            pd.Timestamp("2023-05-02"),
            pd.Timestamp("2023-05-03"),
            pd.Timestamp("2023-05-04"),
            pd.Timestamp("2023-05-05"),
            pd.Timestamp("2023-05-06"),
            pd.Timestamp("2023-05-07"),
            pd.Timestamp("2023-05-08"),
        ]

    def test__order_dataframe_by_day_defence(self, gtfs_fixture):
        """Test __order_dataframe_by_day defences."""
        with pytest.raises(
            TypeError,
            match="'df' expected type pd.DataFrame, got <class 'str'>",
        ):
            (gtfs_fixture._order_dataframe_by_day(df="test"))
        with pytest.raises(
            TypeError,
            match="'day_column_name' expected type str, got <class 'int'>",
        ):
            (
                gtfs_fixture._order_dataframe_by_day(
                    df=pd.DataFrame(), day_column_name=5
                )
            )

    def test_get_route_modes(self, gtfs_fixture, mocker):
        """Assertions about the table returned by get_route_modes()."""
        patch_scrape_lookup = mocker.patch(
            "transport_performance.gtfs.validation.scrape_route_type_lookup",
            # be sure to patch the func wherever it's being called
            return_value=pd.DataFrame(
                {"route_type": ["3"], "desc": ["Mocked bus"]}
            ),
        )
        gtfs_fixture.get_route_modes()
        # check mocker was called
        assert (
            patch_scrape_lookup.called
        ), "mocker.patch `patch_scrape_lookup` was not called."
        found = gtfs_fixture.route_mode_summary_df["desc"][0]
        assert found == "Mocked bus", f"Expected 'Mocked bus', found: {found}"
        assert isinstance(
            gtfs_fixture.route_mode_summary_df, pd.core.frame.DataFrame
        ), f"Expected pd df. Found: {type(gtfs_fixture.route_mode_summary_df)}"
        exp_cols = pd.Index(["route_type", "desc", "n_routes", "prop_routes"])
        found_cols = gtfs_fixture.route_mode_summary_df.columns
        assert (
            found_cols == exp_cols
        ).all(), f"Expected columns are different. Found: {found_cols}"

    def test__preprocess_trips_and_routes(self, gtfs_fixture):
        """Check the outputs of _pre_process_trips_and_route() (test data)."""
        returned_df = gtfs_fixture._preprocess_trips_and_routes()
        assert isinstance(returned_df, pd.core.frame.DataFrame), (
            "Expected DF for _preprocess_trips_and_routes() return,"
            f"found {type(returned_df)}"
        )
        expected_columns = pd.Index(
            [
                "route_id",
                "service_id",
                "trip_id",
                "trip_headsign",
                "block_id",
                "shape_id",
                "wheelchair_accessible",
                "trip_direction_name",
                "vehicle_journey_code",
                "day",
                "date",
                "agency_id",
                "route_short_name",
                "route_long_name",
                "route_type",
            ]
        )
        assert (returned_df.columns == expected_columns).all(), (
            f"Columns not as expected. Expected {expected_columns},",
            f"Found {returned_df.columns}",
        )
        expected_shape = (281627, 15)
        assert returned_df.shape == expected_shape, (
            f"Columns not as expected. Expected {expected_shape},",
            f"Found {returned_df.shape}",
        )

    def test_summarise_trips_defence(self, gtfs_fixture):
        """Defensive checks for summarise_trips()."""
        with pytest.raises(
            TypeError,
            match="Each item in `summ_ops`.*. Found <class 'str'> : np.mean",
        ):
            gtfs_fixture.summarise_trips(summ_ops=[np.mean, "np.mean"])
        # case where is function but not exported from numpy

        def dummy_func():
            """Test case func."""
            return None

        with pytest.raises(
            TypeError,
            match=(
                "Each item in `summ_ops` must be a numpy function. Found"
                " <class 'function'> : dummy_func"
            ),
        ):
            gtfs_fixture.summarise_trips(summ_ops=[np.min, dummy_func])
        # case where a single non-numpy func is being passed
        with pytest.raises(
            NotImplementedError,
            match="`summ_ops` expects numpy functions only.",
        ):
            gtfs_fixture.summarise_trips(summ_ops=dummy_func)
        with pytest.raises(
            TypeError,
            match="`summ_ops` expects a numpy function.*. Found <class 'int'>",
        ):
            gtfs_fixture.summarise_trips(summ_ops=38)
        # cases where return_summary are not of type boolean
        with pytest.raises(
            TypeError,
            match="'return_summary' must be of type boolean."
            " Found <class 'int'> : 5",
        ):
            gtfs_fixture.summarise_trips(return_summary=5)
        with pytest.raises(
            TypeError,
            match="'return_summary' must be of type boolean."
            " Found <class 'str'> : true",
        ):
            gtfs_fixture.summarise_trips(return_summary="true")

    def test_summarise_routes_defence(self, gtfs_fixture):
        """Defensive checks for summarise_routes()."""
        with pytest.raises(
            TypeError,
            match="Each item in `summ_ops`.*. Found <class 'str'> : np.mean",
        ):
            gtfs_fixture.summarise_trips(summ_ops=[np.mean, "np.mean"])
        # case where is function but not exported from numpy

        def dummy_func():
            """Test case func."""
            return None

        with pytest.raises(
            TypeError,
            match=(
                "Each item in `summ_ops` must be a numpy function. Found"
                " <class 'function'> : dummy_func"
            ),
        ):
            gtfs_fixture.summarise_routes(summ_ops=[np.min, dummy_func])
        # case where a single non-numpy func is being passed
        with pytest.raises(
            NotImplementedError,
            match="`summ_ops` expects numpy functions only.",
        ):
            gtfs_fixture.summarise_routes(summ_ops=dummy_func)
        with pytest.raises(
            TypeError,
            match="`summ_ops` expects a numpy function.*. Found <class 'int'>",
        ):
            gtfs_fixture.summarise_routes(summ_ops=38)
        # cases where return_summary are not of type boolean
        with pytest.raises(
            TypeError,
            match="'return_summary' must be of type boolean."
            " Found <class 'int'> : 5",
        ):
            gtfs_fixture.summarise_routes(return_summary=5)
        with pytest.raises(
            TypeError,
            match="'return_summary' must be of type boolean."
            " Found <class 'str'> : true",
        ):
            gtfs_fixture.summarise_routes(return_summary="true")

    @patch("builtins.print")
    def test_clean_feed_defence(self, mock_print, gtfs_fixture):
        """Check defensive behaviours of clean_feed()."""
        # Simulate condition where shapes.txt has no shape_id
        gtfs_fixture.feed.shapes.drop("shape_id", axis=1, inplace=True)
        gtfs_fixture.clean_feed()
        fun_out = mock_print.mock_calls
        assert fun_out == [
            call("KeyError. Feed was not cleaned.")
        ], f"Expected print statement about KeyError. Found: {fun_out}."

    def test_summarise_trips_on_pass(self, gtfs_fixture):
        """Assertions about the outputs from summarise_trips()."""
        gtfs_fixture.summarise_trips()
        # tests the daily_routes_summary return schema
        assert isinstance(
            gtfs_fixture.daily_trip_summary, pd.core.frame.DataFrame
        ), (
            "Expected DF for daily_summary,"
            f"found {type(gtfs_fixture.daily_trip_summary)}"
        )

        found_ds = gtfs_fixture.daily_trip_summary.columns
        exp_cols_ds = pd.MultiIndex.from_tuples(
            [
                ("day", ""),
                ("route_type", ""),
                ("trip_count", "max"),
                ("trip_count", "mean"),
                ("trip_count", "median"),
                ("trip_count", "min"),
            ]
        )

        assert (
            found_ds == exp_cols_ds
        ).all(), f"Columns were not as expected. Found {found_ds}"

        # tests the self.dated_route_counts return schema
        assert isinstance(
            gtfs_fixture.dated_trip_counts, pd.core.frame.DataFrame
        ), (
            "Expected DF for dated_route_counts,"
            f"found {type(gtfs_fixture.dated_trip_counts)}"
        )

        found_drc = gtfs_fixture.dated_trip_counts.columns
        exp_cols_drc = pd.Index(["date", "route_type", "trip_count", "day"])

        assert (
            found_drc == exp_cols_drc
        ).all(), f"Columns were not as expected. Found {found_drc}"

        # tests the output of the daily_route_summary table
        # using tests/data/newport-20230613_gtfs.zip
        expected_df = {
            ("day", ""): {8: "friday", 9: "friday"},
            ("route_type", ""): {8: 3, 9: 200},
            ("trip_count", "max"): {8: 1211, 9: 90},
            ("trip_count", "mean"): {8: 1211.0, 9: 88.0},
            ("trip_count", "median"): {8: 1211.0, 9: 88.0},
            ("trip_count", "min"): {8: 1211, 9: 88},
        }

        found_df = gtfs_fixture.daily_trip_summary[
            gtfs_fixture.daily_trip_summary["day"] == "friday"
        ].to_dict()
        assert (
            found_df == expected_df
        ), f"Daily summary not as expected. Found {found_df}"

        # test that the dated_trip_counts can be returned
        expected_size = (542, 4)
        found_size = gtfs_fixture.summarise_trips(return_summary=False).shape
        assert expected_size == found_size, (
            "Size of date_route_counts not as expected. "
            "Expected {expected_size}"
        )

    def test_summarise_routes_on_pass(self, gtfs_fixture):
        """Assertions about the outputs from summarise_routes()."""
        gtfs_fixture.summarise_routes()
        # tests the daily_routes_summary return schema
        assert isinstance(
            gtfs_fixture.daily_route_summary, pd.core.frame.DataFrame
        ), (
            "Expected DF for daily_summary,"
            f"found {type(gtfs_fixture.daily_route_summary)}"
        )

        found_ds = gtfs_fixture.daily_route_summary.columns
        exp_cols_ds = pd.MultiIndex.from_tuples(
            [
                ("day", ""),
                ("route_count", "max"),
                ("route_count", "mean"),
                ("route_count", "median"),
                ("route_count", "min"),
                ("route_type", ""),
            ]
        )

        assert (
            found_ds == exp_cols_ds
        ).all(), f"Columns were not as expected. Found {found_ds}"

        # tests the self.dated_route_counts return schema
        assert isinstance(
            gtfs_fixture.dated_route_counts, pd.core.frame.DataFrame
        ), (
            "Expected DF for dated_route_counts,"
            f"found {type(gtfs_fixture.dated_route_counts)}"
        )

        found_drc = gtfs_fixture.dated_route_counts.columns
        exp_cols_drc = pd.Index(["date", "route_type", "day", "route_count"])

        assert (
            found_drc == exp_cols_drc
        ).all(), f"Columns were not as expected. Found {found_drc}"

        # tests the output of the daily_route_summary table
        # using tests/data/newport-20230613_gtfs.zip
        expected_df = {
            ("day", ""): {8: "friday", 9: "friday"},
            ("route_count", "max"): {8: 74, 9: 10},
            ("route_count", "mean"): {8: 74.0, 9: 9.0},
            ("route_count", "median"): {8: 74.0, 9: 9.0},
            ("route_count", "min"): {8: 74, 9: 9},
            ("route_type", ""): {8: 3, 9: 200},
        }

        found_df = gtfs_fixture.daily_route_summary[
            gtfs_fixture.daily_route_summary["day"] == "friday"
        ].to_dict()
        assert (
            found_df == expected_df
        ), f"Daily summary not as expected. Found {found_df}"

        # test that the dated_route_counts can be returned
        expected_size = (542, 4)
        found_size = gtfs_fixture.summarise_routes(return_summary=False).shape
        assert expected_size == found_size, (
            "Size of date_route_counts not as expected. "
            "Expected {expected_size}"
        )