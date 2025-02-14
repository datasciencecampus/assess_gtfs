"""Tests for multi_validation.py."""
import calendar
import glob
import os
import pathlib
import shutil
import subprocess
import zipfile
from copy import deepcopy

import folium
import numpy as np
import pandas as pd
import plotly.graph_objs as go
import pytest
from pyprojroot import here

from assess_gtfs.multi_validation import MultiGtfsInstance
from assess_gtfs.validation import GtfsInstance


@pytest.fixture(scope="function")
def multi_gtfs_paths():
    """Small test fixture for GTFS paths."""
    paths = [
        "tests/data/chester-20230816-small_gtfs.zip",
        "tests/data/newport-20230613_gtfs.zip",
    ]
    return paths


@pytest.fixture(scope="function")
def multi_gtfs_fixture(multi_gtfs_paths):
    """Test fixture for MultiGtfsInstance."""
    m_gtfs = MultiGtfsInstance(multi_gtfs_paths)
    return m_gtfs


@pytest.fixture(scope="function")
def multi_gtfs_altered_fixture(multi_gtfs_fixture):
    """Test fixture with calendar_dates.txt in GTFS instance 0."""
    # deepcopy otherwise it overwrites multi_gtfs_fixture
    mgtfs = deepcopy(multi_gtfs_fixture)
    dummy_cdates = pd.DataFrame(
        {
            "service_id": ["000001", "000001", "000002", "000003"],
            "date": ["20231211", "20240601", "20240613", "20220517"],
            "exception_type": [1, 1, 1, 1],
        }
    )
    mgtfs.instances[0].feed.calendar_dates = dummy_cdates
    mgtfs.instances[0].feed.calendar = None
    return mgtfs


class TestMultiGtfsInstance(object):
    """Tests for the MultiGtfsInstance class."""

    def test_init_defences(self, tmp_path):
        """Defensive tests for the class constructor."""
        # path not expected type
        with pytest.raises(
            TypeError, match=".*path.*expected.*str.*list.*Got.*int.*"
        ):
            MultiGtfsInstance(12)
        # not enough files found (0)
        with pytest.raises(FileNotFoundError, match="No GTFS files found."):
            MultiGtfsInstance(f"{tmp_path}/*.zip")
        # not enough files found (1)
        with open(os.path.join(tmp_path, "test.txt"), "w") as f:
            f.write("This is a test.")
        # files of wrong type
        with open(os.path.join(tmp_path, "test2.txt"), "w") as f:
            f.write("This is a test.")
        with pytest.raises(
            ValueError, match=r".*path\[0\].*expected.*zip.*Found .txt"
        ):
            MultiGtfsInstance(f"{tmp_path}/*.txt")

    def test_init(self, multi_gtfs_paths):
        """General tests for the constructor."""
        m_gtfs = MultiGtfsInstance(multi_gtfs_paths)
        assert np.array_equal(
            np.sort(m_gtfs.paths), np.sort(multi_gtfs_paths)
        ), "Paths not as expected"
        assert len(m_gtfs.paths) == 2, "Unexpected number of GTFS paths"
        assert (
            len(m_gtfs.instances) == 2
        ), "Unexpected number of GTFS instances"
        for inst in m_gtfs.instances:
            assert isinstance(
                inst, GtfsInstance
            ), "GtfsInstance not instanciated"
        # test singular gtfs path
        test_path = pathlib.Path(
            os.path.join("tests", "data", "chester-20230816-small_gtfs.zip")
        )
        m_gtfs_2 = MultiGtfsInstance(test_path)
        assert len(m_gtfs_2.paths) == 1, "Too many/Not enough paths passed"
        assert (
            pathlib.Path(m_gtfs.paths[0]) == test_path
        ), "Test path not as expected in MGTFS"

    def test_init_missing_calendar_and_dates(self, tmp_path):
        """Defensive test on init if calendar and calendar_dates is absent."""
        # test that error is raised when calendar and calendar dates is missing
        chest_pth = os.path.join(tmp_path, "chester-20230816-small_gtfs.zip")
        subprocess.run(
            [
                "cp",
                here("tests/data/chester-20230816-small_gtfs.zip"),
                chest_pth,
            ]
        )
        tmp_chester = os.path.join(tmp_path, "chester-20230816-small_gtfs")
        subprocess.run(["mkdir", tmp_chester])
        # unzip chester
        archive = zipfile.ZipFile(chest_pth)
        for file in archive.namelist():
            archive.extract(file, tmp_chester)
        for f in [
            "chester-20230816-small_gtfs.zip",
            "calendar.txt",
            "calendar_dates.txt",
        ]:
            subprocess.run(["rm", os.path.join(tmp_chester, f)])
        # get rid of original as we need to restore it with updated feed
        subprocess.run(["rm", chest_pth])
        # recreate the zip archive
        broken_feed = os.path.join(tmp_path, "broken_feed.zip")
        with zipfile.ZipFile(
            broken_feed, "w", zipfile.ZIP_DEFLATED
        ) as zip_ref:
            for folder_name, subfolders, filenames in os.walk(tmp_chester):
                for filename in filenames:
                    zip_ref.write(
                        os.path.join(tmp_chester, filename), arcname=filename
                    )
        zip_ref.close()
        gtfs = MultiGtfsInstance(broken_feed)
        # a feed exists that does not contain any calendar info. mgtfs should
        # raise when checking calendars
        with pytest.raises(
            FileNotFoundError,
            match="Both calendar and calendar_dates are empty for feed",
        ):
            gtfs.ensure_populated_calendars()

    def test_init_missing_calendar(self, multi_gtfs_paths, tmp_path):
        """Test init when calendar is missing.

        Fixtures do not cover the scenario of reliance on calendar_dates.
        Creates a tmp gtfs with a feed that has no calendar and a minimal
        calendar_dates.txt
        """
        for pth in multi_gtfs_paths:
            subprocess.run(["cp", pth, tmp_path])
        chest_pth = os.path.join(tmp_path, "chester-20230816-small_gtfs.zip")
        tmp_chester = os.path.join(tmp_path, "chester-20230816-small_gtfs")
        # unzip chester
        archive = zipfile.ZipFile(chest_pth)
        for file in archive.namelist():
            archive.extract(file, tmp_chester)
        # get rid of original as we need to restore it with updated feed
        subprocess.run(["rm", chest_pth])
        # make a new calendar_dates
        new_dates = pd.DataFrame(
            {
                "service_id": "740",
                "date": [
                    "20230731",
                    "20230801",
                    "20230802",
                    "20230803",
                    "20230804",
                ],
                "exception_type": "1",
            },
            index=list(range(0, 5)),
        )
        # remove the calendar and replace with calendar_dates
        subprocess.run(["rm", os.path.join(tmp_chester, "calendar.txt")])
        new_dates.to_csv(
            os.path.join(tmp_chester, "calendar_dates.txt"), index=False
        )
        # recreate the zip archive
        with zipfile.ZipFile(chest_pth, "w", zipfile.ZIP_DEFLATED) as zip_ref:
            for folder_name, subfolders, filenames in os.walk(tmp_chester):
                for filename in filenames:
                    zip_ref.write(
                        os.path.join(folder_name, filename), arcname=filename
                    )
        zip_ref.close()
        subprocess.run(["rm", "-r", tmp_chester])
        # we can now go ahead with multigtfs instantiation from the tmp
        m_gtfs = MultiGtfsInstance(tmp_path)
        m_gtfs.ensure_populated_calendars()
        which_chester = ["chester" in i for i in m_gtfs.paths]
        which_chester = [i for i, x in enumerate(which_chester) if x][0]
        updated_calendar = m_gtfs.instances[which_chester].feed.calendar
        assert updated_calendar is not None, "Calendar table was not found."
        n_cal = len(updated_calendar)
        assert (
            n_cal == 1
        ), f"Expected a calendar with one row, instead found {n_cal}"
        exp_calendar = pd.DataFrame(
            {
                "service_id": ["740"],
                "monday": [1],
                "tuesday": [1],
                "wednesday": [1],
                "thursday": [1],
                "friday": [1],
                "saturday": [0],
                "sunday": [0],
                "start_date": ["20230731"],
                "end_date": ["20230804"],
            },
            index=[0],
        )
        # ensure all ints are int8 as variable behaviour on different os
        weekdays = [day.lower() for day in calendar.day_name]
        for cnm in exp_calendar.columns:
            if cnm in weekdays:
                exp_calendar[cnm] = exp_calendar[cnm].astype("int8")
        pd.testing.assert_frame_equal(
            updated_calendar,
            exp_calendar,
        )

    def test_save_feeds(self, multi_gtfs_paths, tmp_path):
        """Tests for .save_feeds()."""
        gtfs = MultiGtfsInstance(multi_gtfs_paths)
        save_dir = os.path.join(tmp_path, "save_test")
        gtfs.save_feeds(save_dir)
        # assert .save created parent dir
        assert os.path.exists(save_dir), "Save directory not created"
        # assert files saved
        expected_paths = [
            "chester-20230816-small_gtfs_new.zip",
            "newport-20230613_gtfs_new.zip",
        ]
        found_paths = [
            os.path.basename(fpath) for fpath in glob.glob(save_dir + "/*.zip")
        ]
        assert np.array_equal(
            np.sort(expected_paths), np.sort(found_paths)
        ), "GtfsInstances not saved as expected"
        # test saves with filenames
        file_name_dir = os.path.join(tmp_path, "filenames")
        gtfs.save_feeds(
            dir=file_name_dir, file_names=["test1.zip", "test2.zip"]
        )
        assert len(os.listdir(file_name_dir)) == 2, "Not enough files saved"
        found_paths = [
            os.path.basename(fpath)
            for fpath in glob.glob(file_name_dir + "/*.zip")
        ]
        assert np.array_equal(
            np.sort(found_paths), np.sort(["test1.zip", "test2.zip"])
        ), "File names not saved correctly"

    def test_clean_feeds_defences(self, multi_gtfs_fixture):
        """Defensive tests for .clean_feeds()."""
        with pytest.raises(TypeError, match=".*clean_kwargs.*dict.*bool"):
            multi_gtfs_fixture.clean_feeds(True)

    def test_clean_feeds_on_pass(self, multi_gtfs_fixture):
        """General tests for .clean_feeds()."""
        # check with far stops logic first
        extra_valid_df = multi_gtfs_fixture.is_valid(
            validation_kwargs={"far_stops": True}
        )
        n = 14
        n_out = len(extra_valid_df)
        assert n_out == n, f"Expected extra_valid_df of len {n}, found {n_out}"
        # validate and do quick check on validity_df
        valid_df = multi_gtfs_fixture.is_valid()
        n = 12
        n_out = len(valid_df)
        assert n_out == n, f"Expected valid_df of len {n}, found {n_out}"
        # clean feed
        multi_gtfs_fixture.clean_feeds()
        # ensure cleaning has occured
        new_valid = multi_gtfs_fixture.is_valid()
        n = 11
        n_out = len(new_valid)
        assert n_out == n, f"Expected valid_df of len {n}, found {n_out}"
        assert np.array_equal(
            list(new_valid.iloc[4][["type", "table"]].values),
            ["error", "routes"],
        ), "Validity df after cleaning not as expected"

    def test_is_valid_defences(self, multi_gtfs_fixture):
        """Defensive tests for .is_valid()."""
        with pytest.raises(TypeError, match=".*validation_kwargs.*dict.*bool"):
            multi_gtfs_fixture.is_valid(True)

    def test_is_valid_on_pass(self, multi_gtfs_fixture):
        """General tests for is_valid()."""
        valid_df = multi_gtfs_fixture.is_valid()
        n = 12
        n_out = len(valid_df)
        assert n_out == n, f"Expected valid_df of len {n}, found {n_out}"
        assert np.array_equal(
            list(valid_df.iloc[4][["type", "message"]].values),
            (
                [
                    "error",
                    "Invalid route_type; maybe has extra space characters",
                ]
            ),
        )
        assert hasattr(
            multi_gtfs_fixture, "validity_df"
        ), "validity_df not created"
        assert isinstance(
            multi_gtfs_fixture.validity_df, pd.DataFrame
        ), "validity_df not a df"
        # run is valid but with fast travel logic
        n = 14
        extra_valid_df = multi_gtfs_fixture.is_valid(
            validation_kwargs={"far_stops": True}
        )
        n_out = len(extra_valid_df)
        assert n_out == n, f"Expected extra_valid_df of len {n}, found {n_out}"
        assert np.array_equal(
            list(extra_valid_df.iloc[4][["type", "message"]].values),
            (["warning", "Fast Travel Between Consecutive Stops"]),
        )

    def test_validate_empty_feeds(self, multi_gtfs_fixture):
        """Tests for validate_empty_feeds."""
        # emulate filtering the feeds to a box with no routes by dropping all
        # stop times
        [
            i.feed.stop_times.drop(i.feed.stop_times.index, inplace=True)
            for i in multi_gtfs_fixture.instances
        ]
        assert (
            len(multi_gtfs_fixture.validate_empty_feeds()) == 2
        ), "Two empty feeds were not found"
        # ensure they weren't deleted
        assert len(multi_gtfs_fixture.instances) == 2, "Feeds deleted"
        with pytest.warns(
            UserWarning, match="MultiGtfsInstance has no feeds."
        ):
            multi_gtfs_fixture.validate_empty_feeds(delete=True)
        assert len(multi_gtfs_fixture.instances) == 0, "Feeds were not deleted"

    def test_validate_empty_feeds_outputs_correct_filenames(
        self, multi_gtfs_paths, tmp_path
    ):
        """Regression test, labelled filenames are correct. Need 3 GTFS."""
        multi_gtfs_paths = sorted(multi_gtfs_paths)
        dest_paths = [
            os.path.join(tmp_path, os.path.basename(pth))
            for pth in multi_gtfs_paths
        ]
        # copy GTFS fixtures into tmp
        for s, d in zip(multi_gtfs_paths, dest_paths):
            shutil.copyfile(src=s, dst=d)
        # add a copy of chester - need 3 files to test filename sequencing
        dupe_chester = os.path.join(
            tmp_path, "DUPE_" + os.path.basename(multi_gtfs_paths[0])
        )
        shutil.copyfile(multi_gtfs_paths[0], dupe_chester)
        # check that we have the correct file setup in tmp
        tmp_contents_pre = sorted(os.listdir(tmp_path))
        assert tmp_contents_pre == [
            "DUPE_chester-20230816-small_gtfs.zip",
            "chester-20230816-small_gtfs.zip",
            "newport-20230613_gtfs.zip",
        ], f"Expected 3 GTFS before empty feed rm, found: {tmp_contents_pre}"
        # instantiate multi gtfs and filter to a newport BBOX with delete empty
        # feeds, expecting a single poulated GTFS with correct newport filenm
        gtfs = MultiGtfsInstance(tmp_path)
        n_expected = len(tmp_contents_pre)
        n_found = len(gtfs.instances)
        assert (
            n_found == n_expected
        ), f"Expected {n_expected} instances but found {n_found}"
        # filter to newport train station
        gtfs.filter_to_bbox(
            [-3.004961, 51.586603, -2.995325, 51.591028],
            delete_empty_feeds=True,
        )
        n_filtered = len(gtfs.instances)
        assert (
            n_filtered == 1
        ), f"Expected 1 instance after delete_empty_feeds, found {n_filtered}"
        # save the multi feed in a new directory in tmp
        out_pth = os.path.join(tmp_path, "NO_CHESTER")
        gtfs.save_feeds(out_pth)
        out_contents = os.listdir(out_pth)
        assert out_contents == [
            "newport-20230613_gtfs_new.zip"
        ], f"Saved feeds expected single Newport GTFS, found: {out_contents}"

    def test_filter_to_date_defences(self, multi_gtfs_fixture):
        """Defensive tests for .filter_to_date()."""
        with pytest.raises(
            TypeError, match=".*dates.*expected.*str.*list.*int.*"
        ):
            multi_gtfs_fixture.filter_to_date(12)
        with pytest.raises(
            ValueError,
            match=(
                r"In GTFS tests/data/chester-20230816-small_gtfs.zip."
                r"\n{\'20040109\'} passed to \'filter_dates\' not present in "
                r"feed dates.*"
            ),
        ):
            multi_gtfs_fixture.filter_to_date(["20040109"])

    def test_filter_to_date(self, multi_gtfs_fixture):
        """Tests for .filter_to_date()."""
        # assert original contents
        assert (
            len(multi_gtfs_fixture.instances[0].feed.stop_times) == 34249
        ), "Gtfs inst[0] not as expected"
        assert (
            len(multi_gtfs_fixture.instances[1].feed.stop_times) == 7765
        ), "Gtfs inst[1] not as expected"
        multi_gtfs_fixture.filter_to_date("20230806")
        # assert filtered contents
        assert (
            len(multi_gtfs_fixture.instances[0].feed.stop_times) == 984
        ), "Gtfs inst[0] not as expected after filter"
        assert (
            len(multi_gtfs_fixture.instances[1].feed.stop_times) == 151
        ), "Gtfs inst[1] not as expected after filter"

    def test_filter_to_bbox_defences(self, multi_gtfs_fixture):
        """Defensive tests for .filter_to_bbox()."""
        with pytest.raises(
            TypeError, match=".*bbox.*expected.*list.*GeoDataFrame.*int.*"
        ):
            multi_gtfs_fixture.filter_to_bbox(12)
        with pytest.raises(
            TypeError, match=".*crs.*expected.*str.*int.*.*DataFrame"
        ):
            multi_gtfs_fixture.filter_to_bbox(
                [12.0, 12.0, 13.0, 13.0], pd.DataFrame()
            )
        with pytest.raises(
            TypeError, match=".*delete_empty_feeds.*expected.*bool.*str.*"
        ):
            multi_gtfs_fixture.filter_to_bbox(
                [1.0, 1.0, 1.0, 1.0], 4326, "test"
            )
        # assert error is raised if bbox empties multi GTFS
        with pytest.raises(
            ValueError, match="BBOX.*has filtered.*to contain no data.*"
        ):
            multi_gtfs_fixture.filter_to_bbox(
                [1.0, 1.0, 1.0, 1.0], "epsg:4326", True
            )

    def test_filter_to_bbox(self, multi_gtfs_fixture):
        """Tests for .filter_to_bbox()."""
        # assert original contents
        assert (
            len(multi_gtfs_fixture.instances[0].feed.stop_times) == 34249
        ), "Gtfs inst[0] not as expected"
        assert (
            len(multi_gtfs_fixture.instances[1].feed.stop_times) == 7765
        ), "Gtfs inst[1] not as expected"
        # filter to bbox
        # (out of scope of Chester, so Chester GTFS should return 0)
        with pytest.warns(UserWarning):
            multi_gtfs_fixture.filter_to_bbox(
                [-2.985535, 51.551459, -2.919617, 51.606077]
            )
        # assert filtered contents
        assert (
            len(multi_gtfs_fixture.instances[0].feed.stop_times) == 0
        ), "Gtfs inst[0] not as expected after filter"
        assert (
            len(multi_gtfs_fixture.instances[1].feed.stop_times) == 217
        ), "Gtfs inst[1] not as expected after filter"

    @pytest.mark.parametrize(
        "which, summ_ops, sort_by_route_type, raises, match",
        (
            ["route", True, True, TypeError, ".*summ_ops.*list.*bool"],
            [True, [np.max], True, TypeError, ".*which.*str.*bool"],
            [
                "not_which",
                [np.max],
                True,
                ValueError,
                ".*which.*trips.*routes.*not_which.*",
            ],
            [
                "trips",
                [np.max],
                "not_sort",
                TypeError,
                ".*sort_by_route_type.*bool.*str",
            ],
        ),
    )
    def test__summarise_core_defence(
        self,
        multi_gtfs_fixture,
        which,
        summ_ops,
        sort_by_route_type,
        raises,
        match,
    ):
        """Defensive tests for _summarise_core()."""
        with pytest.raises(raises, match=match):
            multi_gtfs_fixture._summarise_core(
                which=which,
                summ_ops=summ_ops,
                sort_by_route_type=sort_by_route_type,
            )

    def test__summarise_core(self, multi_gtfs_fixture):
        """General tests for _summarise_core()."""
        # test summarising routes
        summary = multi_gtfs_fixture._summarise_core(
            which="routes", summ_ops=[np.max, np.mean]
        )
        assert isinstance(
            summary, pd.DataFrame
        ), "_summarise_core() did not return a df."
        assert (
            len(summary) == 590
        ), f"Number of rows in route summary df is {len(summary)} Expected 590"
        summ_routes = pd.DataFrame(
            {
                "date": ["2023-06-06", "2023-06-06"],
                "route_type": [3, 200],
                "route_count": [12, 4],
            },
            index=[2, 3],
        )
        summ_routes["date"] = pd.to_datetime(summ_routes["date"])
        pd.testing.assert_frame_equal(
            summary[summary.date == "2023-06-06"], summ_routes
        )
        # test summarising trips
        summary = multi_gtfs_fixture._summarise_core(
            which="trips", summ_ops=[np.max, np.mean]
        )
        assert isinstance(
            summary, pd.DataFrame
        ), "_summarise_core() did not return a df."
        assert (
            len(summary) == 590
        ), f"Number of rows in trip summary df is {len(summary)}. Expected 590"
        summ_trips = pd.DataFrame(
            {
                "date": ["2023-06-10", "2023-06-10"],
                "route_type": [3, 200],
                "trip_count": [120, 21],
            },
            index=[10, 11],
        )
        summ_trips["date"] = pd.to_datetime(summ_trips["date"])
        pd.testing.assert_frame_equal(
            summary[summary.date == "2023-06-10"], summ_trips
        )
        dated = multi_gtfs_fixture._summarise_core(
            which="routes", return_summary=False
        )
        assert isinstance(
            dated, pd.DataFrame
        ), "Returned dated table not DataFrame"
        assert len(dated) == 202955, "Returned dated table not as expected"
        dated_sum = multi_gtfs_fixture._summarise_core(
            which="routes", to_days=False
        )
        assert len(dated_sum) == 590, "Dated route counts not as expected"
        assert (
            dated_sum[dated_sum.date == "2024-04-06"].route_count.iloc[0] == 9
        ), "Unexpecteed number of routes on 2024-04-06"
        # test sorting to route_type
        route_sort = multi_gtfs_fixture._summarise_core(
            which="routes", to_days=True, sort_by_route_type=True
        )
        first_three_types = route_sort.route_type[:3]
        assert np.array_equal(
            first_three_types, [3, 3, 3]
        ), "Summary not sorted by route_type"

    def test_summarise_trips(self, multi_gtfs_fixture):
        """General tests for summarise_trips()."""
        # assert that the summary is returned
        summary = multi_gtfs_fixture.summarise_trips()
        assert isinstance(summary, pd.DataFrame)
        assert hasattr(multi_gtfs_fixture, "daily_trip_summary")

    def test_summarise_routes(self, multi_gtfs_fixture):
        """General tests for summarise_routes()."""
        # assert that the summary is returned
        summary = multi_gtfs_fixture.summarise_routes()
        assert isinstance(summary, pd.DataFrame)
        assert hasattr(multi_gtfs_fixture, "daily_route_summary")

    @pytest.mark.parametrize(
        "path, return_viz, filtered_only, raises, match",
        (
            [
                True,
                True,
                True,
                TypeError,
                ".*path.*expected.*str.*Path.*None.*Got.*bool.*",
            ],
            [
                "test.html",
                12,
                True,
                TypeError,
                ".*return_viz.*expected.*bool.*None.*Got.*int.*",
            ],
            [
                None,
                None,
                True,
                ValueError,
                "Both .*path.*return_viz.* parameters are of NoneType.",
            ],
            [
                "test.html",
                True,
                12,
                TypeError,
                ".*filtered_only.*expected.*bool.*Got.*int.*",
            ],
        ),
    )
    def test_viz_stops_defences(
        self,
        multi_gtfs_fixture,
        path,
        return_viz,
        filtered_only,
        raises,
        match,
    ):
        """Defensive tests for .viz_stops()."""
        with pytest.raises(raises, match=match):
            multi_gtfs_fixture.viz_stops(
                path=path, return_viz=return_viz, filtered_only=filtered_only
            )

    def test_viz_stops(self, multi_gtfs_fixture, tmp_path):
        """General tests for .viz_stops()."""
        # saving without returning
        save_path = os.path.join(tmp_path, "save_test.html")
        returned = multi_gtfs_fixture.viz_stops(
            path=save_path, return_viz=False
        )
        assert os.path.exists(save_path)
        assert isinstance(returned, type(None))
        # saving with returning
        save_path = os.path.join(tmp_path, "save_test2.html")
        returned = multi_gtfs_fixture.viz_stops(
            path=save_path, return_viz=True
        )
        assert os.path.exists(save_path)
        assert isinstance(returned, folium.Map)
        # returning without save
        returned = multi_gtfs_fixture.viz_stops(return_viz=True)
        assert isinstance(returned, folium.Map)
        files = glob.glob(f"{tmp_path}/*.html")
        assert len(files) == 2, "More files saved than expected"
        # returning a folium map without stop_code present
        multi_gtfs_fixture.instances[0].feed.stops.drop(
            "stop_code", axis=1, inplace=True
        )
        no_stop_code_map = multi_gtfs_fixture.viz_stops()
        assert isinstance(
            no_stop_code_map, folium.Map
        ), "Map not plotted without stop_code present"

    def test_get_dates_defence(self, multi_gtfs_fixture):
        """Defensive tests for .get_dates()."""
        with pytest.raises(
            TypeError, match=".*return_range.*expected.*bool.*Got.*str.*"
        ):
            multi_gtfs_fixture.get_dates(return_range="test")

    def test_get_dates(self, multi_gtfs_fixture, multi_gtfs_altered_fixture):
        """General tests for .get_dates()."""
        # multi gtfs with only calendar.txt
        # return_range=True
        assert (
            len(multi_gtfs_fixture.get_dates()) == 2
        ), "Unexpected number of dates returned"
        assert (
            multi_gtfs_fixture.get_dates()[0] == "20230605"
        ), "min not as expected"
        assert (
            multi_gtfs_fixture.get_dates()[1] == "20240426"
        ), "max not as expected"
        # return_range=False
        assert (
            len(multi_gtfs_fixture.get_dates(return_range=False)) == 5
        ), "Unexpected number of dates"
        # multi_gtfs with both calendar.txt and calendar_dates.txt
        # return_range=True
        assert (
            len(multi_gtfs_altered_fixture.get_dates()) == 2
        ), "Unexpected number of dates"
        assert (
            multi_gtfs_altered_fixture.get_dates()[0] == "20220517"
        ), "min not as expected"
        assert (
            multi_gtfs_altered_fixture.get_dates()[1] == "20240613"
        ), "max not as expected"
        # return_range=False
        assert (
            len(multi_gtfs_altered_fixture.get_dates(return_range=False)) == 6
        ), "Unexpected number of dates"
        pass

    def test__plot_core(self, multi_gtfs_fixture):
        """General tests for _plot_core()."""
        # route summary
        data = multi_gtfs_fixture.summarise_routes()
        route_fig = multi_gtfs_fixture._plot_core(data, "route_count")
        assert isinstance(route_fig, go.Figure), "Route counts not plotted"
        # trip summary
        data = multi_gtfs_fixture.summarise_trips()
        trip_fig = multi_gtfs_fixture._plot_core(data, "trip_count")
        assert isinstance(trip_fig, go.Figure), "Trip counts not plotted"
        # trip summary with custom title
        trip_fig = multi_gtfs_fixture._plot_core(
            data, "trip_count", title="test"
        )
        found_title = trip_fig.layout["title"]["text"]
        assert found_title == "test", "Title not as expected"
        # trip summary with custom dimensions
        trip_fig = multi_gtfs_fixture._plot_core(
            data, "trip_count", height=100, width=150
        )
        found_height = trip_fig.layout["height"]
        found_width = trip_fig.layout["width"]
        assert found_height == 100, "Height not as expected"
        assert found_width == 150, "Width not as expected"
        # custom kwargs
        trip_fig = multi_gtfs_fixture._plot_core(
            data, "trip_count", kwargs={"markers": True}
        )
        assert trip_fig.data[0]["mode"] in [
            "markers+lines",
            "lines+markers",
        ], "Markers not plotted"
        # rolling average
        avg_fig = multi_gtfs_fixture._plot_core(
            data, "trip_count", rolling_average=7
        )
        found_ylabel = avg_fig.layout["yaxis"]["title"]["text"]
        assert (
            found_ylabel == "7 Day Rolling Average"
        ), "Rolling average not plotted"
        # draw a line on a date
        avg_fig = multi_gtfs_fixture._plot_core(
            data, "trip_count", rolling_average=7, line_date="2023-12-01"
        )
        found_line = avg_fig.layout["shapes"][0]["line"]["dash"]
        assert found_line == "dash", "Date line not plotted"

    def test_plot_service(self, multi_gtfs_fixture):
        """General tests for .plot_service()."""
        # plot route_type
        fig = multi_gtfs_fixture.plot_service(service_type="routes")
        assert len(fig.data) == 2, "Not plotted by modality"
        # plot without route type
        fig = multi_gtfs_fixture.plot_service(
            service_type="routes", route_type=False
        )
        assert len(fig.data) == 1, "Plot not as expected"
        # rolling average + no route type
        avg_fig = multi_gtfs_fixture.plot_service(
            service_type="routes", rolling_average=7, route_type=False
        )
        leg_status = avg_fig.data[0]["showlegend"]
        assert not leg_status, "Multiple route types found"
        # plot trips
        fig = multi_gtfs_fixture.plot_service(service_type="trips")
        assert len(fig.data) == 2, "Not plotted by modality"
        # plot without route type
        fig = multi_gtfs_fixture.plot_service(
            service_type="trips", route_type=False
        )
        assert len(fig.data) == 1, "Plot not as expected"
