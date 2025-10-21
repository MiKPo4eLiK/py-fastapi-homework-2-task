from datetime import date as dt_date, timedelta
from typing import List, Optional
from pydantic import BaseModel, Field, validator
from enum import Enum


class MovieStatus(str, Enum):
    released = "Released"
    post_production = "Post Production"
    in_production = "In Production"


class Country(BaseModel):
    id_: int
    code: str
    name: Optional[str] = None

    model_config = {"from_attributes": True}


class Genre(BaseModel):
    id_: int
    name: str

    model_config = {"from_attributes": True}


class Actor(BaseModel):
    id_: int
    name: str

    model_config = {"from_attributes": True}


class Language(BaseModel):
    id_: int
    name: str

    model_config = {"from_attributes": True}


class MovieBase(BaseModel):
    name: str = Field(..., max_length=255)
    release_date: dt_date
    score: float = Field(..., ge=0, le=100)
    overview: Optional[str] = None
    status: MovieStatus
    budget: float = Field(..., ge=0)
    revenue: float = Field(..., ge=0)


class MovieShort(BaseModel):
    id_: int
    name: str
    release_date: dt_date
    score: float
    overview: Optional[str]

    model_config = {"from_attributes": True}


class MovieFull(MovieBase):
    id_: int
    country: Optional[Country]
    genres: List[Genre]
    actors: List[Actor]
    languages: List[Language]

    model_config = {"from_attributes": True}


class MovieCreate(MovieBase):
    country: str
    genres: List[str]
    actors: List[str]
    languages: List[str]

    @classmethod
    @validator("release_date")
    def validate_release_date(cls, value: dt_date) -> dt_date:
        if value > dt_date.today() + timedelta(days=365):
            raise ValueError("Release date cannot be more than 1 year in the future.")
        return value

    @classmethod
    @validator("score")
    def validate_score(cls, value: float) -> float:
        if not (0 <= value <= 100):
            raise ValueError("Score must be between 0 and 100.")
        return value

    @classmethod
    @validator("budget", "revenue")
    def validate_non_negative(cls, value: float) -> float:
        if value < 0:
            raise ValueError("Budget and revenue must be non-negative.")
        return value


class MovieUpdate(BaseModel):
    name: Optional[str] = Field(None, max_length=255)
    release_date: Optional[dt_date] = None
    score: Optional[float] = None
    overview: Optional[str] = None
    status: Optional[MovieStatus] = None
    budget: Optional[float] = None
    revenue: Optional[float] = None

    country: Optional[str] = None
    genres: Optional[List[str]] = None
    actors: Optional[List[str]] = None
    languages: Optional[List[str]] = None

    @classmethod
    @validator("score")
    def validate_score(cls, value: Optional[float]) -> Optional[float]:
        if value is not None and not (0 <= value <= 100):
            raise ValueError("Score must be between 0 and 100.")
        return value

    @classmethod
    @validator("budget", "revenue")
    def validate_non_negative(cls, value: Optional[float]) -> Optional[float]:
        if value is not None and value < 0:
            raise ValueError("Budget and revenue must be non-negative.")
        return value


class MoviesListResponse(BaseModel):
    movies: List[MovieShort]
    prev_page: Optional[str]
    next_page: Optional[str]
    total_pages: int
    total_items: int


MovieListResponseSchema = MoviesListResponse
MovieDetailSchema = MovieFull
MovieListItemSchema = MovieShort
