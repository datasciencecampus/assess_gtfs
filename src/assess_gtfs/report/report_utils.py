"""Utils to assist in the creation of a HTML report for GTFS."""
import os
import pathlib
import shutil
from typing import Union

from assess_gtfs.utils.constants import PKG_PATH
from assess_gtfs.utils.defence import (
    _check_parent_dir_exists,
    _handle_path_like,
    _type_defence,
)


class TemplateHTML:
    """A class for inserting HTML string into a template.

    Attributes
    ----------
    template : str
        A string containing the HTML template.

    Methods
    -------
    _insert(placeholder: str, value: str, replace_multiple: bool = False)
        Insert values into the HTML template
    _get_template()
        Returns the template attribute

    """

    def __init__(self, path: Union[str, pathlib.Path]) -> None:
        """Initialise the TemplateHTML object.

        Parameters
        ----------
        path : Union[str, pathlib.Path]
            The file path of the html template

        Returns
        -------
        None

        Raises
        ------
        TypeError
            `path` is not either of string or pathlib.Path.

        """
        _handle_path_like(path, "path")
        with open(path, "r", encoding="utf8") as f:
            self.template = f.read()
        return None

    def _insert(
        self, placeholder: str, value: str, replace_multiple: bool = False
    ) -> None:
        """Insert values into the html template.

        Parameters
        ----------
        placeholder : str
            The placeholder name in the template. This is a string. In the
            template it should be surrounded by square brackets.
        value : str
            The value to place in the placeholder
            location.
        replace_multiple : bool, optional
            Whether or not to replace multiple placeholders that share the same
            placeholder value, by default False

        Returns
        -------
        None

        Raises
        ------
        ValueError
            A ValueError is raised if there are multiple instances of a
            place-holder but 'replace_multiple' is not True
        TypeError
            `placeholder` or `value` is not of type str.
            `replace_multiple` is not of type bool.

        """
        _type_defence(placeholder, "placeholder", str)
        _type_defence(value, "value", str)
        _type_defence(replace_multiple, "replace_multiple", bool)
        occurences = len(self.template.split(f"[{placeholder}]")) - 1
        if occurences > 1 and not replace_multiple:
            raise ValueError(
                "`replace_multiple` requires True as found \n"
                "multiple placeholder matches in template."
            )

        self.template = self.template.replace(f"[{placeholder}]", value)

    def _get_template(self) -> str:
        """Get the template attribute of the TemplateHTML object.

        This is an internal method.
        This method also allows for better testing with pytest.

        Returns
        -------
        str
            The template attribute

        """
        return self.template


def _set_up_report_dir(
    path: Union[str, pathlib.Path] = "outputs", overwrite: bool = False
) -> None:
    """Set up the directory that will hold the report.

    Parameters
    ----------
    path : Union[str, pathlib.Path], optional
        The path to the directory,
        by default "outputs"
    overwrite : bool, optional
        Whether or not to overwrite any current reports,
        by default False

    Returns
    -------
    None

    Raises
    ------
    FileExistsError
        Raises an error if you the gtfs report directory already exists in the
        given path and overwrite=False
    FileNotFoundError
        An error is raised if the `report_dir` parent directory could not be
        found.

    """
    # create report_dir var
    report_dir = os.path.join(path, "gtfs_report")
    # defences
    _check_parent_dir_exists(report_dir, "path", create=True)

    if os.path.exists(report_dir) and not overwrite:
        raise FileExistsError(
            "Report already exists at path: "
            f"[{path}]."
            "Consider setting overwrite=True "
            "if you'd like to overwrite this."
        )

    # make gtfs_report dir
    try:
        os.mkdir(report_dir)
    except FileExistsError:
        pass
    styles_loc = os.path.join(
        PKG_PATH, "data", "report", "css_styles", "styles.css"
    )
    shutil.copy(
        src=styles_loc,
        dst=report_dir,
    )
    return None
