from dataclasses import dataclass, asdict
from typing import Optional, Union


@dataclass
class Artwork:
    source: str
    source_id: Union[int, str]
    title: str
    artist: Optional[str]
    date: Optional[str]
    medium: Optional[str]
    image_url: str
    source_url: Optional[str]
    license: str
    width: int
    height: int
    orientation: str
    display_eligible: bool = True

    def to_dict(self):
        return asdict(self)
