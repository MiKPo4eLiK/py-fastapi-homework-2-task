from datetime import date, timedelta
from typing import List, Optional
from pydantic import BaseModel, Field, validator
from enum import Enum


class MovieStatus(str, Enum):
    released = "Released"
    post_production = "Post Production"
    in_production = "In Production"


class Country(BaseModel):
    id: int
    code: str
    name: Optional[str] = None

    class Config:
        orm_mode = True


class Genre(BaseModel):
    id: int
    name: str

    class Config:
        orm_mode = True


class Actor(BaseModel):
    id: int
    name: str

    class Config:
        orm_mode = True


class Language(BaseModel):
    id: int
    name: str

    class Config:
        orm_mode = True


class MovieBase(BaseModel):
    name: str = Field(..., max_length=255)
    date: date
    score: float = Field(..., ge=0, le=100)
    overview: Optional[str] = None
    status: MovieStatus
    budget: float = Field(..., ge=0)
    revenue: float = Field(..., ge=0)


class MovieShort(BaseModel):
    id: int
    name: str
    date: date
    score: float
    overview: Optional[str]

    class Config:
        orm_mode = True


class MovieFull(MovieBase):
    id: int
    country: Optional[Country]
    genres: List[Genre]
    actors: List[Actor]
    languages: List[Language]

    class Config:
        orm_mode = True


class MovieCreate(MovieBase):
    country: str
    genres: List[str]
    actors: List[str]
    languages: List[str]

    @validator("date")
    def validate_date(cls, v: date):
        if v > date.today() + timedelta(days=365):
            raise ValueError("Date cannot be more than 1 year in the future.")
        return v

    @validator("score")
    def validate_score(cls, v: float):
        if not (0 <= v <= 100):
            raise ValueError("Score must be between 0 and 100.")
        return v

    @validator("budget", "revenue")
    def validate_non_negative(cls, v: float):
        if v < 0:
            raise ValueError("Budget and revenue must be non-negative.")
        return v


class MovieUpdate(BaseModel):
    name: Optional[str]
    date: Optional[date]
    score: Optional[float]
    overview: Optional[str]
    status: Optional[MovieStatus]
    budget: Optional[float]
    revenue: Optional[float]

    @validator("score")
    def validate_score(cls, v: Optional[float]):
        if v is not None and not (0 <= v <= 100):
            raise ValueError("Score must be between 0 and 100.")
        return v

    @validator("budget", "revenue")
    def validate_non_negative(cls, v: Optional[float]):
        if v is not None and v < 0:
            raise ValueError("Budget and revenue must be non-negative.")
        return v


class MoviesListResponse(BaseModel):
    movies: List[MovieShort]
    prev_page: Optional[str]
    next_page: Optional[str]
    total_pages: int
    total_items: int


# Aliases for convenience
MovieListResponseSchema = MoviesListResponse
MovieDetailSchema = MovieFull
MovieListItemSchema = MovieShort
