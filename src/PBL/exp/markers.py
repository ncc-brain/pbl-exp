"""Utilities for generating PsychoPy stimuli from ArUco and AprilTag markers."""

from __future__ import annotations

import operator
import re
from collections.abc import Iterable, Iterator
from typing import Literal

import cv2
import numpy as np
from psychopy import visual

# ---------------------------------------------------------------------------
# Supported marker families and layouts
# ---------------------------------------------------------------------------

APRILTAG_FAMILIES: tuple[str, ...] = (
    "16h5",
    "25h9",
    "36h10",
    "36h11",
)

ARUCO_SIZES: tuple[str, ...] = (
    "4x4",
    "5x5",
    "6x6",
    "7x7",
)

ARUCO_NUMBERS: tuple[str, ...] = (
    "50",
    "100",
    "250",
    "1000",
)

MarkerType = Literal["april", "aruco"]

_ARUCO_FAMILY_PATTERN = re.compile(r"^(?P<rows>\d+)x(?P<columns>\d+)_(?P<number>\d+)$")


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def create_fiducial_marker_stimuli(
    win: visual.Window,
    marker_family: str,
    marker_ids: Iterable[int],
    marker_size_pixels: int,
    auto_layout: bool = True,
    margin: int = 50,
) -> list[visual.ImageStim]:
    """
    Generate PsychoPy stimuli for a collection of fiducial markers.

    Markers are generated from one of OpenCV's predefined ArUco or AprilTag
    dictionaries. Each marker is returned as an independent
    :class:`psychopy.visual.ImageStim`.

    When automatic layout is enabled, 4, 6, or 8 markers are positioned around
    the perimeter of the window. Marker IDs are assigned clockwise, beginning
    at the top-left:

    Four markers::

        0 -------- 1
        |          |
        3 -------- 2

    Six markers::

        0 ---- 1 ---- 2
        |             |
        5 ---- 4 ---- 3

    Eight markers::

        0 ---- 1 ---- 2
        |             |
        7             3
        |             |
        6 ---- 5 ---- 4

    Parameters
    ----------
    win : psychopy.visual.Window
        Window in which the marker stimuli will be drawn.
    marker_family : str
        Marker dictionary to use. Supported values are:

        - AprilTag families: ``"16h5"``, ``"25h9"``, ``"36h10"``,
          and ``"36h11"``.
        - ArUco dictionaries in ``"{size}_{number}"`` format, such as
          ``"4x4_50"`` or ``"6x6_250"``.
        - The original ArUco dictionary: ``"aruco_original"``.

        Family names are case-insensitive, and surrounding whitespace is
        ignored.
    marker_ids : Iterable[int]
        Marker identifiers to generate. Each identifier must be valid for the
        selected dictionary. When automatic layout is enabled, their order
        determines their clockwise placement, beginning at the top-left.
    marker_size_pixels : int
        Width and height of each square marker, in pixels.
    auto_layout : bool, default=True
        If ``True``, automatically position the markers around the perimeter
        of the window. Automatic layout supports exactly 4, 6, or 8 markers.
        If ``False``, all markers are initially centered at ``(0, 0)``.
    margin : int, default=50
        Minimum distance, in pixels, between each automatically positioned
        marker and the nearest window edge. This argument is ignored when
        ``auto_layout`` is ``False``.

    Returns
    -------
    list of psychopy.visual.ImageStim
        Generated marker stimuli in the same order as ``marker_ids``.

    Raises
    ------
    TypeError
        If an argument has an invalid type.
    ValueError
        If the marker family, marker IDs, marker size, margin, or automatic
        layout is invalid.
    RuntimeError
        If the installed OpenCV build does not provide the ``aruco`` module.

    Examples
    --------
    Generate four markers positioned clockwise from the top-left:

    >>> markers = create_fiducial_marker_stimuli(
    ...     win=win,
    ...     marker_family="36h11",
    ...     marker_ids=[0, 1, 2, 3],
    ...     marker_size_pixels=200,
    ...     auto_layout=True,
    ...     margin=50,
    ... )
    >>> for marker in markers:
    ...     marker.draw()
    >>> win.flip()

    Generate markers without assigning positions:

    >>> markers = create_fiducial_marker_stimuli(
    ...     win=win,
    ...     marker_family="6x6_250",
    ...     marker_ids=[10, 11],
    ...     marker_size_pixels=200,
    ...     auto_layout=False,
    ... )
    >>> markers[0].pos = (-300, 0)
    >>> markers[1].pos = (300, 0)
    """
    if not isinstance(auto_layout, (bool, np.bool_)):
        raise TypeError(
            f"auto_layout must be a Boolean, not {type(auto_layout).__name__}."
        )

    marker_ids = _validate_marker_ids(marker_ids)

    # Validate the image size before creating the PsychoPy stimuli.
    marker_type, aruco_dictionary = _marker_family_to_dict(marker_family)
    del marker_type  # The generator resolves this again when creating images.

    marker_size_pixels = _validate_marker_size(
        marker_size_pixels,
        aruco_dictionary,
    )

    marker_images = _generate_markers(
        marker_family=marker_family,
        marker_ids=marker_ids,
        marker_size_pixels=marker_size_pixels,
    )

    stimuli = [
        visual.ImageStim(
            win=win,
            image=marker_image,
            units="pix",
            size=(marker_size_pixels, marker_size_pixels),
            pos=(0, 0),
            opacity=1.0,
            interpolate=False,
            name=f"{marker_family}_{marker_id}",
        )
        for marker_id, marker_image in zip(
            marker_ids,
            marker_images,
            strict=True,
        )
    ]

    if auto_layout:
        positions = _calculate_marker_positions(
            window_size_pixels=win.size,
            number_of_markers=len(stimuli),
            marker_size_pixels=marker_size_pixels,
            margin=margin,
        )

        for stimulus, position in zip(stimuli, positions, strict=True):
            stimulus.pos = position

    return stimuli


# ---------------------------------------------------------------------------
# Marker-family handling
# ---------------------------------------------------------------------------


def _marker_family_to_dict(
    marker_family: str,
) -> tuple[MarkerType, cv2.aruco.Dictionary]:
    """
    Resolve a marker-family name to an OpenCV predefined dictionary.

    Parameters
    ----------
    marker_family : str
        AprilTag or ArUco marker-family name.

    Returns
    -------
    marker_type : {"april", "aruco"}
        General type of the selected marker family.
    aruco_dictionary : cv2.aruco.Dictionary
        Corresponding OpenCV predefined dictionary.

    Raises
    ------
    TypeError
        If ``marker_family`` is not a string.
    ValueError
        If the marker-family name is not recognized.
    RuntimeError
        If the installed OpenCV build does not provide the ``aruco`` module.
    """
    if not isinstance(marker_family, str):
        raise TypeError(
            f"marker_family must be a string, not {type(marker_family).__name__}."
        )

    if not hasattr(cv2, "aruco"):
        raise RuntimeError(
            "The installed OpenCV build does not provide the aruco module. "
            "Install a build that includes OpenCV's contributed modules, "
            "such as 'opencv-contrib-python'."
        )

    normalized_family = marker_family.strip().lower()

    # AprilTag dictionaries use names such as DICT_APRILTAG_36H11.
    if normalized_family in APRILTAG_FAMILIES:
        dictionary_name = f"DICT_APRILTAG_{normalized_family.upper()}"
        dictionary_id = getattr(cv2.aruco, dictionary_name)

        return (
            "april",
            cv2.aruco.getPredefinedDictionary(dictionary_id),
        )

    # OpenCV also provides the original ArUco dictionary.
    if normalized_family == "aruco_original":
        return (
            "aruco",
            cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_ARUCO_ORIGINAL),
        )

    # Other ArUco dictionaries use names such as 4x4_50 and 6x6_250.
    match = _ARUCO_FAMILY_PATTERN.fullmatch(normalized_family)

    if match is not None:
        rows = match.group("rows")
        columns = match.group("columns")
        number = match.group("number")
        size = f"{rows}x{columns}"

        if rows != columns:
            raise ValueError(
                f"ArUco markers must be square, but '{marker_family}' "
                f"specifies a {rows}x{columns} marker."
            )

        if size not in ARUCO_SIZES:
            raise ValueError(
                f"Unsupported ArUco marker size '{size}'. "
                f"Supported sizes are: {', '.join(ARUCO_SIZES)}."
            )

        if number not in ARUCO_NUMBERS:
            raise ValueError(
                f"Unsupported ArUco dictionary size '{number}'. "
                "Supported dictionary sizes are: "
                f"{', '.join(ARUCO_NUMBERS)}."
            )

        dictionary_name = f"DICT_{size.upper()}_{number}"
        dictionary_id = getattr(cv2.aruco, dictionary_name)

        return (
            "aruco",
            cv2.aruco.getPredefinedDictionary(dictionary_id),
        )

    raise ValueError(
        f"Unrecognized marker family '{marker_family}'. Supported formats "
        "are:\n"
        f"  AprilTag: {', '.join(APRILTAG_FAMILIES)}\n"
        "  ArUco: {size}_{number}, for example '6x6_250'\n"
        f"    Sizes: {', '.join(ARUCO_SIZES)}\n"
        f"    Dictionary sizes: {', '.join(ARUCO_NUMBERS)}\n"
        "  Original ArUco: aruco_original"
    )


# ---------------------------------------------------------------------------
# Marker generation
# ---------------------------------------------------------------------------


def _generate_markers(
    marker_family: str,
    marker_ids: Iterable[int],
    marker_size_pixels: int,
) -> Iterator[np.ndarray]:
    """
    Generate marker images suitable for use by PsychoPy.

    Parameters
    ----------
    marker_family : str
        Name of the OpenCV AprilTag or ArUco dictionary.
    marker_ids : Iterable[int]
        Marker identifiers to generate.
    marker_size_pixels : int
        Width and height of each generated marker, in pixels.

    Yields
    ------
    numpy.ndarray
        A square, contiguous ``int8`` array containing values in ``{-1, 1}``.
        PsychoPy interprets ``-1`` as black and ``1`` as white.

    Raises
    ------
    TypeError
        If ``marker_size_pixels`` is not an integer.
    ValueError
        If the marker size or a marker identifier is invalid.
    """
    marker_type, aruco_dictionary = _marker_family_to_dict(marker_family)

    marker_size_pixels = _validate_marker_size(
        marker_size_pixels,
        aruco_dictionary,
    )

    number_of_available_markers = len(aruco_dictionary.bytesList)

    for marker_id in marker_ids:
        if not 0 <= marker_id < number_of_available_markers:
            raise ValueError(
                f"Marker ID {marker_id} is invalid for family "
                f"'{marker_family}'. Valid IDs range from 0 to "
                f"{number_of_available_markers - 1}."
            )

        image = cv2.aruco.generateImageMarker(
            aruco_dictionary,
            marker_id,
            marker_size_pixels,
        )

        # OpenCV represents marker images using values in {0, 255}, whereas
        # PsychoPy's default image color range is {-1, 1}.
        image = np.where(image > 0, 1, -1).astype(
            np.int8,
            copy=False,
        )

        if marker_type == "april":
            # OpenCV and PsychoPy use different orientation conventions for
            # AprilTag images. This transformation preserves the orientation
            # expected by the corresponding detector.
            #
            # See: https://github.com/opencv/opencv-python/issues/1195
            image = np.fliplr(image)
        else:
            # PsychoPy's image y-axis is inverted relative to OpenCV's.
            image = np.flipud(image)

        # Flip operations can create arrays with negative strides. Return a
        # contiguous array to ensure compatibility with PsychoPy and OpenGL.
        yield np.ascontiguousarray(image)


# ---------------------------------------------------------------------------
# Input validation
# ---------------------------------------------------------------------------


def _calculate_marker_positions(
    window_size_pixels: Iterable[int],
    number_of_markers: int,
    marker_size_pixels: int,
    margin: int,
) -> list[tuple[float, float]]:
    """
    Calculate clockwise marker positions around a window's perimeter.

    Position order begins at the top-left and proceeds clockwise. Exactly 4,
    6, or 8 markers are supported.

    Parameters
    ----------
    window_size_pixels : Iterable[int]
        Window width and height, in pixels.
    number_of_markers : int
        Number of marker positions to calculate. Must be 4, 6, or 8.
    marker_size_pixels : int
        Width and height of each marker, in pixels.
    margin : int
        Distance between each marker and the nearest window edge, in pixels.

    Returns
    -------
    list of tuple of float
        Marker-center positions in PsychoPy pixel coordinates.

    Raises
    ------
    TypeError
        If ``margin`` is not an integer.
    ValueError
        If the number of markers is unsupported, the margin is negative, or
        the markers do not fit within the window.
    """
    if margin < 0:
        raise ValueError(f"margin must be nonnegative; received {margin}.")

    if number_of_markers not in {4, 6, 8}:
        raise ValueError(
            "Automatic layout supports exactly 4, 6, or 8 markers; "
            f"received {number_of_markers}. Set auto_layout=False to "
            "position a different number of markers manually."
        )

    window_size = np.asarray(window_size_pixels, dtype=float)

    if window_size.shape != (2,):
        raise ValueError(
            "window_size_pixels must contain exactly two values: width and height."
        )

    window_width, window_height = window_size

    required_extent = marker_size_pixels + 2 * margin

    if required_extent > window_width:
        raise ValueError(
            f"A {marker_size_pixels}-pixel marker with a {margin}-pixel "
            f"margin does not fit within the {window_width:g}-pixel "
            "window width."
        )

    if required_extent > window_height:
        raise ValueError(
            f"A {marker_size_pixels}-pixel marker with a {margin}-pixel "
            f"margin does not fit within the {window_height:g}-pixel "
            "window height."
        )

    half_marker_size = marker_size_pixels / 2

    left = -window_width / 2 + half_marker_size + margin
    center_x = 0.0
    right = window_width / 2 - half_marker_size - margin

    top = window_height / 2 - half_marker_size - margin
    center_y = 0.0
    bottom = -window_height / 2 + half_marker_size + margin

    if number_of_markers == 4:
        return [
            (left, top),  # 0: top-left
            (right, top),  # 1: top-right
            (right, bottom),  # 2: bottom-right
            (left, bottom),  # 3: bottom-left
        ]

    if number_of_markers == 6:
        return [
            (left, top),  # 0: top-left
            (center_x, top),  # 1: top-center
            (right, top),  # 2: top-right
            (right, bottom),  # 3: bottom-right
            (center_x, bottom),  # 4: bottom-center
            (left, bottom),  # 5: bottom-left
        ]

    return [
        (left, top),  # 0: top-left
        (center_x, top),  # 1: top-center
        (right, top),  # 2: top-right
        (right, center_y),  # 3: middle-right
        (right, bottom),  # 4: bottom-right
        (center_x, bottom),  # 5: bottom-center
        (left, bottom),  # 6: bottom-left
        (left, center_y),  # 7: middle-left
    ]


def _validate_marker_ids(marker_ids: Iterable[int]) -> list[int]:
    """
    Materialize and validate a sequence of marker identifiers.

    ``operator.index`` accepts Python and NumPy integer types while rejecting
    floating-point values, including integer-valued floats such as ``1.0``.
    """
    try:
        iterator = iter(marker_ids)
    except TypeError as error:
        raise TypeError("marker_ids must be an iterable of integers.") from error

    validated_ids: list[int] = []

    for position, marker_id in enumerate(iterator):
        if isinstance(marker_id, (bool, np.bool_)):
            raise TypeError(
                f"Marker ID at position {position} is Boolean; "
                "marker IDs must be integers."
            )

        try:
            validated_id = operator.index(marker_id)
        except TypeError as error:
            raise TypeError(
                f"Marker ID at position {position} must be an integer, "
                f"not {type(marker_id).__name__}."
            ) from error

        validated_ids.append(validated_id)

    return validated_ids


def _validate_marker_size(
    marker_size_pixels: int,
    aruco_dictionary: cv2.aruco.Dictionary,
) -> int:
    """Validate and return the requested marker image size."""
    if isinstance(marker_size_pixels, (bool, np.bool_)):
        raise TypeError("marker_size_pixels must be an integer, not a Boolean.")

    try:
        marker_size_pixels = operator.index(marker_size_pixels)
    except TypeError as error:
        raise TypeError(
            "marker_size_pixels must be an integer, "
            f"not {type(marker_size_pixels).__name__}."
        ) from error

    # A generated image needs enough pixels for the marker data plus the
    # default one-cell border on each side.
    minimum_size_pixels = int(aruco_dictionary.markerSize) + 2

    if marker_size_pixels < minimum_size_pixels:
        raise ValueError(
            f"marker_size_pixels must be at least {minimum_size_pixels} "
            f"for this dictionary; received {marker_size_pixels}."
        )

    return marker_size_pixels
