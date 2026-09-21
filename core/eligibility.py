from .artwork import Artwork


# Our physical frame is permanently landscape, 1600 × 1200.
TARGET_ASPECT_RATIO = 1600 / 1200

# Allow artwork to be somewhat different from 4:3.
# The image pipeline will handle the final crop.
MIN_ASPECT_RATIO = 0.75
MAX_ASPECT_RATIO = 1.80

# Minimum source dimensions.
# We want enough resolution for a high-quality 1600 × 1200 output.
MIN_WIDTH = 1200
MIN_HEIGHT = 900


def check_display_eligibility(artwork: Artwork) -> bool:
    """
    Determine whether an artwork meets our initial technical
    requirements for the landscape frame.
    """

    if not artwork.image_url:
        return False

    if artwork.license != "CC0":
        return False

    if artwork.width < MIN_WIDTH:
        return False

    if artwork.height < MIN_HEIGHT:
        return False

    aspect_ratio = artwork.width / artwork.height

    if aspect_ratio < MIN_ASPECT_RATIO:
        return False

    if aspect_ratio > MAX_ASPECT_RATIO:
        return False

    return True
